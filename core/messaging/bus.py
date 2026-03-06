"""
Chapter 6: Agent Event Bus

In-process pub/sub bus demonstrating temporal and spatial decoupling.
For production: Azure Service Bus (reliable) or Azure Event Hubs (high-throughput).

Features:
  - Idempotency: duplicate message IDs are silently skipped
  - Dead-letter queue: failed handlers are retried then dead-lettered
  - Wildcard subscribers: subscribe to "*" to receive all events
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Callable

from core.messaging.events import BaseMessage, Event


class DeadLetterQueue:
    def __init__(self):
        self._queue: list[tuple[BaseMessage, Exception]] = []

    def add(self, message: BaseMessage, error: Exception) -> None:
        self._queue.append((message, error))

    def drain(self) -> list[tuple[BaseMessage, Exception]]:
        items, self._queue = self._queue[:], []
        return items

    def __len__(self) -> int:
        return len(self._queue)


class AgentEventBus:
    def __init__(self, max_retries: int = 3):
        self._subscribers: dict[str, list[Callable]] = defaultdict(list)
        self._processed_ids: set[str] = set()
        self._dead_letter = DeadLetterQueue()
        self.max_retries = max_retries

    def subscribe(self, event_type: str, handler: Callable) -> None:
        self._subscribers[event_type].append(handler)

    async def publish(self, event: Event) -> None:
        if event.message_id in self._processed_ids:
            return  # Idempotency gate
        handlers = list(self._subscribers.get(event.event_type, []))
        handlers += list(self._subscribers.get("*", []))
        for handler in handlers:
            await self._deliver(event, handler)
        self._processed_ids.add(event.message_id)

    async def _deliver(self, event: Event, handler: Callable, attempt: int = 1) -> None:
        try:
            await handler(event)
        except Exception as exc:
            if attempt < self.max_retries:
                await asyncio.sleep(0.1 * attempt)
                await self._deliver(event, handler, attempt + 1)
            else:
                self._dead_letter.add(event, exc)

    @property
    def dead_letter_queue(self) -> DeadLetterQueue:
        return self._dead_letter

    def subscriber_count(self, event_type: str) -> int:
        return len(self._subscribers.get(event_type, []))
