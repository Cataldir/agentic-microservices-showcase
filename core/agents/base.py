"""
Chapter 4: Well-Defined Agent Protocol

Implements the PEAS framework (Performance, Environment, Actuators, Sensors)
and the WellDefinedAgent protocol with CognitiveDomain, AgentCapability,
and ResourceConstraints.

Key principle: every agent must declare *what it knows*, *what it can do*,
and *what it is forbidden from doing* before receiving any task.
"""

from __future__ import annotations

import uuid
from abc import abstractmethod
from dataclasses import dataclass, field
from enum import auto, Enum
from typing import Any, Protocol, runtime_checkable


class AgentCapability(Enum):
    """Fine-grained capability permissions (Chapter 4, §Isolation)."""
    READ_DATA = auto()
    WRITE_DATA = auto()
    CALL_EXTERNAL_API = auto()
    EMIT_EVENTS = auto()
    CONSUME_EVENTS = auto()
    SPAWN_SUBAGENTS = auto()
    MANAGE_MEMORY = auto()
    EVALUATE_OUTPUT = auto()


@dataclass
class CognitiveDomain:
    """
    What an agent knows and can perceive — the 'E' (Environment) in PEAS.
    """
    name: str
    description: str
    knowledge_sources: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)


@dataclass
class ResourceConstraints:
    """
    Hard resource boundaries (Chapter 4, §Constraints).
    Prevents an agent from consuming disproportionate resources.
    """
    max_tokens_per_call: int = 4_096
    max_calls_per_minute: int = 60
    max_concurrent_executions: int = 5
    token_budget_per_session: int = 100_000


@runtime_checkable
class WellDefinedAgent(Protocol):
    """
    Protocol contract for all agents (Chapter 4, §SRP).
    Every agent must declare its domain, capabilities, and constraints.
    """
    agent_id: str
    cognitive_domain: CognitiveDomain
    capabilities: frozenset[AgentCapability]
    constraints: ResourceConstraints

    @abstractmethod
    async def execute(self, task: str, context: dict[str, Any]) -> dict[str, Any]: ...

    @abstractmethod
    async def validate_scope(self, task: str) -> bool: ...


class BaseAgent:
    """
    Concrete base that satisfies WellDefinedAgent.
    Subclass and override execute() with domain-specific logic.
    """

    def __init__(
        self,
        cognitive_domain: CognitiveDomain,
        capabilities: frozenset[AgentCapability] | None = None,
        constraints: ResourceConstraints | None = None,
    ):
        self.agent_id = str(uuid.uuid4())
        self.cognitive_domain = cognitive_domain
        self.capabilities = capabilities or frozenset()
        self.constraints = constraints or ResourceConstraints()

    async def validate_scope(self, task: str) -> bool:
        task_lower = task.lower()
        return any(kw.lower() in task_lower for kw in self.cognitive_domain.tools)

    async def execute(self, task: str, context: dict[str, Any]) -> dict[str, Any]:
        raise NotImplementedError(f"{self.__class__.__name__} must implement execute()")
