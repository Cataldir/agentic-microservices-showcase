"""Async callable for the notebook agent API; no SDK is imported at construction."""

import asyncio
from dataclasses import replace
from typing import Callable, Mapping

from .gcp_support.genai_adapter import GenerationConfig, GoogleGenAIAdapter


def build_generation_function(
    env: Mapping[str, str] | None = None,
    *,
    client_factory: Callable | None = None,
    max_output_tokens: int = 512,
):
    """Validate configuration and return an async text generator.

    The bounded synchronous SDK request runs in a worker thread. Cancelling the
    awaiting task does not abort a request already running in that thread; the
    configured SDK timeout still applies. No automatic retry is added here.
    """
    config = replace(GenerationConfig.from_env(env), max_output_tokens=max_output_tokens)
    adapter = GoogleGenAIAdapter(config, client_factory=client_factory)

    async def generate(prompt: str) -> str:
        return await asyncio.to_thread(adapter.generate_text, prompt)

    return generate
