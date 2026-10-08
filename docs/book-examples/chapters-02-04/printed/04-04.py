def discover_by_capability(self, task_description: str,
    min_confidence: float = 0.7,
    max_latency_ms: float | None = None
    ) -> list[tuple[AgentProfile, float]]:
    task_embedding = self._embedding_model.encode(
        task_description)
    candidates = []
    for agent in self._agents.values():
        if not agent.is_healthy:
            continue
        if (max_latency_ms
                and agent.avg_latency_ms > max_latency_ms):
            continue
        similarity = self._compute_similarity(
            task_embedding, agent.capability_embeddings)
        if similarity >= min_confidence:
            candidates.append((agent, similarity))
    return sorted(candidates, key=lambda x: x[1],
                  reverse=True)

def _compute_similarity(self, task_emb: np.ndarray,
    capability_embs: np.ndarray) -> float:
    similarities = np.dot(capability_embs, task_emb) / (
        np.linalg.norm(capability_embs, axis=1)
        * np.linalg.norm(task_emb))
    return float(np.max(similarities))
