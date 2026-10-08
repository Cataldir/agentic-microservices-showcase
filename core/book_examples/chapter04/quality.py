"""Complete 04-09 listing, with only its missing breaker imports assembled."""
from core.book_examples.chapter04.breaker import AgentCircuitBreaker, CircuitBreakerConfig

from abc import ABC, abstractmethod
import re
from typing import Callable

class QualityEvaluator(ABC):
    """Interface base para avaliadores de qualidade."""

    @abstractmethod
    def evaluate(self, response: str, context: dict | None = None) -> float:
        """Retorna score de 0.0 (péssimo) a 1.0
        (excelente)."""
        ...

class HeuristicQualityEvaluator(QualityEvaluator):
    """Avaliador baseado em heurísticas estruturais."""

    def __init__(
        self,
        min_length: int = 50,
        max_length: int = 5000,
        ideal_length_range: tuple[int, int] = (200, 2000)
    ):
        self.min_length = min_length
        self.max_length = max_length
        self.ideal_range = ideal_length_range

    def evaluate(self, response: str, context: dict | None = None) -> float:
        """Avalia usando heurísticas de estrutura."""
        scores = []
        length = len(response)
        # Penalidade por comprimento inadequado
        if length < self.min_length:
            scores.append(0.3)  # Muito curto
        elif length > self.max_length:
            scores.append(0.5)  # Muito longo
        elif self.ideal_range[0] <= length <= self.ideal_range[1]:
            scores.append(1.0)  # Ideal
        else:
            scores.append(0.8)  # Aceitável
        # Bonus por estrutura (parágrafos, listas)
        has_paragraphs = response.count("\n\n") >= 1
        has_lists = bool(re.search(r"^[\-\*\d]\.", response, re.MULTILINE))
        structure_score = 0.7
        if has_paragraphs:
            structure_score += 0.15
        if has_lists:
            structure_score += 0.15
        scores.append(structure_score)
        return sum(scores) / len(scores)

class EvasionDetectorEvaluator(QualityEvaluator):
    """Detecta respostas evasivas e disclaimers
    excessivos."""
    EVASION_PATTERNS = [
        r"como (um |uma )?(modelo|IA|inteligência artificial)",
        r"não (posso|consigo|tenho capacidade)",
        r"é importante (notar|considerar|lembrar) que",
        r"depende (do|de|da) contexto",
        r"existem (muitos|vários|diversos) fatores",
        r"eu recomendaria consultar (um|uma) (especialista|profissional)",
        r"não tenho acesso a informações (atualizadas|em tempo real)",
    ]

    def __init__(self, max_evasions: int = 2, penalty_per_evasion: float = 0.15):
        self.max_evasions = max_evasions
        self.penalty = penalty_per_evasion
        self.patterns = [re.compile(p, re.IGNORECASE) for p in self.EVASION_PATTERNS]

    def evaluate(self, response: str, context: dict | None = None) -> float:
        """Conta padrões de evasão e penaliza
        proporcionalmente."""
        evasion_count = sum(
            1 for pattern in self.patterns
            if pattern.search(response)
        )
        if evasion_count <= self.max_evasions:
            return 1.0 - (evasion_count * self.penalty * 0.5)
        # Penalidade mais severa acima do threshold
        excess = evasion_count - self.max_evasions
        base_score = 1.0 - (self.max_evasions * self.penalty * 0.5)
        return max(0.1, base_score - (excess * self.penalty))

class CompositeQualityEvaluator(QualityEvaluator):
    """Combina múltiplos avaliadores com pesos
    configuráveis."""

    def __init__(self, evaluators: list[tuple[QualityEvaluator, float]]):
        """Recebe pares (avaliador, peso); pesos somam 1."""
        self.evaluators = evaluators
        total_weight = sum(w for _, w in evaluators)
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError(f"Pesos devem somar 1.0, mas somam {total_weight}")

    def evaluate(self, response: str, context: dict | None = None) -> float:
        """Média ponderada dos avaliadores componentes."""
        return sum(
            evaluator.evaluate(response, context) * weight
            for evaluator, weight in self.evaluators
        )
# Exemplo de uso prático
def create_production_evaluator() -> QualityEvaluator:
    """Cria avaliador de qualidade para ambiente de
    produção."""
    return CompositeQualityEvaluator([
        (HeuristicQualityEvaluator(), 0.4),
        (EvasionDetectorEvaluator(), 0.6),
    ])
# Integração com o circuit breaker
circuit_breaker = AgentCircuitBreaker(
    name="customer-support-agent",
    config=CircuitBreakerConfig(
        include_quality_in_failure=True,
        quality_threshold=0.7,  # 70% é o mínimo aceitável
    ),
    quality_evaluator=create_production_evaluator().evaluate
)
