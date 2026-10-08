"""Runtime HTTP mínimo: health e geração; nenhuma conexão ao importar."""

import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer

from .genai_adapter import (
    EmptyResponseError, GenerationConfig, GoogleGenAIAdapter, ProviderError,
)

MAX_BODY_BYTES = 65_536


def route(method, path, body, generator):
    """Contrato puro de request/response; testes não abrem sockets."""
    if method == "GET" and path == "/healthz":
        return 200, {"status": "ready"}
    if path != "/generate":
        return 404, {"error": "not_found"}
    if method != "POST":
        return 405, {"error": "method_not_allowed"}
    if len(body) > MAX_BODY_BYTES:
        return 413, {"error": "body_too_large"}
    try:
        data = json.loads(body)
        if not isinstance(data, dict) or set(data) != {"prompt"}:
            return 400, {"error": "invalid_request"}
        return 200, {"text": generator.generate_text(data["prompt"])}
    except (ValueError, UnicodeDecodeError):
        return 400, {"error": "invalid_request"}
    except EmptyResponseError:
        return 502, {"error": "empty_provider_response"}
    except ProviderError:
        return 502, {"error": "provider_failure"}


def make_handler(generator):
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._handle()

        def do_POST(self):
            self._handle()

        def _handle(self):
            # Sem chunked body: este exemplo requer Content-Length no POST.
            if self.headers.get("Transfer-Encoding"):
                self._reply(400, {"error": "invalid_request"})
                return
            if self.command == "POST" and self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                self._reply(415, {"error": "unsupported_media_type"})
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self._reply(400, {"error": "invalid_request"})
                return
            if length < 0:
                self._reply(400, {"error": "invalid_request"})
                return
            if length > MAX_BODY_BYTES:
                self._reply(413, {"error": "body_too_large"})
                return
            body = self.rfile.read(length)
            status, result = route(self.command, self.path, body, generator)
            self._reply(status, result)

        def _reply(self, status, result):
            raw = json.dumps(result, ensure_ascii=False).encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        def log_message(self, format, *args):
            # Somente status/rota do servidor; não há log de prompt ou resposta.
            return

    return Handler


def main():
    config = GenerationConfig.from_env()
    port = int(os.environ.get("PORT", "8080"))
    if not 1 <= port <= 65535:
        raise ValueError("PORT inválido")
    generator = GoogleGenAIAdapter(config)
    # Cloud Run requer 0.0.0.0:PORT; TLS e autenticação ficam na plataforma.
    with HTTPServer(("0.0.0.0", port), make_handler(generator)) as server:
        server.serve_forever()


if __name__ == "__main__":
    main()
