"""
Chapter 8: LLM-as-Judge Evaluation Framework

Classical testing cannot validate non-deterministic LLM output.
We need multi-dimensional semantic scoring evaluated by another LLM.

Dimensions:
  - Relevance:    Does the response address the task?
  - Groundedness: Is it grounded in verifiable facts?
  - Coherence:    Is it internally consistent and logical?
  - Fluency:      Is it well-written and grammatical?

In the six-stage CI/CD pipeline (Chapter 8), this runs in Stage 3
before any deployment, blocking promotion if quality gates fail.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class EvaluationResult:
    task: str
    response: str
    relevance: float
    groundedness: float
    coherence: float
    fluency: float
    pass_threshold: float = 0.7
    reasoning: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    @property
    def overall_score(self) -> float:
        return (self.relevance + self.groundedness + self.coherence + self.fluency) / 4.0

    @property
    def passed(self) -> bool:
        return self.overall_score >= self.pass_threshold

    def to_dict(self) -> dict[str, Any]:
        return {
            "task": self.task, "relevance": self.relevance,
            "groundedness": self.groundedness, "coherence": self.coherence,
            "fluency": self.fluency, "overall": self.overall_score,
            "passed": self.passed, "reasoning": self.reasoning,
        }


@dataclass
class EvaluationReport:
    results: list[EvaluationResult] = field(default_factory=list)
    model_under_test: str = ""
    prompt_version: str = ""

    @property
    def pass_rate(self) -> float:
        return sum(1 for r in self.results if r.passed) / len(self.results) if self.results else 0.0

    @property
    def avg_quality(self) -> dict[str, float]:
        if not self.results:
            return {}
        n = len(self.results)
        return {
            "relevance": sum(r.relevance for r in self.results) / n,
            "groundedness": sum(r.groundedness for r in self.results) / n,
            "coherence": sum(r.coherence for r in self.results) / n,
            "fluency": sum(r.fluency for r in self.results) / n,
            "overall": sum(r.overall_score for r in self.results) / n,
        }

    def quality_gate_passed(self, threshold: float = 0.8) -> bool:
        """CI gate (Chapter 8, §Pipeline Stage 3): block if any dimension fails."""
        avg = self.avg_quality
        return bool(avg) and all(v >= threshold for v in avg.values())

    def summary(self) -> str:
        avg = self.avg_quality
        if not avg:
            return "No results."
        lines = [
            f"Model: {self.model_under_test} | Prompt: {self.prompt_version}",
            f"Pass rate: {self.pass_rate:.1%} ({sum(r.passed for r in self.results)}/{len(self.results)})",
        ]
        for dim, score in avg.items():
            lines.append(f"  {'✓' if score >= 0.8 else '✗'} {dim}: {score:.3f}")
        return "\n".join(lines)


class LLMJudge:
    """
    Semantic evaluator using an LLM as judge (Chapter 8).
    Compatible with Azure OpenAI, OpenAI, Azure AI Foundry, or local models.
    """

    JUDGE_PROMPT = """\
You are an objective evaluator. Score the following AI response (0.0 to 1.0 each):
- relevance:    Does it address the task?
- groundedness: Is it factually grounded?
- coherence:    Is it logically consistent?
- fluency:      Is it well-written?

Task: {task}
Response: {response}

Return ONLY valid JSON: {{"relevance": 0.9, "groundedness": 0.8, "coherence": 0.95, "fluency": 0.85, "reasoning": "..."}}"""

    def __init__(self, judge_fn: Callable[[str], Awaitable[str]], pass_threshold: float = 0.7):
        self._judge = judge_fn
        self.pass_threshold = pass_threshold

    async def evaluate(self, task: str, response: str) -> EvaluationResult:
        prompt = self.JUDGE_PROMPT.format(task=task, response=response)
        raw = await self._judge(prompt)
        try:
            start, end = raw.find("{"), raw.rfind("}") + 1
            scores = json.loads(raw[start:end]) if start >= 0 else {}
        except (json.JSONDecodeError, ValueError):
            scores = {}
        return EvaluationResult(
            task=task, response=response,
            relevance=float(scores.get("relevance", 0.0)),
            groundedness=float(scores.get("groundedness", 0.0)),
            coherence=float(scores.get("coherence", 0.0)),
            fluency=float(scores.get("fluency", 0.0)),
            pass_threshold=self.pass_threshold,
            reasoning=str(scores.get("reasoning", raw)),
        )

    async def evaluate_batch(
        self, cases: list[dict[str, str]], model_under_test: str = "", prompt_version: str = ""
    ) -> EvaluationReport:
        results = [await self.evaluate(c["task"], c["response"]) for c in cases]
        return EvaluationReport(results=results, model_under_test=model_under_test, prompt_version=prompt_version)
