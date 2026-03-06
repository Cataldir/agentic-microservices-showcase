"""
Tests for ReflexionAgent.
"""
import pytest
from core.agents.reflexion import ReflexionAgent


@pytest.mark.asyncio
async def test_reflexion_converges_on_high_score():
    async def generate(prompt): return "Good detailed response about the topic."
    async def reflect(response, task): return "Already excellent."
    async def score(response): return 0.95

    agent = ReflexionAgent(generate, reflect, score, quality_threshold=0.85)
    result = await agent.run("Explain microservices")
    assert result.converged is True
    assert result.quality_score >= 0.85
    assert result.iterations == 1


@pytest.mark.asyncio
async def test_reflexion_exhausts_max_iterations():
    calls = [0]

    async def generate(prompt):
        calls[0] += 1
        return f"Attempt {calls[0]}"

    async def reflect(response, task): return "Try harder."
    async def score(response): return 0.2  # Always fails

    agent = ReflexionAgent(generate, reflect, score, quality_threshold=0.85, max_iterations=3)
    result = await agent.run("Explain circuit breakers")
    assert result.converged is False
    assert result.iterations == 3
