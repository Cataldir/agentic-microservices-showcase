async def call(self, func, *args, **kwargs):
    async with self._lock:
        if not self._should_allow_call():
            self.metrics.rejected_calls += 1
            raise CircuitOpenError(
                f"Circuit {self.name} is "
                f"{self.state.value}")
    self.metrics.total_calls += 1
    start_time = time.time()
    try:
        result = await asyncio.wait_for(
            func(*args, **kwargs)
            if asyncio.iscoroutinefunction(func)
            else asyncio.to_thread(func, *args, **kwargs),
            timeout=self.config.timeout_seconds)
        if (self.config.include_quality_in_failure
                and self.quality_evaluator):
            quality = self.quality_evaluator(result)
            if quality < self.config.quality_threshold:
                raise QualityBelowThresholdError(
                    f"Quality {quality} below threshold "
                    f"{self.config.quality_threshold}")
        await self._record_success(time.time() - start_time)
        return result
    except Exception:
        await self._record_failure()
        raise
