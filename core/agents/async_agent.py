"""
Chapter 6: Async Agent Base Class

Provides AsyncAgent base that integrates with AgentEventBus.
Agents subscribe to event types and emit events in response,
achieving temporal and spatial decoupling.
"""

from __future__ import annotations

import uuid
from abc import ABC, abstractmethod
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from core.messaging.bus import AgentEventBus
    from core.messaging.events import Event


class AsyncAgent(ABC):
    """
    Base for asynchronously-communicating agents (Chapter 6).
    Agents communicate through the event bus only — never direct references.
    """

    def __init__(self, name: str, bus: "AgentEventBus"):
        self.agent_id = str(uuid.uuid4())
        self.name = name
        self._bus = bus

    def subscribe_to(self, event_type: str, handler: Callable | None = None) -> None:
        """Register a handler (defaults to self.handle) for an event type."""
        actual_handler = handler or self.handle
        self._bus.subscribe(event_type, actual_handler)

    async def emit(self, event: "Event") -> None:
        """Publish an event to the bus."""
        event.source_agent = self.name
        await self._bus.publish(event)

    @abstractmethod
    async def handle(self, event: "Event") -> None:
        """Primary event handler — override in concrete agents."""
        ...
