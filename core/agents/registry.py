"""
Chapter 4: Agent Registry with Semantic Discovery

Agents register their CognitiveDomain; the registry finds the best
match for a task using embedding-based semantic similarity.

Production: replace _stub_embed() with Azure OpenAI:
  model: text-embedding-3-small or text-embedding-3-large
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class AgentProfile:
    agent_id: str
    name: str
    description: str
    capabilities: list[str]
    endpoint: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


def _cosine_similarity(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(y * y for y in b))
    return dot / (norm_a * norm_b + 1e-10)


class AgentRegistry:
    """In-process registry with embedding-based semantic discovery."""

    def __init__(self, embed_fn: Callable[[str], list[float]] | None = None):
        self._profiles: dict[str, AgentProfile] = {}
        self._embeddings: dict[str, list[float]] = {}
        self._embed = embed_fn or self._stub_embed

    @staticmethod
    def _stub_embed(text: str) -> list[float]:
        import hashlib
        digest = hashlib.sha256(text.encode()).digest()
        return [b / 255.0 for b in digest]

    def register(self, profile: AgentProfile) -> None:
        self._profiles[profile.agent_id] = profile
        text = f"{profile.name} {profile.description} {' '.join(profile.capabilities)}"
        self._embeddings[profile.agent_id] = self._embed(text)

    def find_best_match(self, task: str) -> AgentProfile | None:
        if not self._profiles:
            return None
        task_vec = self._embed(task)
        scores = {aid: _cosine_similarity(task_vec, vec) for aid, vec in self._embeddings.items()}
        return self._profiles[max(scores, key=scores.__getitem__)]

    def list_agents(self) -> list[AgentProfile]:
        return list(self._profiles.values())

    def deregister(self, agent_id: str) -> None:
        self._profiles.pop(agent_id, None)
        self._embeddings.pop(agent_id, None)
