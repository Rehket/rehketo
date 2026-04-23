// Run event stream consumer.
//
// Protocol (spec §5.4):
// - success: message.delta* → message.complete → run.status=succeeded
//            → [conversation.updated] → run.ended
// - failure: message.delta* → run.status=failed → run.ended
// - cancel:  message.delta* → run.status=cancelled → run.ended
//
// The backend emits SSE frames with an `event:` field set to the event
// type (e.g. `event: message.delta`). Browsers dispatch those as custom
// DOM events of that name — NOT as generic `message` events — so we must
// addEventListener for each type. A single `addEventListener('message', …)`
// would miss every frame.
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

type TerminalState = 'terminalSucceeded' | 'terminalFailed' | 'terminalCancelled';

function isTerminal(state: StreamState): state is TerminalState {
	return (
		state === 'terminalSucceeded' || state === 'terminalFailed' || state === 'terminalCancelled'
	);
}

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
	let closed = false;

	function close(final: StreamState): void {
		if (closed) return;
		closed = true;
		sub.state = final;
		source.close();
		handlers.onEnded?.();
	}

	function parseOrError<E extends RunEvent>(evt: Event): E | null {
		const data = (evt as MessageEvent<string>).data;
		try {
			return JSON.parse(data) as E;
		} catch (err) {
			handlers.onError?.(err);
			return null;
		}
	}

	source.addEventListener('message.delta', (evt) => {
		const event = parseOrError<Extract<RunEvent, { type: 'message.delta' }>>(evt);
		if (!event) return;
		if (sub.state === 'idle' || sub.state === 'queued') sub.state = 'running';
		handlers.onDelta?.(event.delta, event);
	});

	source.addEventListener('message.complete', (evt) => {
		const event = parseOrError<Extract<RunEvent, { type: 'message.complete' }>>(evt);
		if (!event) return;
		handlers.onMessageComplete?.(event.message);
	});

	source.addEventListener('conversation.updated', (evt) => {
		const event = parseOrError<Extract<RunEvent, { type: 'conversation.updated' }>>(evt);
		if (!event) return;
		handlers.onConversationUpdated?.(event.conversation_id, event.title);
	});

	source.addEventListener('run.status', (evt) => {
		const event = parseOrError<Extract<RunEvent, { type: 'run.status' }>>(evt);
		if (!event) return;
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
	});

	source.addEventListener('run.ended', () => {
		close(isTerminal(sub.state) ? sub.state : 'closed');
	});

	source.addEventListener('error', (err) => {
		// Browsers dispatch an error when the server closes the HTTP stream
		// or the connection drops. If we've already received a terminal
		// run.status, this is the normal EOF tail — treat it as run.ended
		// (close quietly, no disconnect banner). Only surface onError when
		// the stream genuinely broke mid-run.
		if (closed) return;
		if (isTerminal(sub.state)) {
			close(sub.state);
			return;
		}
		handlers.onError?.(err);
		close('closed');
	});

	return {
		get state(): StreamState {
			return sub.state;
		},
		unsubscribe(): void {
			if (closed) return;
			closed = true;
			source.close();
		}
	};
}
