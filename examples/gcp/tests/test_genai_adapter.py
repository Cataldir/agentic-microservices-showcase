from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

from gcp_support.genai_adapter import (
    ConfigurationError, EmptyResponseError, GenerationConfig,
    GoogleGenAIAdapter, ProviderError, resolve_model, sdk_client_factory,
)


def config(**overrides):
    return GenerationConfig(**dict(
        project="example-project", location="us-central1",
        model="chosen-model-v1", **overrides,
    ))


class ConfigurationTests(unittest.TestCase):
    def test_env_alias_is_resolved(self):
        cfg = GenerationConfig.from_env({
            "GOOGLE_CLOUD_PROJECT": "example-project",
            "GOOGLE_CLOUD_LOCATION": "europe-west1",
            "GOOGLE_GENAI_MODEL": "selected-model",
        }, alias="reasoning")
        self.assertEqual((cfg.project, cfg.location, cfg.model),
                         ("example-project", "europe-west1", "selected-model"))

    def test_no_model_default(self):
        with self.assertRaises(ConfigurationError):
            GenerationConfig.from_env({
                "GOOGLE_CLOUD_PROJECT": "example-project",
                "GOOGLE_CLOUD_LOCATION": "us-central1",
            })

    def test_unknown_alias(self):
        with self.assertRaises(ConfigurationError):
            resolve_model("unmapped", {"GOOGLE_GENAI_MODEL": "some-model"})

    def test_required_project_and_location(self):
        for absent in ("GOOGLE_CLOUD_PROJECT", "GOOGLE_CLOUD_LOCATION"):
            env = dict(GOOGLE_CLOUD_PROJECT="example-project",
                       GOOGLE_CLOUD_LOCATION="global", GOOGLE_GENAI_MODEL="m1")
            env.pop(absent)
            with self.subTest(absent=absent), self.assertRaises(ConfigurationError):
                GenerationConfig.from_env(env)

    def test_global_is_explicitly_allowed(self):
        self.assertEqual(GenerationConfig("example-project", "global", "m1").location, "global")

    def test_syntax_validation_does_not_assert_model_availability(self):
        self.assertEqual(config().model, "chosen-model-v1")
        for value in ("", "bad project", "UPPER", "abc", None):
            with self.subTest(value=value), self.assertRaises(ConfigurationError):
                GenerationConfig(value, "us-central1", "m1")

    def test_invalid_region_and_model(self):
        for location, model in (("bad region", "m1"), ("us-central1", "bad/model"),
                                (None, "m1"), ("us-central1", "")):
            with self.subTest(location=location, model=model), self.assertRaises(ConfigurationError):
                GenerationConfig("example-project", location, model)

    def test_positive_integer_limits(self):
        for field in ("timeout_ms", "max_output_tokens"):
            for value in (True, 0, -1, 1.5, "10"):
                kwargs = {field: value}
                with self.subTest(field=field, value=value), self.assertRaises(ConfigurationError):
                    GenerationConfig("example-project", "global", "m1", **kwargs)

    def test_temperature_is_finite_and_in_range(self):
        for value in (float("nan"), float("inf"), -0.1, 2.1, True, "0.2"):
            with self.subTest(value=value), self.assertRaises(ConfigurationError):
                GenerationConfig("example-project", "global", "m1", temperature=value)

    def test_api_keys_refused_in_env_config(self):
        for key in ("GOOGLE_API_KEY", "GEMINI_API_KEY"):
            with self.subTest(key=key), self.assertRaises(ConfigurationError):
                GenerationConfig.from_env({key: "fake-key"})

    def test_api_keys_refused_before_sdk_import(self):
        with patch.dict("os.environ", {"GOOGLE_API_KEY": "fake-key"}, clear=True):
            with self.assertRaises(ConfigurationError):
                sdk_client_factory()


class AdapterTests(unittest.TestCase):
    def client(self, text="  resposta\n"):
        return SimpleNamespace(models=SimpleNamespace(
            generate_content=Mock(return_value=SimpleNamespace(text=text))), close=Mock())

    def test_reply_and_kwargs(self):
        client = self.client()
        factory = Mock(return_value=client)
        adapter = GoogleGenAIAdapter(config(), factory)
        self.assertEqual(adapter.generate_text("pergunta"), "  resposta\n")
        factory.assert_called_once_with(enterprise=True, project="example-project",
            location="us-central1", http_options={"api_version": "v1", "timeout": 30_000,
                                                 "retry_options": {"attempts": 1}})
        client.models.generate_content.assert_called_once_with(
            model="chosen-model-v1", contents="pergunta",
            config={"temperature": 0.2, "max_output_tokens": 1024})
        client.close.assert_called_once_with()

    def test_invalid_prompt_never_creates_client(self):
        factory = Mock()
        adapter = GoogleGenAIAdapter(config(), factory)
        for prompt in (None, "", "  ", 12, "x" * 16001):
            with self.subTest(prompt_type=type(prompt).__name__), self.assertRaises(ValueError):
                adapter.generate_text(prompt)
        factory.assert_not_called()

    def test_empty_output_is_an_error_and_client_is_closed(self):
        for text in (None, "", "  ", 12):
            client = self.client(text)
            with self.subTest(text=text), self.assertRaises(EmptyResponseError):
                GoogleGenAIAdapter(config(), lambda **kwargs: client).generate_text("q")
            client.close.assert_called_once()

    def test_sdk_failure_preserves_cause(self):
        client = self.client()
        original = RuntimeError("remote failure with sensitive details")
        client.models.generate_content.side_effect = original
        with self.assertRaises(ProviderError) as caught:
            GoogleGenAIAdapter(config(), lambda **kwargs: client).generate_text("q")
        self.assertIs(caught.exception.__cause__, original)
        self.assertNotIn("sensitive", str(caught.exception))
        client.close.assert_called_once()
        client.models.generate_content.assert_called_once()

    def test_adc_or_import_failure_preserves_cause(self):
        error = ImportError("optional SDK absent")
        with self.assertRaises(ProviderError) as caught:
            GoogleGenAIAdapter(config(), Mock(side_effect=error)).generate_text("q")
        self.assertIs(caught.exception.__cause__, error)

    def test_close_failure_does_not_replace_generation_failure(self):
        client = self.client()
        generation_error = RuntimeError("generation")
        client.models.generate_content.side_effect = generation_error
        client.close.side_effect = RuntimeError("close")
        with self.assertRaises(ProviderError) as caught:
            GoogleGenAIAdapter(config(), lambda **kwargs: client).generate_text("q")
        self.assertIs(caught.exception.__cause__, generation_error)

    def test_close_failure_after_success_is_reported(self):
        client = self.client()
        error = RuntimeError("close")
        client.close.side_effect = error
        with self.assertRaises(ProviderError) as caught:
            GoogleGenAIAdapter(config(), lambda **kwargs: client).generate_text("q")
        self.assertIs(caught.exception.__cause__, error)

    def test_import_and_construction_do_not_load_sdk(self):
        factory = Mock()
        with patch("builtins.__import__", side_effect=AssertionError("unexpected import")):
            GoogleGenAIAdapter(config(), factory)
        factory.assert_not_called()
