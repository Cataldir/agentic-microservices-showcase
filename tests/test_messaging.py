"""
Tests for AgentEventBus, Event, DeadLetterQueue.
"""
import pytest
from core.messaging.events import Event
from core.messaging.bus import AgentEventBus


@pytest.mark.asyncio
async def test_event_delivered():
    bus = AgentEventBus()
    received = []
    async def handler(event): received.append(event)
    bus.subscribe("OrderPlaced", handler)
    await bus.publish(Event(event_type="OrderPlaced", payload={"order_id": "ORD-1"}))
    assert len(received) == 1
    assert received[0].payload["order_id"] == "ORD-1"


@pytest.mark.asyncio
async def test_idempotency_skips_duplicate():
    bus = AgentEventBus()
    received = []
    async def handler(event): received.append(event)
    bus.subscribe("Test", handler)
    event = Event(event_type="Test")
    await bus.publish(event)
    await bus.publish(event)  # duplicate
    assert len(received) == 1


@pytest.mark.asyncio
async def test_failed_handler_dead_lettered():
    bus = AgentEventBus(max_retries=1)
    async def bad_handler(event): raise ValueError("crash")
    bus.subscribe("Test", bad_handler)
    await bus.publish(Event(event_type="Test"))
    assert len(bus.dead_letter_queue) == 1
