from dataclasses import dataclass, field
from typing import Any

@dataclass
class IsolatedAgentContext:
    """
    Contexto isolado para um agente.
    Equivalente ao container runtime de um microsserviço.
    """
    agent_id: str
    system_prompt: str
    available_tools: list[str]
    memory_namespace: str
    token_budget: int
    secrets_scope: str  # Quais secrets o agente pode acessar

    # Estado interno isolado
    _conversation_history: list[dict] = field(default_factory=list)
    _working_memory: dict[str, Any] = field(default_factory=dict)

    def add_to_history(self, role: str, content: str) -> None:
        """Adiciona mensagem ao histórico isolado deste agente."""
        self._conversation_history.append({
            "role": role,
            "content": content,
            "agent_id": self.agent_id  # Rastreabilidade
        })

    def get_context_for_llm(self) -> list[dict]:
        """
        Retorna contexto formatado para o LLM.
        Inclui apenas informações dentro do escopo deste agente.
        """
        return [
            {"role": "system", "content": self.system_prompt},
            *self._conversation_history[-self._max_history_items():]
        ]

    def _max_history_items(self) -> int:
        """Calcula quantos itens de histórico cabem no token budget."""
        # Simplificado - na prática, contaria tokens
        return min(20, self.token_budget // 500)
