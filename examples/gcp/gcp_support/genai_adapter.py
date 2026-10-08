"""Adaptador síncrono injetável; google-genai só é importado no uso real."""

from dataclasses import dataclass
import math
import os
import re
import sys
from typing import Callable, Mapping, Protocol


class ConfigurationError(ValueError):
    pass


class ProviderError(RuntimeError):
    """Falha do cliente; a causa original permanece em __cause__."""


class EmptyResponseError(ProviderError):
    """Resposta sem texto: pode ser bloqueio, saída não textual ou vazia."""


class TextGenerator(Protocol):
    def generate_text(self, prompt: str) -> str: ...


def resolve_model(alias: str, env: Mapping[str, str]) -> str:
    """Alias didático neutro para um ID escolhido fora do código."""
    if alias != "reasoning":
        raise ConfigurationError("Alias de modelo não configurado")
    model = env.get("GOOGLE_GENAI_MODEL", "")
    if not isinstance(model, str) or not model.strip():
        raise ConfigurationError("Variável obrigatória: GOOGLE_GENAI_MODEL")
    return model


@dataclass(frozen=True)
class GenerationConfig:
    project: str
    location: str
    model: str
    timeout_ms: int = 30_000
    max_output_tokens: int = 1024
    temperature: float = 0.2

    def __post_init__(self):
        patterns = {
            "project": r"[a-z][a-z0-9-]{4,28}[a-z0-9]",
            "location": r"(?:global|[a-z][a-z0-9]*(?:-[a-z0-9]+)+)",
            "model": r"[A-Za-z0-9][A-Za-z0-9._-]*",
        }
        for field, pattern in patterns.items():
            value = getattr(self, field)
            if not isinstance(value, str) or not re.fullmatch(pattern, value):
                raise ConfigurationError(f"Configuração inválida: {field}")
        for field in ("timeout_ms", "max_output_tokens"):
            value = getattr(self, field)
            if type(value) is not int or value <= 0:
                raise ConfigurationError(f"Configuração inválida: {field}")
        if (
            type(self.temperature) not in (int, float)
            or not math.isfinite(self.temperature)
            or not 0 <= self.temperature <= 2
        ):
            raise ConfigurationError("Configuração inválida: temperature")

    @classmethod
    def from_env(cls, env: Mapping[str, str] | None = None, alias: str = "reasoning"):
        env = os.environ if env is None else env
        # Seleção explícita do backend empresarial; sem API key ou fallback.
        if env.get("GOOGLE_API_KEY") or env.get("GEMINI_API_KEY"):
            raise ConfigurationError("Este adaptador usa ADC; remova API keys")
        names = ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION")
        values = []
        for name in names:
            value = env.get(name, "")
            if not isinstance(value, str) or not value.strip():
                raise ConfigurationError(f"Variável obrigatória: {name}")
            values.append(value)
        return cls(*values, model=resolve_model(alias, env))


def sdk_client_factory(**kwargs):
    """ADC é resolvida pelo SDK durante o uso do cliente real."""
    if os.environ.get("GOOGLE_API_KEY") or os.environ.get("GEMINI_API_KEY"):
        raise ConfigurationError("Este adaptador usa ADC; remova API keys")
    from google import genai
    return genai.Client(**kwargs)


class GoogleGenAIAdapter:
    def __init__(
        self, config: GenerationConfig,
        client_factory: Callable | None = None,
    ):
        self.config = config
        self._factory = client_factory or sdk_client_factory

    def generate_text(self, prompt: str) -> str:
        if not isinstance(prompt, str) or not prompt.strip():
            raise ValueError("prompt deve conter texto")
        if len(prompt) > 16_000:
            raise ValueError("prompt excede 16000 caracteres")
        client = None
        try:
            client = self._factory(
                enterprise=True,
                project=self.config.project,
                location=self.config.location,
                http_options={
                    "api_version": "v1", "timeout": self.config.timeout_ms,
                    "retry_options": {"attempts": 1},
                },
            )
            response = client.models.generate_content(
                model=self.config.model, contents=prompt,
                config={
                    "temperature": self.config.temperature,
                    "max_output_tokens": self.config.max_output_tokens,
                },
            )
            text = response.text
            if not isinstance(text, str) or not text.strip():
                raise EmptyResponseError("O provedor devolveu resposta sem texto")
            return text
        except EmptyResponseError:
            raise
        except Exception as error:
            raise ProviderError("Falha na geração pelo provedor") from error
        finally:
            if client is not None:
                # Falha de fechamento não substitui uma falha de geração ativa.
                active_error = sys.exc_info()[0] is not None
                try:
                    client.close()
                except Exception as error:
                    if not active_error:
                        raise ProviderError("Falha ao fechar o cliente") from error
