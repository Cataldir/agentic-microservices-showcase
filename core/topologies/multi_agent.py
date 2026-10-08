"""
Chapter 3: Multi-Agent Topologies

  Star:  Centralized hub + leaves. Simple, single point of failure.
  Mesh:  Every agent can message every other. Fault-tolerant, O(n^2).
  Ring:  Sequential pipeline. Natural for staged processing.
  Tree:  Hierarchical decomposition. Recursive task breakdown.
"""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, Callable, Awaitable


@dataclass
class AgentNode:
    node_id: str
    name: str
    process: Callable[[Any], Awaitable[Any]] | None = None


class TopologyBase(ABC):
    def __init__(self):
        self._nodes: dict[str, AgentNode] = {}

    def add_node(self, node: AgentNode) -> None:
        self._nodes[node.node_id] = node

    def node_count(self) -> int:
        return len(self._nodes)

    @abstractmethod
    async def route(self, message: Any, sender_id: str) -> list[Any]: ...


class StarTopology(TopologyBase):
    """
    Hub fans out to all leaves. Simple orchestration, single bottleneck.
    """
    def __init__(self, hub_id: str):
        super().__init__()
        self.hub_id = hub_id

    async def route(self, message: Any, sender_id: str) -> list[Any]:
        hub = self._nodes.get(self.hub_id)
        if not hub or not hub.process:
            return []
        hub_result = await hub.process(message)
        leaves = [n for nid, n in self._nodes.items() if nid != self.hub_id and n.process]
        return list(await asyncio.gather(*[n.process(hub_result) for n in leaves]))


class MeshTopology(TopologyBase):
    """
    Explicit directed edges between nodes. Max fault tolerance, O(n^2) connections.
    """
    def __init__(self):
        super().__init__()
        self._edges: dict[str, list[str]] = {}

    def add_edge(self, from_id: str, to_id: str) -> None:
        self._edges.setdefault(from_id, []).append(to_id)

    async def route(self, message: Any, sender_id: str) -> list[Any]:
        results = []
        for tid in self._edges.get(sender_id, []):
            node = self._nodes.get(tid)
            if node and node.process:
                results.append(await node.process(message))
        return results


class RingTopology(TopologyBase):
    """
    Work passes through nodes in a fixed sequence. Single broken stage halts pipeline.
    """
    def __init__(self):
        super().__init__()
        self._order: list[str] = []

    def set_order(self, ordered_ids: list[str]) -> None:
        self._order = ordered_ids

    async def route(self, message: Any, sender_id: str) -> list[Any]:
        result, trace = message, []
        for nid in self._order:
            node = self._nodes.get(nid)
            if node and node.process:
                result = await node.process(result)
                trace.append(result)
        return trace


class TreeTopology(TopologyBase):
    """
    Root orchestrator delegates to child sub-teams recursively.
    """
    def __init__(self, root_id: str):
        super().__init__()
        self.root_id = root_id
        self._children: dict[str, list[str]] = {}

    def add_children(self, parent_id: str, child_ids: list[str]) -> None:
        self._children[parent_id] = child_ids

    async def route(self, message: Any, sender_id: str) -> list[Any]:
        return await self._dispatch(self.root_id, message)

    async def _dispatch(self, node_id: str, message: Any) -> list[Any]:
        node = self._nodes.get(node_id)
        result = await node.process(message) if (node and node.process) else message
        children = self._children.get(node_id, [])
        if not children:
            return [result]
        subtree = await asyncio.gather(*[self._dispatch(c, result) for c in children])
        return [item for sub in subtree for item in sub]
