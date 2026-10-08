import io
import json
import unittest
from unittest.mock import Mock

from gcp_support.genai_adapter import EmptyResponseError, ProviderError
from gcp_support.http_service import MAX_BODY_BYTES, make_handler, route


class RouteTests(unittest.TestCase):
    def setUp(self):
        self.generator = Mock()
        self.generator.generate_text.return_value = "resultado"

    def test_health_does_not_invoke_provider(self):
        self.assertEqual(route("GET", "/healthz", b"", self.generator),
                         (200, {"status": "ready"}))
        self.generator.generate_text.assert_not_called()

    def test_success(self):
        status, body = route("POST", "/generate", b'{"prompt":"q"}', self.generator)
        self.assertEqual((status, body), (200, {"text": "resultado"}))
        self.generator.generate_text.assert_called_once_with("q")

    def test_invalid_json_and_shape(self):
        for body in (b"bad", b"[]", b"null", b"{}", b'{"prompt":"q","extra":1}', b"\xff"):
            with self.subTest(body=body):
                self.assertEqual(route("POST", "/generate", body, self.generator)[0], 400)
        self.generator.generate_text.assert_not_called()

    def test_prompt_validation_returns_400(self):
        self.generator.generate_text.side_effect = ValueError("invalid")
        self.assertEqual(route("POST", "/generate", b'{"prompt":null}', self.generator)[0], 400)

    def test_unknown_endpoint_and_method(self):
        self.assertEqual(route("GET", "/unknown", b"", self.generator)[0], 404)
        self.assertEqual(route("GET", "/generate", b"", self.generator)[0], 405)
        self.generator.generate_text.assert_not_called()

    def test_oversized_body_refused_before_provider(self):
        self.assertEqual(route("POST", "/generate", b"x" * (MAX_BODY_BYTES + 1), self.generator)[0], 413)
        self.generator.generate_text.assert_not_called()

    def test_provider_failure_redacted(self):
        self.generator.generate_text.side_effect = ProviderError("secret text")
        self.assertEqual(route("POST", "/generate", b'{"prompt":"q"}', self.generator),
                         (502, {"error": "provider_failure"}))

    def test_empty_reply_has_distinct_error(self):
        self.generator.generate_text.side_effect = EmptyResponseError("empty")
        self.assertEqual(route("POST", "/generate", b'{"prompt":"q"}', self.generator),
                         (502, {"error": "empty_provider_response"}))


class HandlerTests(unittest.TestCase):
    def request(self, headers, body=b"", method="POST", path="/generate"):
        generator = Mock()
        generator.generate_text.return_value = "ação"
        handler = object.__new__(make_handler(generator))
        handler.command, handler.path, handler.headers = method, path, headers
        handler.rfile, handler.wfile = io.BytesIO(body), io.BytesIO()
        handler.send_response, handler.send_header, handler.end_headers = Mock(), Mock(), Mock()
        handler._handle()
        status = handler.send_response.call_args.args[0]
        return status, json.loads(handler.wfile.getvalue()), generator, handler

    def test_json_content_type_with_charset(self):
        body = b'{"prompt":"q"}'
        status, result, generator, handler = self.request({
            "Content-Type": "application/json; charset=utf-8", "Content-Length": str(len(body)),
        }, body)
        self.assertEqual((status, result), (200, {"text": "ação"}))
        handler.send_header.assert_any_call("Content-Length", str(len(handler.wfile.getvalue())))

    def test_media_type_required(self):
        status, result, generator, handler = self.request({"Content-Type": "text/plain"})
        self.assertEqual(status, 415)
        generator.generate_text.assert_not_called()

    def test_invalid_length(self):
        for value in ("abc", "-1"):
            with self.subTest(value=value):
                status, _, generator, _ = self.request({"Content-Type": "application/json", "Content-Length": value})
                self.assertEqual(status, 400)
                generator.generate_text.assert_not_called()

    def test_large_body_is_not_read(self):
        status, _, generator, handler = self.request({"Content-Type": "application/json", "Content-Length": "65537"}, b"not read")
        self.assertEqual(status, 413)
        self.assertEqual(handler.rfile.tell(), 0)
        generator.generate_text.assert_not_called()

    def test_chunked_body_refused(self):
        status, _, generator, _ = self.request({"Transfer-Encoding": "chunked"})
        self.assertEqual(status, 400)
        generator.generate_text.assert_not_called()

    def test_missing_length_cannot_invoke_generator(self):
        status, _, generator, _ = self.request({"Content-Type": "application/json"})
        self.assertEqual(status, 400)
        generator.generate_text.assert_not_called()
