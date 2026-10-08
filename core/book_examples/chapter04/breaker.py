from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Callable, TypeVar, Generic, Any
from enum import Enum
import asyncio
import time

T = TypeVar('T')

class CircuitState(Enum):
    CLOSED = "closed"      # Operação normal
    OPEN = "open"          # Rejeitando requisições
    HALF_OPEN = "half_open"  # Testando recuperação

@dataclass
class CircuitBreakerConfig:
    """Configuração do circuit breaker."""
    failure_threshold: int = 5
    recovery_timeout_seconds: float = 60.0
    success_threshold: int = 2  # Sucessos para fechar em half-open
    timeout_seconds: float = 30.0
    # Específico para agentes
    quality_threshold: float = 0.7  # Score mínimo de qualidade
    include_quality_in_failure: bool = True

@dataclass
class CircuitMetrics:
    """Métricas do circuit breaker."""
    total_calls: int = 0
    successful_calls: int = 0
    failed_calls: int = 0
    rejected_calls: int = 0
    consecutive_failures: int = 0
    consecutive_successes: int = 0
    last_failure_time: float | None = None
    average_latency_ms: float = 0.0

class AgentCircuitBreaker(Generic[T]):
    """
    Circuit breaker especializado para agentes LLM.

    Considera não apenas falhas técnicas, mas também
    qualidade da resposta como critério de "falha".
    """

    def __init__(
        self,
        name: str,
        config: CircuitBreakerConfig | None = None,
        quality_evaluator: Callable[[T], float] | None = None
    ):
        self.name = name
        self.config = config or CircuitBreakerConfig()
        self.quality_evaluator = quality_evaluator
        self.state = CircuitState.CLOSED
        self.metrics = CircuitMetrics()
        self._lock = asyncio.Lock()

    async def call(
        self,
        func: Callable[..., T],
        *args,
        **kwargs
    ) -> T:
        """
        Executa função protegida pelo circuit breaker.

        Raises:
            CircuitOpenError: Se circuito está aberto
            TimeoutError: Se função excede timeout
        """
        async with self._lock:
            if not self._should_allow_call():
                self.metrics.rejected_calls += 1
                raise CircuitOpenError(
                    f"Circuit {self.name} is {self.state.value}"
                )

        self.metrics.total_calls += 1
        start_time = time.time()

        try:
            # Executa com timeout
            result = await asyncio.wait_for(
                func(*args, **kwargs)
                if asyncio.iscoroutinefunction(func)
                else asyncio.to_thread(func, *args, **kwargs),
                timeout=self.config.timeout_seconds
            )

            # Avalia qualidade se configurado
            if (
                self.config.include_quality_in_failure
                and self.quality_evaluator
            ):
                quality = self.quality_evaluator(result)
                if quality < self.config.quality_threshold:
                    raise QualityBelowThresholdError(
                        f"Quality {quality} below threshold "
                        f"{self.config.quality_threshold}"
                    )

            # Sucesso
            await self._record_success(time.time() - start_time)
            return result

        except (asyncio.TimeoutError, QualityBelowThresholdError) as e:
            await self._record_failure()
            raise
        except Exception as e:
            await self._record_failure()
            raise

    def _should_allow_call(self) -> bool:
        """Determina se chamada deve ser permitida."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Verifica se é hora de tentar novamente
            if self.metrics.last_failure_time:
                elapsed = time.time() - self.metrics.last_failure_time
                if elapsed >= self.config.recovery_timeout_seconds:
                    self.state = CircuitState.HALF_OPEN
                    return True
            return False

        if self.state == CircuitState.HALF_OPEN:
            return True

        return False

    async def _record_success(self, latency_seconds: float) -> None:
        """Registra chamada bem-sucedida."""
        async with self._lock:
            self.metrics.successful_calls += 1
            self.metrics.consecutive_failures = 0
            self.metrics.consecutive_successes += 1

            # Atualiza latência média
            alpha = 0.1
            latency_ms = latency_seconds * 1000
            self.metrics.average_latency_ms = (
                alpha * latency_ms +
                (1 - alpha) * self.metrics.average_latency_ms
            )

            # Transição de estado
            if self.state == CircuitState.HALF_OPEN:
                if (self.metrics.consecutive_successes >=
                        self.config.success_threshold):
                    self.state = CircuitState.CLOSED
                    self.metrics.consecutive_successes = 0

    async def _record_failure(self) -> None:
        """Registra chamada falha."""
        async with self._lock:
            self.metrics.failed_calls += 1
            self.metrics.consecutive_failures += 1
            self.metrics.consecutive_successes = 0
            self.metrics.last_failure_time = time.time()

            # Transição de estado
            if self.state == CircuitState.CLOSED:
                if (self.metrics.consecutive_failures >=
                        self.config.failure_threshold):
                    self.state = CircuitState.OPEN

            elif self.state == CircuitState.HALF_OPEN:
                # Qualquer falha em half-open reabre o circuito
                self.state = CircuitState.OPEN

class CircuitOpenError(Exception):
    """Levantada quando circuito está aberto."""
    pass

class QualityBelowThresholdError(Exception):
    """Levantada quando qualidade da resposta está abaixo do threshold."""
    pass
