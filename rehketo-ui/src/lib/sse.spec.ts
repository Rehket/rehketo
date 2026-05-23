import { beforeEach, describe, expect, test, vi } from 'vitest';

import { subscribeRun, type RunStreamHandlers } from './sse';
import type { MessageOut, RunEvent } from './types';

// EventSource mock that matches browser dispatch semantics: SSE frames
// with `event: <name>` dispatch as custom events of that name — NOT as
// generic `message` events. The real backend emits `event: message.delta`,
// `event: run.ended`, etc., so tests must too, or we'd mask a class of
// bug where the client listens for the wrong event type.
class MockEventSource {
	static instances: MockEventSource[] = [];
	readonly url: string;
	closed = false;
	private listeners: Record<string, ((e: Event) => void)[]> = {};

	constructor(url: string) {
		this.url = url;
		MockEventSource.instances.push(this);
	}

	addEventListener(name: string, fn: (e: Event) => void): void {
		(this.listeners[name] ??= []).push(fn);
	}

	close(): void {
		this.closed = true;
	}

	emitEvent(event: RunEvent): void {
		const me = new MessageEvent(event.type, { data: JSON.stringify(event) });
		for (const fn of this.listeners[event.type] ?? []) fn(me);
	}

	emitRaw(eventType: string, data: string): void {
		const me = new MessageEvent(eventType, { data });
		for (const fn of this.listeners[eventType] ?? []) fn(me);
	}

	emitError(): void {
		for (const fn of this.listeners.error ?? []) fn(new Event('error'));
	}
}

function mkMessage(overrides: Partial<MessageOut> = {}): MessageOut {
	return {
		id: 'msg-1',
		conversation_id: 'conv-1',
		role: 'assistant',
		content: { text: 'hello' },
		run_id: 'run-1',
		created_at: '2026-04-21T00:00:00Z',
		run_status: 'succeeded',
		run_error: null,
		...overrides
	};
}

function collectHandlers(): {
	deltas: string[];
	completes: MessageOut[];
	statuses: string[];
	updates: { id: string; title: string }[];
	ended: number;
	errors: number;
	handlers: RunStreamHandlers;
} {
	const deltas: string[] = [];
	const completes: MessageOut[] = [];
	const statuses: string[] = [];
	const updates: { id: string; title: string }[] = [];
	let ended = 0;
	let errors = 0;
	return {
		deltas,
		completes,
		statuses,
		updates,
		ended,
		errors,
		get handlers(): RunStreamHandlers {
			return {
				onDelta: (d) => deltas.push(d),
				onMessageComplete: (m) => completes.push(m),
				onStatus: (s) => statuses.push(s),
				onConversationUpdated: (id, title) => updates.push({ id, title }),
				onEnded: () => {
					ended++;
				},
				onError: () => {
					errors++;
				}
			};
		}
	};
}

describe('subscribeRun', () => {
	beforeEach(() => {
		MockEventSource.instances.length = 0;
	});

	test('success flow: deltas → complete → succeeded → ended (run.ended closes)', () => {
		const c = collectHandlers();
		const sub = subscribeRun('run-1', c.handlers, {
			EventSourceImpl: MockEventSource as unknown as typeof EventSource
		});
		const src = MockEventSource.instances[0]!;

		src.emitEvent({
			type: 'message.delta',
			delta: 'hel',
			message_id: 'm1',
			sequence: 1,
			run_id: 'run-1'
		});
		src.emitEvent({
			type: 'message.delta',
			delta: 'lo',
			message_id: 'm1',
			sequence: 2,
			run_id: 'run-1'
		});
		expect(sub.state).toBe('running');

		src.emitEvent({
			type: 'message.complete',
			message: mkMessage(),
			sequence: 3,
			run_id: 'run-1'
		});

		src.emitEvent({ type: 'run.status', status: 'succeeded', sequence: 4, run_id: 'run-1' });
		expect(sub.state).toBe('terminalSucceeded');
		expect(src.closed).toBe(false); // succeeded alone does NOT close

		src.emitEvent({
			type: 'conversation.updated',
			conversation_id: 'conv-1',
			title: 'new',
			sequence: 5,
			run_id: 'run-1'
		});

		src.emitEvent({ type: 'run.ended', sequence: 6, run_id: 'run-1' });
		expect(src.closed).toBe(true);
		expect(sub.state).toBe('terminalSucceeded');

		expect(c.deltas.join('')).toBe('hello');
		expect(c.completes).toHaveLength(1);
		expect(c.statuses).toEqual(['succeeded']);
		expect(c.updates).toEqual([{ id: 'conv-1', title: 'new' }]);
	});

	test('failure flow: delta → failed → ended (no message.complete)', () => {
		const c = collectHandlers();
		const sub = subscribeRun('run-f', c.handlers, {
			EventSourceImpl: MockEventSource as unknown as typeof EventSource
		});
		const src = MockEventSource.instances[0]!;

		src.emitEvent({
			type: 'message.delta',
			delta: 'partial',
			message_id: 'm1',
			sequence: 1,
			run_id: 'run-f'
		});
		src.emitEvent({
			type: 'run.status',
			status: 'failed',
			error: { code: 'llm_failure', message: 'boom' },
			sequence: 2,
			run_id: 'run-f'
		});
		expect(sub.state).toBe('terminalFailed');
		expect(src.closed).toBe(false);

		src.emitEvent({ type: 'run.ended', sequence: 3, run_id: 'run-f' });
		expect(src.closed).toBe(true);
		expect(sub.state).toBe('terminalFailed');
		expect(c.completes).toEqual([]);
	});

	test('cancel flow: delta → cancelled → ended', () => {
		const c = collectHandlers();
		const sub = subscribeRun('run-c', c.handlers, {
			EventSourceImpl: MockEventSource as unknown as typeof EventSource
		});
		const src = MockEventSource.instances[0]!;

		src.emitEvent({
			type: 'message.delta',
			delta: 'half',
			message_id: 'm1',
			sequence: 1,
			run_id: 'run-c'
		});
		src.emitEvent({ type: 'run.status', status: 'cancelled', sequence: 2, run_id: 'run-c' });
		src.emitEvent({ type: 'run.ended', sequence: 3, run_id: 'run-c' });

		expect(sub.state).toBe('terminalCancelled');
		expect(src.closed).toBe(true);
	});

	test('native EventSource error mid-run closes stream and reports', () => {
		const c = collectHandlers();
		const sub = subscribeRun('run-x', c.handlers, {
			EventSourceImpl: MockEventSource as unknown as typeof EventSource
		});
		const src = MockEventSource.instances[0]!;

		src.emitError();

		expect(src.closed).toBe(true);
		expect(sub.state).toBe('closed');
	});

	test('error after terminal status is treated as normal EOF — no onError', () => {
		// Browsers fire `error` whenever the server closes the HTTP stream,
		// including the normal EOF after run.ended. When we've already seen
		// a terminal run.status, suppress the disconnect signal.
		const onError = vi.fn();
		const onEnded = vi.fn();
		subscribeRun(
			'run-tail',
			{ onError, onEnded },
			{ EventSourceImpl: MockEventSource as unknown as typeof EventSource }
		);
		const src = MockEventSource.instances[0]!;

		src.emitEvent({
			type: 'run.status',
			status: 'failed',
			error: { code: 'llm_failure', message: 'overloaded' },
			sequence: 1,
			run_id: 'run-tail'
		});
		// Server closes the connection without sending run.ended first, OR
		// the native error fires racing against our run.ended handler.
		src.emitError();

		expect(onError).not.toHaveBeenCalled();
		expect(onEnded).toHaveBeenCalledTimes(1);
	});

	test('malformed JSON payload reports via onError, stream stays open', () => {
		const onError = vi.fn();
		const sub = subscribeRun(
			'run-malformed',
			{ onError },
			{ EventSourceImpl: MockEventSource as unknown as typeof EventSource }
		);
		const src = MockEventSource.instances[0]!;

		src.emitRaw('message.delta', 'not-json');

		expect(onError).toHaveBeenCalledTimes(1);
		expect(src.closed).toBe(false);
		expect(sub.state).toBe('idle');
	});

	test('unsubscribe closes the underlying EventSource', () => {
		const c = collectHandlers();
		const sub = subscribeRun('run-u', c.handlers, {
			EventSourceImpl: MockEventSource as unknown as typeof EventSource
		});
		sub.unsubscribe();
		expect(MockEventSource.instances[0]!.closed).toBe(true);
	});

	test('from_sequence query param is set when provided', () => {
		const c = collectHandlers();
		subscribeRun('run-r', c.handlers, {
			fromSequence: 7,
			EventSourceImpl: MockEventSource as unknown as typeof EventSource
		});
		expect(MockEventSource.instances[0]!.url).toBe('/runs/run-r/events?from_sequence=7');
	});
});
