"""
Chapter 2: Hot / Warm / Cold Memory Hierarchy

  HotMemory:  context window — fast access, FIFO eviction, limited capacity.
  WarmMemory: RAG-style dynamic retrieval via embedding similarity.
  ColdMemory: persistent key-value store for long-term knowledge.
              Production: Azure Cosmos DB, Azure AI Search, or Blob Storage.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class MemoryEntry:
    text: str
    metadata: dict[str, Any] = field(default_factory=dict)
    embedding: list[float] | None = None


class HotMemory:
    """
    Context window buffer (Chapter 2, §Hot Memory).
    FIFO truncation when token budget exceeded.
    """

    def __init__(self, max_tokens: int = 4_096, avg_chars_per_token: int = 4):
        self._max_chars = max_tokens * avg_chars_per_token
        self._entries: deque[MemoryEntry] = deque()

    def add(self, entry: MemoryEntry) -> None:
        self._entries.append(entry)
        while self._current_size() > self._max_chars and self._entries:
            self._entries.popleft()

    def get_context(self) -> list[str]:
        return [e.text for e in self._entries]

    def clear(self) -> None:
        self._entries.clear()

    def _current_size(self) -> int:
        return sum(len(e.text) for e in self._entries)

    def __len__(self) -> int:
        return len(self._entries)


class WarmMemory:
    """RAG-style retrieval memory (Chapter 2, §Warm Memory)."""

    def __init__(self, top_k: int = 5, embed_fn: Callable[[str], list[float]] | None = None):
        self._store: list[MemoryEntry] = []
        self.top_k = top_k
        self._embed = embed_fn or self._stub_embed

    @staticmethod
    def _stub_embed(text: str) -> list[float]:
        import hashlib
        digest = hashlib.sha256(text.encode()).digest()
        return [b / 255.0 for b in digest]

    @staticmethod
    def _cosine(a: list[float], b: list[float]) -> float:
        dot = sum(x * y for x, y in zip(a, b))
        na = math.sqrt(sum(x * x for x in a))
        nb = math.sqrt(sum(y * y for y in b))
        return dot / (na * nb + 1e-10)

    def index(self, entry: MemoryEntry) -> None:
        if entry.embedding is None:
            entry.embedding = self._embed(entry.text)
        self._store.append(entry)

    def retrieve(self, query: str, top_k: int | None = None) -> list[MemoryEntry]:
        if not self._store:
            return []
        k = top_k or self.top_k
        q_vec = self._embed(query)
        return sorted(
            self._store,
            key=lambda e: self._cosine(q_vec, e.embedding or []),
            reverse=True,
        )[:k]

    def __len__(self) -> int:
        return len(self._store)


class ColdMemory:
    """Persistent knowledge base (Chapter 2, §Cold Memory)."""

    def __init__(self):
        self._store: dict[str, MemoryEntry] = {}

    def write(self, key: str, entry: MemoryEntry) -> None:
        self._store[key] = entry

    def read(self, key: str) -> MemoryEntry | None:
        return self._store.get(key)

    def delete(self, key: str) -> None:
        self._store.pop(key, None)

    def keys(self) -> list[str]:
        return list(self._store.keys())

    def search_by_tag(self, tag: str) -> list[MemoryEntry]:
        return [e for e in self._store.values() if tag in e.metadata.get("tags", [])]

    def __len__(self) -> int:
        return len(self._store)
