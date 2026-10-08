"""
Chapter 2: Reflexion Agent Pattern

The Reflexion pattern drives iterative self-correction:
  1. Generate a candidate response
  2. Evaluate it against a quality threshold
  3. Reflect on shortcomings
  4. Re-generate an improved response

Reference: Shinn et al. (2023), "Reflexion: Language Agents with
Verbal Reinforcement Learning", NeurIPS 2023.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class ReflexionResult:
    """The final product of a Reflexion loop, including all iteration traces."""
    final_response: str
    quality_score: float
    iterations: int
    trace: list[dict[str, Any]] = field(default_factory=list)
    converged: bool = False


class ReflexionAgent:
    """
    Portable Reflexion agent that works with any async LLM callable.
    Stateless across calls — each task starts fresh (hot memory model).

    Example::

        async def mock_generate(prompt): return "draft response"
        async def mock_reflect(response, task): return "be more specific"
        async def mock_score(response): return 0.9

        agent = ReflexionAgent(mock_generate, mock_reflect, mock_score)
        result = await agent.run("Explain circuit breakers")
    """

    def __init__(
        self,
        generate_fn: Callable[[str], Awaitable[str]],
        reflect_fn: Callable[[str, str], Awaitable[str]],
        score_fn: Callable[[str], Awaitable[float]],
        quality_threshold: float = 0.85,
        max_iterations: int = 3,
    ):
        self._generate = generate_fn
        self._reflect = reflect_fn
        self._score = score_fn
        self.quality_threshold = quality_threshold
        self.max_iterations = max_iterations

    async def run(self, task: str) -> ReflexionResult:
        trace: list[dict[str, Any]] = []
        response = await self._generate(task)

        for iteration in range(self.max_iterations):
            score = await self._score(response)
            trace.append({"iteration": iteration + 1, "response": response, "score": score})

            if score >= self.quality_threshold:
                return ReflexionResult(
                    final_response=response, quality_score=score,
                    iterations=iteration + 1, trace=trace, converged=True,
                )

            reflection = await self._reflect(response, task)
            response = await self._generate(
                f"{task}\n\nPrevious attempt:\n{response}\n\n"
                f"Reflection:\n{reflection}\n\nImproved response:"
            )

        final_score = await self._score(response)
        trace.append({"iteration": self.max_iterations, "response": response, "score": final_score})
        return ReflexionResult(
            final_response=response, quality_score=final_score,
            iterations=self.max_iterations, trace=trace, converged=False,
        )
