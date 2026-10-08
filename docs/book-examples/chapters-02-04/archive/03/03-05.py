from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Callable, Any
import asyncio

@dataclass
class AgentMessage:
    """Mensagem trocada entre agentes na topologia."""
    sender_id: str
    recipient_id: str
    content: Any
    hop_count: int = 0

class TopologyBase(ABC):
    """Classe base para topologias multiagentes."""

    def __init__(self):
        self.agents: dict[str, Callable] = {}
        self.connections: dict[str, set[str]] = {}

    def register_agent(self, agent_id: str, handler: Callable) -> None:
        """Registra um agente e seu handler de mensagens."""
        self.agents[agent_id] = handler
        if agent_id not in self.connections:
            self.connections[agent_id] = set()

    @abstractmethod
    def connect(self, agent_a: str, agent_b: str) -> None:
        """Estabelece conexão entre dois agentes."""
        ...

    @abstractmethod
    async def route_message(self, message: AgentMessage) -> None:
        """Roteia mensagem do sender ao recipient."""
        ...

    def get_neighbors(self, agent_id: str) -> set[str]:
        """Retorna vizinhos diretos de um agente."""
        return self.connections.get(agent_id, set())

class StarTopology(TopologyBase):
    """Topologia em estrela com um hub central."""

    def __init__(self, hub_id: str):
        super().__init__()
        self.hub_id = hub_id

    def connect(self, agent_a: str, agent_b: str) -> None:
        """Na estrela, todos conectam apenas ao hub."""
        if agent_a == self.hub_id:
            self.connections.setdefault(agent_a, set()).add(agent_b)
            self.connections.setdefault(agent_b, set()).add(agent_a)
        elif agent_b == self.hub_id:
            self.connections.setdefault(agent_a, set()).add(agent_b)
            self.connections.setdefault(agent_b, set()).add(agent_a)
        else:
            # Conexões não hub são ignoradas na topologia estrela
            raise ValueError(
                f"Na topologia estrela, conexões devem incluir o hub '{self.hub_id}'"
            )

    async def route_message(self, message: AgentMessage) -> None:
        """Roteia via hub central."""
        if message.sender_id == self.hub_id:
            # Hub enviando diretamente ao destinatário
            if message.recipient_id in self.agents:
                await self.agents[message.recipient_id](message)
        else:
            # Mensagem passa pelo hub primeiro
            hub_message = AgentMessage(
                sender_id=message.sender_id,
                recipient_id=message.recipient_id,
                content=message.content,
                hop_count=message.hop_count + 1
            )
            # Hub decide se encaminha
            if self.hub_id in self.agents:
                await self.agents[self.hub_id](hub_message)

class MeshTopology(TopologyBase):
    """Topologia em malha totalmente conectada."""

    def connect(self, agent_a: str, agent_b: str) -> None:
        """Conexão bidirecional direta."""
        self.connections.setdefault(agent_a, set()).add(agent_b)
        self.connections.setdefault(agent_b, set()).add(agent_a)

    def fully_connect(self) -> None:
        """Conecta todos os agentes registrados entre si."""
        agent_ids = list(self.agents.keys())
        for i, agent_a in enumerate(agent_ids):
            for agent_b in agent_ids[i + 1:]:
                self.connect(agent_a, agent_b)

    async def route_message(self, message: AgentMessage) -> None:
        """Entrega direta ao destinatário (1 hop)."""
        if message.recipient_id in self.agents:
            await self.agents[message.recipient_id](message)

class RingTopology(TopologyBase):
    """Topologia em anel com passagem de token."""

    def __init__(self, agent_order: list[str]):
        super().__init__()
        self.ring_order = agent_order
        self._setup_ring()

    def _setup_ring(self) -> None:
        """Configura conexões do anel baseado na ordem."""
        n = len(self.ring_order)
        for i, agent_id in enumerate(self.ring_order):
            left_neighbor = self.ring_order[(i - 1) % n]
            right_neighbor = self.ring_order[(i + 1) % n]
            self.connections[agent_id] = {left_neighbor, right_neighbor}

    def connect(self, agent_a: str, agent_b: str) -> None:
        """No anel, conexões são definidas pela ordem
        inicial."""
        raise NotImplementedError(
            "Conexões no anel são definidas pela ordem no construtor"
        )

    async def route_message(
        self,
        message: AgentMessage,
        direction: str = "clockwise"
    ) -> None:
        """Roteia mensagem pelo anel até o destinatário."""
        current_idx = self.ring_order.index(message.sender_id)
        max_hops = len(self.ring_order)
        while message.hop_count < max_hops:
            # Próximo agente na direção escolhida
            if direction == "clockwise":
                current_idx = (current_idx + 1) % len(self.ring_order)
            else:
                current_idx = (current_idx - 1) % len(self.ring_order)
            next_agent = self.ring_order[current_idx]
            message.hop_count += 1
            if next_agent == message.recipient_id:
                # Encontrou o destinatário
                await self.agents[next_agent](message)
                return
            # Passa adiante (agente intermediário pode processar)
            if next_agent in self.agents:
                await self.agents[next_agent](message)

@dataclass
class TreeNode:
    """Nó na topologia em árvore."""
    agent_id: str
    parent: str | None = None
    children: set[str] = field(default_factory=set)

class TreeTopology(TopologyBase):
    """Topologia em árvore hierárquica."""

    def __init__(self, root_id: str):
        super().__init__()
        self.root_id = root_id
        self.nodes: dict[str, TreeNode] = {root_id: TreeNode(root_id)}

    def connect(self, parent_id: str, child_id: str) -> None:
        """Estabelece relação pai-filho na árvore."""
        if parent_id not in self.nodes:
            raise ValueError(f"Pai '{parent_id}' não existe na árvore")
        self.nodes[child_id] = TreeNode(child_id, parent=parent_id)
        self.nodes[parent_id].children.add(child_id)
        # Atualiza conexões bidirecionais
        self.connections.setdefault(parent_id, set()).add(child_id)
        self.connections.setdefault(child_id, set()).add(parent_id)

    def _find_path(self, from_id: str, to_id: str) -> list[str]:
        """Encontra caminho na árvore entre dois nós."""
        # Sobe até a raiz coletando ancestrais de 'from'
        from_ancestors = []
        current = from_id
        while current:
            from_ancestors.append(current)
            current = self.nodes[current].parent
        # Sobe até a raiz coletando ancestrais de 'to'
        to_ancestors = []
        current = to_id
        while current:
            to_ancestors.append(current)
            current = self.nodes[current].parent
        # Encontra ancestral comum mais baixo (LCA)
        from_set = set(from_ancestors)
        lca = None
        for ancestor in to_ancestors:
            if ancestor in from_set:
                lca = ancestor
                break
        # Constrói caminho: from -> LCA -> to
        path_up = []
        current = from_id
        while current != lca:
            path_up.append(current)
            current = self.nodes[current].parent
        path_down = []
        current = to_id
        while current != lca:
            path_down.append(current)
            current = self.nodes[current].parent
        return path_up + [lca] + list(reversed(path_down))

    async def route_message(self, message: AgentMessage) -> None:
        """Roteia pela hierarquia da árvore."""
        path = self._find_path(message.sender_id, message.recipient_id)
        for node_id in path[1:]:  # Pula o sender
            message.hop_count += 1
            if node_id == message.recipient_id:
                await self.agents[node_id](message)
                return
            # Nós intermediários podem observar/filtrar
            if node_id in self.agents:
                await self.agents[node_id](message)
