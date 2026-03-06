"""
Chapter 7: Cognitive Bounded Context

Formalizes an agent's domain as 4-tuple (S, T, K, V):
  S = Semantic Context   (what the agent understands)
  T = Tool Permissions   (what the agent is allowed to do)
  K = Knowledge Bases    (structured information it can access)
  V = Value Function     (restricted decision space)

An agent receiving a task outside its context MUST reject it or
route it through an Anti-Corruption Layer (ACL).
Domain leakage is the primary source of unpredictable multi-agent behavior.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import auto, Enum
from typing import Any, Callable


class AgentCapabilityLevel(Enum):
    READ = auto()
    WRITE = auto()
    EXECUTE = auto()
    ORCHESTRATE = auto()


@dataclass
class SemanticContext:
    domain: str
    keywords: list[str]
    ontology_refs: list[str] = field(default_factory=list)


@dataclass
class KnowledgeBase:
    name: str
    uri: str
    version: str = "1.0"
    schema: dict[str, Any] = field(default_factory=dict)


@dataclass
class CognitiveBoundedContext:
    """
    Formal specification of an agent's cognitive domain (Chapter 7).
    Agents MUST stay within their declared context.
    """
    name: str
    semantic_context: SemanticContext
    tool_permissions: list[AgentCapabilityLevel]
    knowledge_bases: list[KnowledgeBase]
    value_function: Callable[[Any], float] | None = None

    def is_in_scope(self, task_description: str) -> bool:
        task_lower = task_description.lower()
        return any(kw.lower() in task_lower for kw in self.semantic_context.keywords)

    def can_execute(self, required_level: AgentCapabilityLevel) -> bool:
        return required_level in self.tool_permissions

    def describe(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "domain": self.semantic_context.domain,
            "keywords": self.semantic_context.keywords,
            "permissions": [p.name for p in self.tool_permissions],
            "knowledge_bases": [kb.name for kb in self.knowledge_bases],
        }
