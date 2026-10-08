async def execute(self, arguments: dict) -> dict:
    cache_key = self._compute_cache_key(arguments)
    cached = self._get_from_cache(cache_key)
    if cached is not None:
        return cached
    endpoint = self._build_endpoint(arguments)
    method = self._determine_method(arguments)
    try:
        if method == "GET":
            response = await self._client.get(
                f"{self.service_url}{endpoint}",
                params=arguments)
        else:
            response = await self._client.post(
                f"{self.service_url}{endpoint}",
                json=arguments)
        response.raise_for_status()
        result = response.json()
        self._set_cache(cache_key, result)
        return result
    except httpx.HTTPStatusError as e:
        return {"error": True,
                "status_code": e.response.status_code,
                "message":
                f"Erro ao chamar {self.definition.name}"}
