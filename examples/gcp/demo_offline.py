"""Demonstração explícita com cliente falso; sem SDK, ADC ou rede."""
from types import SimpleNamespace
from gcp_support import GenerationConfig, GoogleGenAIAdapter


class FakeModels:
    def generate_content(self, *, model, contents, config):
        return SimpleNamespace(text=f"[RESPOSTA FALSA LOCAL; {model}] {contents}")


class FakeClient:
    models = FakeModels()

    def close(self):
        pass


def main():
    cfg = GenerationConfig.from_env({
        "GOOGLE_CLOUD_PROJECT": "example-project",
        "GOOGLE_CLOUD_LOCATION": "us-central1",
        "GOOGLE_GENAI_MODEL": "fake-model",
    }, alias="reasoning")
    adapter = GoogleGenAIAdapter(cfg, lambda **kwargs: FakeClient())
    print(adapter.generate_text("Explique o contrato de uma porta de geração."))


if __name__ == "__main__":
    main()
