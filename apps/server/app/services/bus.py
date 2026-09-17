import asyncio


class SessionBus:
    def __init__(self):
        self._subs: dict[str, set[asyncio.Queue]] = {}

    def subscribe(self, session_id: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue()
        self._subs.setdefault(session_id, set()).add(q)
        return q

    def unsubscribe(self, session_id: str, q: asyncio.Queue) -> None:
        self._subs.get(session_id, set()).discard(q)

    async def publish(self, session_id: str, event: dict) -> None:
        for q in list(self._subs.get(session_id, ())):
            q.put_nowait(event)


bus = SessionBus()
