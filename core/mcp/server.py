"""
Chapter 5: Model Context Protocol (MCP) Server

Exposes Tools (actions), Resources (data), and Prompts (templates)
via a simulated JSON-RPC interface for local demonstration.

For production: use the official `mcp` Python SDK with stdio/HTTP+SSE transport.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Awaitable


@dataclass
class ToolDefinition:
    name: str
    description: str
    input_schema: dict[str, Any]
    handler: Callable[..., Awaitable[Any]] | None = None


@dataclass
class ResourceDefinition:
    uri: str
    name: str
    mime_type: str = "text/plain"
    description: str = ""
    reader: Callable[[], Awaitable[Any]] | None = None


@dataclass
class PromptDefinition:
    name: str
    description: str
    arguments: list[dict[str, str]] = field(default_factory=list)
    template: str = ""


class MCPServer:
    """
    Local MCP server (Chapter 5, §MCP Architecture).

    Usage::

        server = MCPServer("OrderServer")
        server.register_tool(ToolDefinition(
            name="get_order",
            description="Retrieve an order by ID",
            input_schema={"type": "object", "properties": {"order_id": {"type": "string"}}},
            handler=get_order_handler,
        ))
        result = await server.call_tool("get_order", {"order_id": "ORD-123"})
    """

    def __init__(self, name: str, version: str = "1.0.0"):
        self.name = name
        self.version = version
        self._tools: dict[str, ToolDefinition] = {}
        self._resources: dict[str, ResourceDefinition] = {}
        self._prompts: dict[str, PromptDefinition] = {}

    def register_tool(self, tool: ToolDefinition) -> None:
        self._tools[tool.name] = tool

    def register_resource(self, resource: ResourceDefinition) -> None:
        self._resources[resource.uri] = resource

    def register_prompt(self, prompt: PromptDefinition) -> None:
        self._prompts[prompt.name] = prompt

    def list_tools(self) -> list[dict[str, Any]]:
        return [
            {"name": t.name, "description": t.description, "inputSchema": t.input_schema}
            for t in self._tools.values()
        ]

    async def call_tool(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        tool = self._tools.get(name)
        if not tool:
            return {"isError": True, "content": [{"type": "text", "text": f"Tool '{name}' not found"}]}
        if not tool.handler:
            return {"isError": True, "content": [{"type": "text", "text": f"Tool '{name}' has no handler"}]}
        try:
            result = await tool.handler(**arguments)
            return {"isError": False, "content": [{"type": "text", "text": str(result)}]}
        except Exception as exc:
            return {"isError": True, "content": [{"type": "text", "text": str(exc)}]}

    def list_resources(self) -> list[dict[str, Any]]:
        return [
            {"uri": r.uri, "name": r.name, "mimeType": r.mime_type}
            for r in self._resources.values()
        ]

    async def read_resource(self, uri: str) -> dict[str, Any]:
        resource = self._resources.get(uri)
        if not resource or not resource.reader:
            return {"error": f"Resource '{uri}' not found or has no reader"}
        content = await resource.reader()
        return {"contents": [{"uri": uri, "mimeType": resource.mime_type, "text": str(content)}]}

    def list_prompts(self) -> list[dict[str, Any]]:
        return [
            {"name": p.name, "description": p.description, "arguments": p.arguments}
            for p in self._prompts.values()
        ]

    async def get_prompt(self, name: str, arguments: dict[str, str] | None = None) -> dict[str, Any]:
        prompt = self._prompts.get(name)
        if not prompt:
            return {"error": f"Prompt '{name}' not found"}
        text = prompt.template
        for k, v in (arguments or {}).items():
            text = text.replace(f"{{{k}}}", v)
        return {"messages": [{"role": "user", "content": {"type": "text", "text": text}}]}
