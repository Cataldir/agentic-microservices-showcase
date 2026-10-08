@dataclass
class IsolatedAgentContext:
    agent_id: str
    system_prompt: str
    available_tools: list[str]
    memory_namespace: str
    token_budget: int
    secrets_scope: str
    _conversation_history: list[dict] = field(
        default_factory=list)
    _working_memory: dict[str, Any] = field(
        default_factory=dict)

    def add_to_history(self, role: str, content: str
                       ) -> None:
        self._conversation_history.append({
            "role": role, "content": content,
            "agent_id": self.agent_id})

    def get_context_for_llm(self) -> list[dict]:
        return [
            {"role": "system",
             "content": self.system_prompt},
            *self._conversation_history[
                -self._max_history_items():]]

    def _max_history_items(self) -> int:
        return min(20, self.token_budget // 500)
