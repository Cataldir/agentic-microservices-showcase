async def execute_task(self, task: str, context: dict
                       ) -> dict:
    plan = await self._create_plan(task, context)
    results = {}
    for step in plan:
        try:
            step.status = TaskStatus.IN_PROGRESS
            self._execution_history.append(step)
            inputs = self._resolve_inputs(
                step.input_mapping, results)
            agent = await self._get_agent(step.agent_id)
            result = await agent.execute(
                step.action, inputs)
            step.result = result
            step.status = TaskStatus.COMPLETED
            results[step.step_id] = result
        except Exception as e:
            step.error = str(e)
            step.status = TaskStatus.FAILED
            await self._compensate_completed_steps()
            raise OrchestrationError(
                f"Falha no passo {step.step_id}: "
                f"{e}") from e
    return self._aggregate_results(results)
