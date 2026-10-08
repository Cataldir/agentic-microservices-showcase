class AgentWithFallback:
    """
    Agente com estratégias de fallback quando circuit breaker abre.
    """

    def __init__(
        self,
        primary_agent: Any,
        fallback_agent: Any | None = None,
        cache: Any | None = None
    ):
        self.primary = primary_agent
        self.fallback = fallback_agent
        self.cache = cache
        self.circuit_breaker = AgentCircuitBreaker("primary")

    async def execute(self, task: str, context: dict) -> dict:
        """
        Executa tarefa com fallback em caso de falha.

        Estratégia:
        1. Tenta agente primário
        2. Se circuit aberto ou falha, tenta cache
        3. Se sem cache, tenta agente secundário (modelo menor)
        4. Se tudo falhar, retorna resposta degradada
        """
        cache_key = self._compute_cache_key(task, context)

        try:
            result = await self.circuit_breaker.call(
                self.primary.execute,
                task,
                context
            )
            # Atualiza cache em caso de sucesso
            if self.cache:
                await self.cache.set(cache_key, result)
            return result

        except CircuitOpenError:
            return await self._fallback_strategy(task, context, cache_key)

        except Exception as e:
            return await self._fallback_strategy(task, context, cache_key)

    async def _fallback_strategy(
        self,
        task: str,
        context: dict,
        cache_key: str
    ) -> dict:
        """Executa estratégia de fallback em ordem de preferência."""

        # Estratégia 1: Cache
        if self.cache:
            cached = await self.cache.get(cache_key)
            if cached:
                return {
                    **cached,
                    "_fallback": "cache",
                    "_warning": "Resposta em cache, pode estar desatualizada"
                }

        # Estratégia 2: Agente secundário (modelo menor/mais rápido)
        if self.fallback:
            try:
                result = await self.fallback.execute(task, context)
                return {
                    **result,
                    "_fallback": "secondary_agent",
                    "_warning": "Usando modelo secundário, qualidade pode variar"
                }
            except Exception:
                pass

        # Estratégia 3: Resposta degradada
        return {
            "success": False,
            "_fallback": "degraded",
            "_error": "Serviço temporariamente indisponível",
            "_suggestion": "Por favor, tente novamente em alguns minutos"
        }

    def _compute_cache_key(self, task: str, context: dict) -> str:
        """Computa chave de cache determinística."""
        import hashlib
        import json
        content = json.dumps({"task": task, "context": context}, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()
