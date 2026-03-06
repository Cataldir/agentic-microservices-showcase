"""
Chapter 1 & 7: Circuit Breaker Pattern

Prevents cascading failures by detecting repeated errors and temporarily
rejecting calls to a failing downstream service.

States: CLOSED → OPEN (on threshold) → HALF_OPEN (on timeout) → CLOSED (on success)

Chapter 7 extends with AI-specific failure detectors:
  - Latency:    trips when p95 latency > SLO (ms)
  - Confidence: trips when LLM confidence < threshold
  - Cost:       trips when token budget is exhausted
"""

from __future__ import annotations

import asyncio
import time
from enum import auto, Enum
from typing import Any, Callable, Awaitable


class CircuitState(Enum):
    CLOSED = auto()
    OPEN = auto()
    HALF_OPEN = auto()


class CircuitBreakerError(Exception):
    pass


class CircuitBreaker:
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout_s: float = 30.0,
        half_open_max_calls: int = 1,
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_s = recovery_timeout_s
        self.half_open_max_calls = half_open_max_calls
        self._state = CircuitState.CLOSED
        self._failure_count = 0
        self._half_open_calls = 0
        self._last_failure_time: float | None = None
        self._lock = asyncio.Lock()

    @property
    def state(self) -> CircuitState:
        return self._state

    async def call(self, fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
        async with self._lock:
            self._check_recovery()
            if self._state == CircuitState.OPEN:
                raise CircuitBreakerError("Circuit OPEN — call rejected")
            if self._state == CircuitState.HALF_OPEN:
                if self._half_open_calls >= self.half_open_max_calls:
                    raise CircuitBreakerError("Circuit HALF-OPEN — probe in flight")
                self._half_open_calls += 1
        try:
            result = await fn(*args, **kwargs)
            await self._on_success()
            return result
        except CircuitBreakerError:
            raise
        except Exception:
            await self._on_failure()
            raise

    def _check_recovery(self) -> None:
        if self._state == CircuitState.OPEN and self._last_failure_time:
            if time.monotonic() - self._last_failure_time >= self.recovery_timeout_s:
                self._state = CircuitState.HALF_OPEN
                self._half_open_calls = 0

    async def _on_success(self) -> None:
        async with self._lock:
            self._failure_count = 0
            self._half_open_calls = 0
            self._state = CircuitState.CLOSED

    async def _on_failure(self) -> None:
        async with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.monotonic()
            if self._failure_count >= self.failure_threshold:
                self._state = CircuitState.OPEN


class AgentCircuitBreaker:
    """
    AI-specific multi-mode circuit breaker (Chapter 7, §Guardrails).
    Three failure modes: latency, confidence, and cost.
    """

    def __init__(
        self,
        latency_slo_ms: float = 2_000.0,
        confidence_threshold: float = 0.6,
        token_budget: int = 50_000,
        base_failure_threshold: int = 5,
    ):
        self._base = CircuitBreaker(failure_threshold=base_failure_threshold)
        self.latency_slo_ms = latency_slo_ms
        self.confidence_threshold = confidence_threshold
        self.token_budget = token_budget
        self._total_tokens = 0
        self._latencies: list[float] = []

    async def call(
        self, fn: Callable[..., Awaitable[Any]], *args: Any,
        expected_confidence: float = 1.0, token_cost: int = 0, **kwargs: Any,
    ) -> Any:
        if self._total_tokens + token_cost > self.token_budget:
            raise CircuitBreakerError(f"Token budget exhausted ({self._total_tokens}/{self.token_budget})")
        if expected_confidence < self.confidence_threshold:
            raise CircuitBreakerError(f"Confidence {expected_confidence:.2f} < threshold {self.confidence_threshold}")
        start_ms = time.monotonic() * 1_000
        result = await self._base.call(fn, *args, **kwargs)
        elapsed_ms = time.monotonic() * 1_000 - start_ms
        self._total_tokens += token_cost
        self._latencies.append(elapsed_ms)
        if self._p95_latency() > self.latency_slo_ms:
            await self._base._on_failure()
        return result

    def _p95_latency(self) -> float:
        if not self._latencies:
            return 0.0
        s = sorted(self._latencies)
        return s[min(int(len(s) * 0.95), len(s) - 1)]

    @property
    def state(self) -> CircuitState:
        return self._base.state

    @property
    def tokens_consumed(self) -> int:
        return self._total_tokens
