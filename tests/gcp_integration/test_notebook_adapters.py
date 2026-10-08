import asyncio
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from examples.gcp.notebook_adapters import build_generation_function
from examples.gcp.gcp_support.genai_adapter import (
    ConfigurationError, EmptyResponseError, ProviderError,
)


ENV = {
    'GOOGLE_CLOUD_PROJECT': 'example-project',
    'GOOGLE_CLOUD_LOCATION': 'global',
    'GOOGLE_GENAI_MODEL': 'configured-model',
}


def fake_client(text='local fake text'):
    client = Mock()
    client.models.generate_content.return_value = SimpleNamespace(text=text)
    return client


class NotebookAdapterTests(unittest.TestCase):
    def test_construction_does_not_create_client(self):
        factory = Mock()
        generate = build_generation_function(ENV, client_factory=factory)
        self.assertTrue(callable(generate))
        factory.assert_not_called()

    def test_prompt_result_and_sdk_contract(self):
        client = fake_client()
        factory = Mock(return_value=client)
        generate = build_generation_function(ENV, client_factory=factory)
        self.assertEqual(asyncio.run(generate('task input')), 'local fake text')
        factory.assert_called_once_with(
            enterprise=True, project='example-project', location='global',
            http_options={'api_version': 'v1', 'timeout': 30000,
                          'retry_options': {'attempts': 1}},
        )
        client.models.generate_content.assert_called_once_with(
            model='configured-model', contents='task input',
            config={'temperature': 0.2, 'max_output_tokens': 512},
        )
        client.close.assert_called_once_with()

    def test_provider_failure_preserves_original_cause(self):
        failure = RuntimeError('fake provider failure')
        client = fake_client()
        client.models.generate_content.side_effect = failure
        generate = build_generation_function(ENV, client_factory=Mock(return_value=client))
        with self.assertRaises(ProviderError) as caught:
            asyncio.run(generate('task input'))
        self.assertIs(caught.exception.__cause__, failure)
        client.close.assert_called_once_with()

    def test_empty_response_is_an_error(self):
        client = fake_client(' ')
        generate = build_generation_function(ENV, client_factory=Mock(return_value=client))
        with self.assertRaises(EmptyResponseError):
            asyncio.run(generate('task input'))
        client.close.assert_called_once_with()

    def test_empty_prompt_does_not_create_client(self):
        factory = Mock()
        generate = build_generation_function(ENV, client_factory=factory)
        with self.assertRaises(ValueError):
            asyncio.run(generate(' '))
        factory.assert_not_called()

    def test_missing_model_and_invalid_token_limit_fail_at_construction(self):
        factory = Mock()
        missing = {k: v for k, v in ENV.items() if k != 'GOOGLE_GENAI_MODEL'}
        with self.assertRaises(ConfigurationError):
            build_generation_function(missing, client_factory=factory)
        with self.assertRaises(ConfigurationError):
            build_generation_function(ENV, client_factory=factory, max_output_tokens=0)
        factory.assert_not_called()


if __name__ == '__main__':
    unittest.main()
