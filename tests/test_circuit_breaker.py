"""
Tests for CircuitBreaker and AgentCircuitBreaker.
"""
import pytest
from core.patterns.circuit_breaker import (
    AgentCircuitBreaker, CircuitBreaker, CircuitBreakerError, CircuitState,
)


async def ok() -> str: return "ok"
async def fail() -> str: raise RuntimeError("downstream failure")


@pytest.mark.asyncio
async def test_starts_closed():
    assert CircuitBreaker().state == CircuitState.CLOSED


@pytest.mark.asyncio
async def test_opens_after_threshold():
    cb = CircuitBreaker(failure_threshold=2)
    for _ in range(2):
        with pytest.raises(RuntimeError):
            await cb.call(fail)
    assert cb.state == CircuitState.OPEN


@pytest.mark.asyncio
async def test_open_rejects_calls():
    cb = CircuitBreaker(failure_threshold=1)
    with pytest.raises(RuntimeError):
        await cb.call(fail)
    with pytest.raises(CircuitBreakerError):
        await cb.call(ok)


@pytest.mark.asyncio
async def test_agent_circuit_rejects_on_budget_exhausted():
    acb = AgentCircuitBreaker(token_budget=10)
    with pytest.raises(CircuitBreakerError):
        await acb.call(ok, token_cost=20)
