"""
Chapter 6: Message Types — Events, Commands, and Causal Tracing

Naming conventions:
  Events:   OrderPlaced, PaymentProcessed, AgentTaskCompleted (past participle)
  Commands: ProcessOrder, EvaluateResponse, SpawnSubagent (imperative verb)
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return str(uuid.uuid4())


@dataclass
class BaseMessage:
    message_id: str = field(default_factory=_new_id)
    timestamp: datetime = field(default_factory=_now)
    correlation_id: str = field(default_factory=_new_id)
    causation_id: str | None = None
    source_agent: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class Event(BaseMessage):
    """
    An immutable fact that something occurred.
    Producers MUST NOT modify events after emission.
    """
    event_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)

    def causes(self) -> "Event":
        """Factory: create a causally-related follow-up event."""
        return Event(causation_id=self.message_id, correlation_id=self.correlation_id)


@dataclass
class Command(BaseMessage):
    """
    A directive instructing an agent to perform an action.
    Commands may be rejected; Events may not.
    """
    command_type: str = ""
    payload: dict[str, Any] = field(default_factory=dict)
    reply_to: str | None = None


@dataclass
class EventContext:
    """
    Distributed tracing context (Chapter 6, §Causal Tracing).
    Propagated through every message for causal chain reconstruction.
    """
    trace_id: str = field(default_factory=_new_id)
    span_id: str = field(default_factory=_new_id)
    parent_span_id: str | None = None

    def new_child(self) -> "EventContext":
        return EventContext(trace_id=self.trace_id, parent_span_id=self.span_id)
