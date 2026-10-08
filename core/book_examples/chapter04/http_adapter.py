"""Complete 04-12 behavior with an explicit injected local HTTP port.

The immutable archive retains the httpx version. This variant neither imports
httpx nor opens a connection. See README-QUALITY-HTTP.md for the exact boundary.
"""
from dataclasses import dataclass
from typing import Any, Protocol

class HttpResponsePort(Protocol):
    """Local boundary used by the injected client variant."""
    status_code: int

    def raise_for_status(self) -> None: ...
    def json(self) -> Any: ...

class AsyncHttpClientPort(Protocol):
    """A client must provide get/post; its own timeout is configured by the caller."""
    async def get(self, url: str, *, params: dict) -> HttpResponsePort: ...
    async def post(self, url: str, *, json: dict) -> HttpResponsePort: ...

class HTTPStatusError(Exception):
    """Local status-error shape for offline tests; not httpx.HTTPStatusError."""
    def __init__(self, message: str, *, response: HttpResponsePort):
        super().__init__(message)
        self.response = response

@dataclass
class ToolDefinition:
    """
    Definição de tool para exposição a agentes.
    Compatível com OpenAI function calling e MCP.
    """
    name: str
    description: str
    parameters: dict  # JSON Schema
    required: list[str]

class MicroserviceToolAdapter:
    """
    Adapta um microsserviço existente como tool para agentes.

    Responsabilidades:
    - Expor interface de tool (JSON Schema)
    - Traduzir chamadas de tool para requisições HTTP
    - Cachear respostas quando apropriado
    - Implementar rate limiting
    """

    def __init__(
        self,
        service_base_url: str,
        tool_definition: ToolDefinition,
        cache_ttl_seconds: int = 300,
        *,
        client: AsyncHttpClientPort
    ):
        self.service_url = service_base_url
        self.definition = tool_definition
        self.cache_ttl = cache_ttl_seconds
        self._cache: dict[str, tuple[Any, float]] = {}
        self._client = client

    def get_tool_schema(self) -> dict:
        """
        Retorna schema da tool no formato esperado pelo agente.
        Compatível com OpenAI function calling.
        """
        return {
            "type": "function",
            "function": {
                "name": self.definition.name,
                "description": self.definition.description,
                "parameters": {
                    "type": "object",
                    "properties": self.definition.parameters,
                    "required": self.definition.required
                }
            }
        }

    async def execute(self, arguments: dict) -> dict:
        """
        Executa a tool, chamando o microsserviço subjacente.
        """
        # Verifica cache
        cache_key = self._compute_cache_key(arguments)
        cached = self._get_from_cache(cache_key)
        if cached is not None:
            return cached

        # Constrói e executa requisição
        endpoint = self._build_endpoint(arguments)
        method = self._determine_method(arguments)

        try:
            if method == "GET":
                response = await self._client.get(
                    f"{self.service_url}{endpoint}",
                    params=arguments
                )
            else:
                response = await self._client.post(
                    f"{self.service_url}{endpoint}",
                    json=arguments
                )

            response.raise_for_status()
            result = response.json()

            # Atualiza cache
            self._set_cache(cache_key, result)

            return result

        except HTTPStatusError as e:
            return {
                "error": True,
                "status_code": e.response.status_code,
                "message": f"Erro ao chamar {self.definition.name}"
            }

    def _compute_cache_key(self, arguments: dict) -> str:
        import hashlib
        import json
        content = json.dumps(arguments, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

    def _get_from_cache(self, key: str) -> Any | None:
        import time
        if key in self._cache:
            value, timestamp = self._cache[key]
            if time.time() - timestamp < self.cache_ttl:
                return value
            del self._cache[key]
        return None

    def _set_cache(self, key: str, value: Any) -> None:
        import time
        self._cache[key] = (value, time.time())

    def _build_endpoint(self, arguments: dict) -> str:
        """Constrói endpoint baseado em argumentos. Override em subclasses."""
        return "/"

    def _determine_method(self, arguments: dict) -> str:
        """Determina método HTTP. Override em subclasses."""
        return "GET"

# Exemplo: Adapter para Catalog Service
class CatalogToolAdapter(MicroserviceToolAdapter):
    """Adapter que expõe Catalog Service como tool."""

    def __init__(self, catalog_service_url: str, *, client: AsyncHttpClientPort):
        super().__init__(
            service_base_url=catalog_service_url,
            tool_definition=ToolDefinition(
                name="search_products",
                description=(
                    "Busca produtos no catálogo por termo de pesquisa. "
                    "Retorna lista de produtos com nome, preço e disponibilidade."
                ),
                parameters={
                    "query": {
                        "type": "string",
                        "description": "Termo de busca"
                    },
                    "category": {
                        "type": "string",
                        "description": "Categoria para filtrar (opcional)"
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Número máximo de resultados",
                        "default": 10
                    }
                },
                required=["query"]
            ),
            client=client
        )

    def _build_endpoint(self, arguments: dict) -> str:
        return "/api/v1/products/search"

    def _determine_method(self, arguments: dict) -> str:
        return "GET"
