from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import AsyncIterator, DefaultDict


class EventBus:
    """Simple in-memory publish/subscribe bus for websocket updates."""

    def __init__(self) -> None:
        self._subscribers: DefaultDict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, channel: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue()
        self._subscribers[channel].add(queue)
        return queue

    def unsubscribe(self, channel: str, queue: asyncio.Queue) -> None:
        queues = self._subscribers.get(channel)
        if not queues:
            return
        queues.discard(queue)
        if not queues:
            self._subscribers.pop(channel, None)

    async def publish(self, channel: str, payload: dict) -> None:
        queues = list(self._subscribers.get(channel, set()))
        for queue in queues:
            await queue.put(payload)

    async def listen(self, channel: str) -> AsyncIterator[dict]:
        queue = self.subscribe(channel)
        try:
            while True:
                payload = await queue.get()
                yield payload
        finally:
            self.unsubscribe(channel, queue)


event_bus = EventBus()
