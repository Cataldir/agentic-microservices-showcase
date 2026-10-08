"""Portas e adaptadores GCP; importar este pacote não acessa rede ou ADC."""

from .genai_adapter import (
    ConfigurationError, EmptyResponseError, GenerationConfig,
    GoogleGenAIAdapter, ProviderError, TextGenerator, resolve_model,
)

__all__ = [
    "ConfigurationError", "EmptyResponseError", "GenerationConfig",
    "GoogleGenAIAdapter", "ProviderError", "TextGenerator", "resolve_model",
]
