export interface SseHandlers {
  onMessage: (ev: { role: string; blocks: unknown[] }) => void;
  onDone: (ev: { duration_ms?: number; cost?: number }) => void;
  onError: (ev: { message: string }) => void;
}

export function connectSessionEvents(sid: string, handlers: SseHandlers): () => void {
  const es = new EventSource(`/api/sessions/${sid}/events`);
  es.addEventListener('agent_message', (e) =>
    handlers.onMessage(JSON.parse((e as MessageEvent).data))
  );
  es.addEventListener('agent_done', (e) => {
    handlers.onDone(JSON.parse((e as MessageEvent).data));
  });
  es.addEventListener('agent_error', (e) =>
    handlers.onError(JSON.parse((e as MessageEvent).data))
  );
  return () => es.close();
}
