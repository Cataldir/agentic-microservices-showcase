from dataclasses import dataclass
from typing import Any
import numpy as np

@dataclass
class AgentProfile:
    """
    Perfil completo de um agente no registry.
    Inclui informações para descoberta semântica.
    """
    agent_id: str
    name: str
    endpoint: str
    domain: str
    capabilities: list[str]
    capability_embeddings: np.ndarray  # Vetores para busca semântica
    avg_latency_ms: float
    success_rate: float
    token_cost_per_request: int
    is_healthy: bool
    metadata: dict[str, Any]

class AgentRegistry:
    """
    Registry de agentes com descoberta semântica.
    Combina service discovery tradicional com matching por competência.
    """

    def __init__(self, embedding_model):
        self._agents: dict[str, AgentProfile] = {}
        self._embedding_model = embedding_model

    def register(self, profile: AgentProfile) -> None:
        """Registra ou atualiza um agente no registry."""
        self._agents[profile.agent_id] = profile

    def deregister(self, agent_id: str) -> None:
        """Remove um agente do registry."""
        self._agents.pop(agent_id, None)

    def discover_by_capability(
        self,
        task_description: str,
        min_confidence: float = 0.7,
        max_latency_ms: float | None = None
    ) -> list[tuple[AgentProfile, float]]:
        """
        Descobre agentes capazes de executar uma tarefa.

        Retorna lista de (perfil, confiança) ordenada por relevância.
        Combina similaridade semântica com filtros de QoS.
        """
        task_embedding = self._embedding_model.encode(task_description)
        candidates = []

        for agent in self._agents.values():
            if not agent.is_healthy:
                continue

            if max_latency_ms and agent.avg_latency_ms > max_latency_ms:
                continue

            # Calcula similaridade com capacidades do agente
            similarity = self._compute_similarity(
                task_embedding,
                agent.capability_embeddings
            )

            if similarity >= min_confidence:
                candidates.append((agent, similarity))

        # Ordena por similaridade (maior primeiro)
        return sorted(candidates, key=lambda x: x[1], reverse=True)

    def _compute_similarity(
        self,
        task_emb: np.ndarray,
        capability_embs: np.ndarray
    ) -> float:
        """Calcula máxima similaridade cosseno entre tarefa e capacidades."""
        # Similaridade cosseno
        similarities = np.dot(capability_embs, task_emb) / (
            np.linalg.norm(capability_embs, axis=1) * np.linalg.norm(task_emb)
        )
        return float(np.max(similarities))

    def update_health(self, agent_id: str, is_healthy: bool) -> None:
        """Atualiza estado de saúde de um agente."""
        if agent_id in self._agents:
            self._agents[agent_id].is_healthy = is_healthy

    def update_metrics(
        self,
        agent_id: str,
        latency_ms: float,
        success: bool
    ) -> None:
        """
        Atualiza métricas de performance com média móvel exponencial.
        Permite que o registry reflita performance real.
        """
        if agent_id not in self._agents:
            return

        agent = self._agents[agent_id]
        alpha = 0.1  # Fator de suavização

        # Atualiza latência média
        agent.avg_latency_ms = (
            alpha * latency_ms + (1 - alpha) * agent.avg_latency_ms
        )

        # Atualiza taxa de sucesso
        success_val = 1.0 if success else 0.0
        agent.success_rate = (
            alpha * success_val + (1 - alpha) * agent.success_rate
        )
