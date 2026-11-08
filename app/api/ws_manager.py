"""WebSocket fan-out for count events and detection frames."""
from __future__ import annotations

import asyncio
import json
import logging
from collections import defaultdict, deque
from typing import Any, Deque, Dict, Set

log = logging.getLogger(__name__)


class Broadcaster:
    """Thread safe broadcaster: the engine (threads) publishes, FastAPI (loop) consumes."""

    def __init__(self, history: int = 200):
        self._subscribers: Dict[str, Set[asyncio.Queue]] = defaultdict(set)
        self._pending: Deque[tuple] = deque(maxlen=history)
        self._loop: asyncio.AbstractEventLoop = None  # type: ignore[assignment]
        self._lock = asyncio.Lock()

    def bind_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop
        pending = list(self._pending)
        self._pending.clear()
        for topic, payload in pending:
            self._deliver(topic, payload)

    def _deliver(self, topic: str, payload: Any) -> None:
        for queue in list(self._subscribers.get(topic, ())):
            try:
                queue.put_nowait(payload)
            except asyncio.QueueFull:
                pass

    def publish_threadsafe(self, topic: str, payload: Any) -> None:
        """May be called from any thread."""
        loop = self._loop
        if loop is None or loop.is_closed():
            self._pending.append((topic, payload))
            return
        try:
            loop.call_soon_threadsafe(self._deliver, topic, payload)
        except RuntimeError:  # pragma: no cover - loop shutting down
            self._pending.append((topic, payload))

    async def subscribe(self, topic: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        async with self._lock:
            self._subscribers[topic].add(queue)
        return queue

    async def unsubscribe(self, topic: str, queue: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers[topic].discard(queue)
            if not self._subscribers[topic]:
                self._subscribers.pop(topic, None)

    @property
    def subscriber_count(self) -> int:
        return sum(len(queues) for queues in self._subscribers.values())


_broadcaster = Broadcaster()


def get_broadcaster() -> Broadcaster:
    return _broadcaster
