// Run event stream consumer.
//
// Protocol (spec §5.4):
// - success: message.delta* → message.complete → run.status=succeeded
//            → [conversation.updated] → run.ended
// - failure: message.delta* → run.status=failed → run.ended
// - cancel:  message.delta* → run.status=cancelled → run.ended
//
// The stream closes on `run.ended` only. run.status alone is a state
// signal, not a terminator — closing on succeeded would drop the
// subsequent conversation.updated.

import type { MessageOut, RunEvent, RunStatus } from './types';

export type StreamState =
	| 'idle'
	| 'queued'
	| 'running'
	| 'terminalSucceeded'
	| 'terminalFailed'
	| 'terminalCancelled'
	| 'closed';

export type RunStreamHandlers = {
	onDelta?: (delta: string, event: Extract<RunEvent, { type: 'message.delta' }>) => void;
	onMessageComplete?: (message: MessageOut) => void;
	onStatus?: (status: RunStatus, error: { code: string; message: string } | undefined) => void;
	onConversationUpdated?: (conversationId: string, title: string) => void;
	onEnded?: () => void;
	onError?: (err: unknown) => void;
};

export type RunStreamSubscription = {
	/** Reactive getter — the chat view can read this as `$derived` or
	 *  `$state` wrapper to reflect state in UI without wiring every
	 *  transition by hand. */
	readonly state: StreamState;
	unsubscribe: () => void;
};

// Factory takes an EventSource constructor so tests can inject a mock.
type EventSourceCtor = new (url: string, init?: EventSourceInit) => EventSource;

export function subscribeRun(
	runId: string,
	handlers: RunStreamHandlers,
	opts: { fromSequence?: number; EventSourceImpl?: EventSourceCtor } = {}
): RunStreamSubscription {
	const params = new URLSearchParams();
	if (opts.fromSequence !== undefined) {
		params.set('from_sequence', String(opts.fromSequence));
	}
	const qs = params.toString();
	const url = `/runs/${encodeURIComponent(runId)}/events${qs ? `?${qs}` : ''}`;

	const Ctor = opts.EventSourceImpl ?? (globalThis.EventSource as EventSourceCtor);
	const source = new Ctor(url, { withCredentials: true });

	const sub: { state: StreamState } = { state: 'idle' };

	function close(final: StreamState): void {
		sub.state = final;
		source.close();
		handlers.onEnded?.();
	}

	source.addEventListener('message', (evt: MessageEvent<string>) => {
		let event: RunEvent;
		try {
			event = JSON.parse(evt.data) as RunEvent;
		} catch (err) {
			handlers.onError?.(err);
			return;
		}

		switch (event.type) {
			case 'message.delta':
				if (sub.state === 'idle' || sub.state === 'queued') sub.state = 'running';
				handlers.onDelta?.(event.delta, event);
				break;
			case 'message.complete':
				handlers.onMessageComplete?.(event.message);
				break;
			case 'conversation.updated':
				handlers.onConversationUpdated?.(event.conversation_id, event.title);
				break;
			case 'run.status':
				handlers.onStatus?.(event.status, event.error);
				if (event.status === 'queued') {
					if (sub.state === 'idle') sub.state = 'queued';
				} else if (event.status === 'running') {
					sub.state = 'running';
				} else if (event.status === 'succeeded') {
					sub.state = 'terminalSucceeded';
				} else if (event.status === 'failed') {
					sub.state = 'terminalFailed';
				} else if (event.status === 'cancelled') {
					sub.state = 'terminalCancelled';
				}
				break;
			case 'run.ended':
				close(
					sub.state === 'idle' || sub.state === 'queued' || sub.state === 'running'
						? 'closed'
						: sub.state
				);
				break;
		}
	});

	source.addEventListener('error', (err) => {
		// Browsers dispatch an error for transient reconnects too; we don't
		// auto-reconnect in v1 (spec §8). Always close and surface.
		handlers.onError?.(err);
		close('closed');
	});

	return {
		get state(): StreamState {
			return sub.state;
		},
		unsubscribe(): void {
			source.close();
		}
	};
}
