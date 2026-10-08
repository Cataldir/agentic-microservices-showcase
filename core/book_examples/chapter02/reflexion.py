from dataclasses import dataclass
from typing import Protocol, TypeVar
import asyncio
T = TypeVar("T")

class LLMClient(Protocol):
    """Interface para cliente LLM."""
    async def generate(self, prompt: str) -> str: ...

@dataclass
class ReflexionResult:
    """Resultado de uma iteração Reflexion."""
    response: str
    reflection: str
    quality_score: float
    iteration: int
    is_final: bool

class ReflexionAgent:
    """Agente com capacidade de autorreflexão e correção."""

    def __init__(
        self,
        llm: LLMClient,
        quality_threshold: float = 0.8,
        max_iterations: int = 3
    ):
        # Guards are local support-material additions; archive/02/02-01.py is unchanged.
        if (isinstance(max_iterations, bool)
                or not isinstance(max_iterations, int)
                or max_iterations < 1):
            raise ValueError("max_iterations deve ser um inteiro >= 1")
        if not 0.0 <= quality_threshold <= 1.0:
            raise ValueError("quality_threshold deve estar entre 0.0 e 1.0")
        self.llm = llm
        self.quality_threshold = quality_threshold
        self.max_iterations = max_iterations
        self.history: list[ReflexionResult] = []

    async def solve(self, task: str) -> ReflexionResult:
        """Resolve uma tarefa com autorreflexão
        iterativa."""
        self.history.clear()
        context = f"Tarefa: {task}"
        for iteration in range(1, self.max_iterations + 1):
            # Fase 1: Gerar resposta
            response = await self._generate_response(context)
            # Fase 2: Autorreflexão crítica
            reflection, score = await self._reflect(task, response)
            result = ReflexionResult(
                response=response,
                reflection=reflection,
                quality_score=score,
                iteration=iteration,
                is_final=(score >= self.quality_threshold
                          or iteration == self.max_iterations)
            )
            self.history.append(result)
            if result.is_final:
                return result
            # Fase 3: Incorporar reflexão no contexto para próxima iteração
            context = self._build_improved_context(task, response, reflection)
        return self.history[-1]

    async def _generate_response(self, context: str) -> str:
        """Gera resposta baseada no contexto atual."""
        prompt = f"""
{context}
Forneça uma resposta completa e precisa.
Resposta:"""
        return await self.llm.generate(prompt)

    async def _reflect(self, task: str, response: str) -> tuple[str, float]:
        """Analisa criticamente a resposta gerada."""
        prompt = f"""
Analise criticamente a seguinte resposta para a tarefa dada.
Tarefa: {task}
Resposta a avaliar:
{response}
Avalie em três dimensões:
1. Completude: A resposta aborda todos os aspectos da tarefa?
2. Correção: As informações estão corretas e bem fundamentadas?
3. Clareza: A resposta é clara e bem estruturada?
Forneça:
- Uma reflexão detalhada identificando pontos fortes e fracos
- Uma nota de 0.0 a 1.0 para a qualidade geral
Formato da resposta:
REFLEXÃO: [sua análise crítica]
SCORE: [valor numérico]"""
        result = await self.llm.generate(prompt)
        # Parse simples do resultado
        reflection = ""
        score = 0.5  # Default conservador
        for line in result.split("\n"):
            if line.startswith("REFLEXÃO:"):
                reflection = line[9:].strip()
            elif line.startswith("SCORE:"):
                try:
                    score = float(line[6:].strip())
                    score = max(0.0, min(1.0, score))
                except ValueError:
                    pass
        return reflection, score

    def _build_improved_context(
        self,
        task: str,
        previous_response: str,
        reflection: str
    ) -> str:
        """Constrói contexto enriquecido com feedback da
        reflexão."""
        return f"""
Tarefa: {task}
Sua tentativa anterior:
{previous_response}
Autorreflexão identificou os seguintes problemas:
{reflection}
Por favor, gere uma resposta MELHORADA que corrija os problemas identificados.
Mantenha os pontos fortes e corrija as deficiências."""
