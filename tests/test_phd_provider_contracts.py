from __future__ import annotations

import io
import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.parse import urlsplit

from phd_agents.catalog import PROVIDERS
from phd_agents.providers import ProviderError, invoke, invoke_stream


class StubResponse(io.BytesIO):
    def __init__(self, data: bytes, *, content_type: str = "application/json") -> None:
        super().__init__(data)
        self.headers = {"Content-Type": content_type}


class FakeOpener:
    def __init__(self, body: object, *, streaming: bool = False,
                 code: int | None = None) -> None:
        self.body = body
        self.streaming = streaming
        self.code = code
        self.calls = []

    def open(self, request, timeout: int):
        self.calls.append((request, timeout))
        if self.code is not None:
            raise HTTPError(request.full_url, self.code, "Synthetic failure", None,
                            io.BytesIO(b"DO_NOT_SURFACE_REMOTE_ERROR"))
        body = self.body
        if isinstance(body, dict):
            body = json.dumps(body).encode()
        return StubResponse(body, content_type="text/event-stream" if self.streaming else "application/json")


def provider(identity: str) -> dict:
    return next(dict(item) for item in PROVIDERS if item["id"] == identity)


class ProviderContractMatrixTests(unittest.TestCase):
    def send(self, name: str, body: object, *, streaming: bool = False,
             error_code: int | None = None):
        config = provider(name)
        fake = FakeOpener(body, streaming=streaming, code=error_code)
        with patch("phd_agents.providers.read_secret", return_value="SYNTHETIC_PRIVATE_KEY"), patch(
            "phd_agents.providers.build_opener", return_value=fake
        ) as transport:
            if streaming:
                deltas = []
                outcome = invoke_stream(config, "System contract", "Prompt contract",
                                        deltas.append, timeout=13)
            else:
                outcome = invoke(config, "System contract", "Prompt contract", timeout=13)
                deltas = []
        self.assertEqual(len(fake.calls), 1)
        self.assertEqual(fake.calls[0][1], 13)
        self.assertEqual(outcome.provider_id, name)
        self.assertEqual(transport.call_count, 1)
        return fake.calls[0][0], outcome, deltas

    def test_openai_and_local_chat_contracts(self) -> None:
        body = {"model": "synthetic", "choices": [{"message": {"content": "Traceable response"}}],
                "usage": {"prompt_tokens": 40, "completion_tokens": 2}}
        for name in ("openai", "ollama", "vllm", "lmstudio", "gemini", "openrouter", "groq"):
            with self.subTest(provider=name):
                request, reply, _ = self.send(name, body)
                payload = json.loads(request.data)
                self.assertTrue(request.full_url.endswith("/chat/completions"))
                self.assertEqual(payload["messages"][0], {"role": "system", "content": "System contract"})
                self.assertEqual(payload["messages"][1]["content"], "Prompt contract")
                self.assertEqual(payload["stream"], False)
                self.assertEqual(reply.content, "Traceable response")
                self.assertEqual(reply.usage["prompt_tokens"], 40)
                headers = {k.lower(): v for k, v in request.header_items()}
                if provider(name)["api_key_env"]:
                    self.assertEqual(headers.get("authorization"), "Bearer SYNTHETIC_PRIVATE_KEY")

    def test_azure_versioned_deployment_and_v1_contract(self) -> None:
        message = {"choices": [{"message": {"content": "Azure synthetic"}}],
                   "usage": {"prompt_tokens": 8, "completion_tokens": 3}}
        for name in ("azure", "azure_deploy"):
            with self.subTest(provider=name):
                request, reply, _ = self.send(name, message)
                parsed = urlsplit(request.full_url)
                headers = {k.lower(): v for k, v in request.header_items()}
                self.assertEqual(headers["api-key"], "SYNTHETIC_PRIVATE_KEY")
                self.assertNotIn("authorization", headers)
                data = json.loads(request.data)
                self.assertIn("max_completion_tokens", data)
                self.assertEqual(reply.content, "Azure synthetic")
                if name == "azure_deploy":
                    self.assertIn("/openai/deployments/model-router/chat/completions", parsed.path)
                    self.assertEqual(parsed.query, "api-version=2024-10-21")
                else:
                    self.assertEqual(parsed.query, "")
                    self.assertIn("/openai/v1/chat/completions", parsed.path)

    def test_anthropic_native_messages_contract(self) -> None:
        message = {"model": "synthetic-claude",
                   "content": [{"type": "text", "text": "Part A"}, {"type": "text", "text": "Part B"}],
                   "usage": {"input_tokens": 14, "output_tokens": 10}}
        request, reply, _ = self.send("anthropic", message)
        self.assertEqual(urlsplit(request.full_url).path, "/v1/messages")
        payload = json.loads(request.data)
        headers = {k.lower(): v for k, v in request.header_items()}
        self.assertEqual(headers["anthropic-version"], "2023-06-01")
        self.assertEqual(headers["x-api-key"], "SYNTHETIC_PRIVATE_KEY")
        self.assertEqual(payload["system"], "System contract")
        self.assertNotIn("stream", payload)
        self.assertEqual(reply.content, "Part A\nPart B")
        self.assertEqual(reply.usage, {"input_tokens": 14, "output_tokens": 10})

    def test_native_openai_azure_sse_is_not_simulated(self) -> None:
        body = (b'data: {"choices":[{"delta":{"content":"Direct "}}]}\n\n'
                b'data: {"choices":[{"delta":{"content":"stream"}}]}\n\n'
                b'data: {"choices":[],"usage":{"prompt_tokens":8,"completion_tokens":2}}\n\n'
                b'data: [DONE]\n\n')
        for name in ("ollama", "openai", "azure_deploy"):
            with self.subTest(provider=name):
                request, reply, deltas = self.send(name, body, streaming=True)
                self.assertEqual(deltas, ["Direct ", "stream"])
                self.assertEqual(reply.content, "Direct stream")
                self.assertTrue(json.loads(request.data)["stream"])
                self.assertEqual(reply.usage["completion_tokens"], 2)

    def test_oversized_model_text_is_rejected_not_silently_truncated(self) -> None:
        body = {"choices": [{"message": {"content": "x" * 20001}}]}
        fake = FakeOpener(body)
        with patch("phd_agents.providers.read_secret", return_value="SYNTHETIC_PRIVATE_KEY"), patch(
            "phd_agents.providers.build_opener", return_value=fake
        ):
            with self.assertRaisesRegex(ProviderError, "text limit"):
                invoke(provider("ollama"), "Policy", "Question")

    def test_invalid_choices_usage_and_sensitive_http_errors(self) -> None:
        with self.assertRaisesRegex(ProviderError, "Malformed"):
            self.send("ollama", {"choices": []})
        bad_usage = {"choices": [{"message": {"content": "safe"}}],
                     "usage": {"prompt_tokens": True, "completion_tokens": -2, "output_tokens": 7.4}}
        _, outcome, _ = self.send("ollama", bad_usage)
        self.assertEqual(outcome.usage, {})
        fake = FakeOpener({}, code=429)
        with patch("phd_agents.providers.read_secret", return_value="SYNTHETIC_PRIVATE_KEY"), patch(
            "phd_agents.providers.build_opener", return_value=fake
        ):
            with self.assertRaisesRegex(ProviderError, "HTTP 429") as caught:
                invoke(provider("openai"), "Policy", "Question")
        self.assertNotIn("DO_NOT_SURFACE", str(caught.exception))

    def test_bound_credential_rejects_attacker_before_transport(self) -> None:
        config = provider("openai")
        config["base_url"] = "https://api.openai.com.evil.example/v1"
        with patch("phd_agents.providers.build_opener") as transport:
            with self.assertRaisesRegex(ValueError, "official provider host"):
                invoke(config, "Policy", "Question")
            transport.assert_not_called()


if __name__ == "__main__":
    unittest.main()
