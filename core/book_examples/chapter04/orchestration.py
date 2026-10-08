from dataclasses import dataclass
from typing import Any, Protocol
from enum import Enum
import asyncio

from .registry import AgentRegistry

class TaskStatus(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    COMPENSATED = "compensated"

@dataclass
class OrchestrationStep:
    """Um passo no plano de orquestração."""
    step_id: str
    agent_id: str
    action: str
    input_mapping: dict[str, str]  # Como mapear outputs anteriores
    compensation_action: str | None = None
    status: TaskStatus = TaskStatus.PENDING
    result: Any = None
    error: str | None = None

class Agent(Protocol):
    """Interface que agentes devem implementar."""

    async def execute(self, action: str, inputs: dict) -> dict:
        ...

    async def compensate(self, action: str, original_inputs: dict) -> None:
        ...

class AgentOrchestrator:
    """
    Orquestrador de agentes com suporte a Saga pattern.

    Responsabilidades:
    - Planejamento dinâmico de sequência de ações
    - Execução coordenada de múltiplos agentes
    - Compensação em caso de falhas
    - Agregação de resultados
    """

    def __init__(
        self,
        registry: AgentRegistry,
        planner_agent: Agent
    ):
        self.registry = registry
        self.planner = planner_agent
        self._execution_history: list[OrchestrationStep] = []

    async def execute_task(self, task: str, context: dict) -> dict:
        """
        Executa uma tarefa complexa orquestrando múltiplos agentes.

        1. Usa agente planejador para decompor tarefa
        2. Executa passos sequencialmente
        3. Compensa se necessário
        """
        # Fase 1: Planejamento
        plan = await self._create_plan(task, context)

        # Fase 2: Execução
        results = {}
        for step in plan:
            try:
                step.status = TaskStatus.IN_PROGRESS
                self._execution_history.append(step)

                # Resolve inputs baseado em resultados anteriores
                inputs = self._resolve_inputs(step.input_mapping, results)

                # Descobre e executa agente
                agent = await self._get_agent(step.agent_id)
                result = await agent.execute(step.action, inputs)

                step.result = result
                step.status = TaskStatus.COMPLETED
                results[step.step_id] = result

            except Exception as e:
                step.error = str(e)
                step.status = TaskStatus.FAILED

                # Fase 3: Compensação
                await self._compensate_completed_steps()
                raise OrchestrationError(
                    f"Falha no passo {step.step_id}: {e}"
                ) from e

        return self._aggregate_results(results)

    async def _create_plan(
        self,
        task: str,
        context: dict
    ) -> list[OrchestrationStep]:
        """
        Usa agente planejador para decompor tarefa em passos.
        O planejador considera agentes disponíveis no registry.
        """
        available_agents = [
            {"id": a.agent_id, "capabilities": a.capabilities}
            for a in self.registry._agents.values()
            if a.is_healthy
        ]

        plan_result = await self.planner.execute(
            "create_plan",
            {
                "task": task,
                "context": context,
                "available_agents": available_agents
            }
        )

        return [
            OrchestrationStep(**step_data)
            for step_data in plan_result["steps"]
        ]

    async def _compensate_completed_steps(self) -> None:
        """
        Executa compensações em ordem reversa.
        Implementa rollback semântico da Saga.
        """
        completed = [
            s for s in self._execution_history
            if s.status == TaskStatus.COMPLETED
            and s.compensation_action
        ]

        for step in reversed(completed):
            try:
                agent = await self._get_agent(step.agent_id)
                await agent.compensate(
                    step.compensation_action,
                    step.result
                )
                step.status = TaskStatus.COMPENSATED
            except Exception as e:
                # Log e continua - compensação é best-effort
                print(f"Falha na compensação de {step.step_id}: {e}")

    async def _get_agent(self, agent_id: str) -> Agent:
        """Obtém instância de agente do registry."""
        # Implementação depende de como agentes são instanciados
        raise NotImplementedError

    def _resolve_inputs(
        self,
        mapping: dict[str, str],
        results: dict[str, Any]
    ) -> dict:
        """Resolve referências a outputs anteriores."""
        resolved = {}
        for key, ref in mapping.items():
            if ref.startswith("$"):
                step_id, field = ref[1:].split(".")
                resolved[key] = results[step_id][field]
            else:
                resolved[key] = ref
        return resolved

    def _aggregate_results(self, results: dict) -> dict:
        """Agrega resultados de todos os passos."""
        return {
            "success": True,
            "steps": results,
            "execution_trace": [
                {
                    "step": s.step_id,
                    "agent": s.agent_id,
                    "status": s.status.value
                }
                for s in self._execution_history
            ]
        }

class OrchestrationError(Exception):
    pass
