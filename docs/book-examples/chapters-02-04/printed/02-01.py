async def solve(self, task: str) -> ReflexionResult:
    self.history.clear()
    context = f"Tarefa: {task}"
    for iteration in range(1, self.max_iterations + 1):
        response = await self._generate_response(context)
        reflection, score = await self._reflect(task, response)
        final = (score >= self.quality_threshold
                 or iteration == self.max_iterations)
        result = ReflexionResult(
            response, reflection, score, iteration, final)
        self.history.append(result)
        if final:
            return result
        context = self._build_improved_context(
            task, response, reflection)
    return self.history[-1]
