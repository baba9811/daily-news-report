/**
 * EventSource wrapper for `/api/debate/{id}/stream`.
 *
 * Subscribes to the named SSE events emitted by the backend debate
 * orchestrator and forwards them to the caller. Returns an unsubscribe
 * function that closes the underlying EventSource.
 */

export type DebateEvent = {
  kind: string;
  data: unknown;
};

const DEBATE_EVENT_KINDS = [
  "analyst_start",
  "analyst_done",
  "round_start",
  "round_end",
  "judge_done",
  "phase_change",
  "debate_done",
  "error",
] as const;

export function subscribeDebate(
  debateId: string,
  onEvent: (event: DebateEvent) => void,
  onError?: (err: Event) => void
): () => void {
  const url = `/api/debate/${encodeURIComponent(debateId)}/stream`;
  const es = new EventSource(url);

  const makeHandler = (kind: string) => (msg: MessageEvent) => {
    let data: unknown = null;
    try {
      data = JSON.parse(msg.data as string);
    } catch {
      data = msg.data;
    }
    onEvent({ kind, data });
  };

  for (const kind of DEBATE_EVENT_KINDS) {
    es.addEventListener(kind, makeHandler(kind));
  }

  es.onerror = onError ?? (() => {});

  return () => {
    es.close();
  };
}
