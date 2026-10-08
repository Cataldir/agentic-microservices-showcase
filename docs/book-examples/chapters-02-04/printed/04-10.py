async def _fallback_strategy(self, task, context,
                             cache_key):
    if self.cache:
        cached = await self.cache.get(cache_key)
        if cached:
            return {
                **cached, "_fallback": "cache",
                "_warning":
                    "Resposta em cache, "
                    "pode estar desatualizada"}
    if self.fallback:
        try:
            result = await self.fallback.execute(
                task, context)
            return {
                **result, "_fallback": "secondary_agent",
                "_warning":
                "Usando modelo secundário, "
                "qualidade pode variar"}
        except Exception:
            pass
    return {
        "success": False, "_fallback": "degraded",
        "_error": "Serviço temporariamente indisponível",
        "_suggestion":
            "Por favor, tente novamente em alguns minutos"}
