class CompositeQualityEvaluator(QualityEvaluator):
    def __init__(self, evaluators):
        self.evaluators = evaluators
        total_weight = sum(w for _, w in evaluators)
        if abs(total_weight - 1.0) > 0.001:
            raise ValueError(
                f"Pesos devem somar 1.0, mas somam "
                f"{total_weight}")

    def evaluate(self, response: str,
                 context: dict | None = None
                 ) -> float:
        return sum(
            evaluator.evaluate(response, context) * weight
            for evaluator, weight in self.evaluators)

def create_production_evaluator() -> QualityEvaluator:
    return CompositeQualityEvaluator([
        (HeuristicQualityEvaluator(), 0.4),
        (EvasionDetectorEvaluator(), 0.6)])
