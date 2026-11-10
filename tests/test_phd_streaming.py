from __future__ import annotations

import io
import json
import tempfile
import threading
import unittest
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from phd_agents.providers import ModelReply, ProviderError, invoke_stream
from phd_agents.server import ApiServer
from phd_agents.store import Store
from phd_agents.streaming import StreamFormatError, sse_events


class SSEParserTests(unittest.TestCase):
    def test_events_and_multiline_payload(self) -> None:
        wire = io.BytesIO(b": ping\n\nevent: delta\ndata: {\"text\":\ndata: \"hello\"}\n\n")
        self.assertEqual(list(sse_events(wire)), [("delta", '{"text":\n"hello"}')])

    def test_invalid_utf8_and_oversized_frames_fail(self) -> None:
        with self.assertRaises(StreamFormatError):
            list(sse_events([b"data: \xff\n\n"]))
        with self.assertRaises(StreamFormatError):
            list(sse_events([b"data: " + b"x" * 80 + b"\n\n"], max_event_bytes=50))


class NativeInferenceStreamingTests(unittest.TestCase):
    def test_real_http_provider_sse_preserves_deltas(self) -> None:
        requests: list[dict] = []

        class LocalModel(BaseHTTPRequestHandler):
            def log_message(self, *_: object) -> None:
                return

            def do_POST(self) -> None:
                length = int(self.headers["Content-Length"])
                requests.append(json.loads(self.rfile.read(length)))
                body = (
                    b'data: {"model":"synthetic","choices":[{"delta":{"content":"First "}}]}\n\n'
                    b'data: {"choices":[{"delta":{"content":"second"}}]}\n\n'
                    b'data: {"choices":[],"usage":{"prompt_tokens":14,"completion_tokens":2}}\n\n'
                    b'data: [DONE]\n\n'
                )
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream; charset=utf-8")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                self.wfile.flush()

        server = ThreadingHTTPServer(("127.0.0.1", 0), LocalModel)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            provider = {
                "id": "test_stream", "local": True, "kind": "openai_compatible",
                "base_url": f"http://127.0.0.1:{server.server_port}/v1",
                "model": "synthetic", "api_key_env": "",
                "max_output_tokens": 40, "token_parameter": "max_tokens",
            }
            chunks: list[str] = []
            reply = invoke_stream(provider, "Policy", "Research question", chunks.append, timeout=10)
            self.assertEqual(chunks, ["First ", "second"])
            self.assertEqual(reply.content, "First second")
            self.assertEqual(reply.usage, {"prompt_tokens": 14, "completion_tokens": 2})
            self.assertTrue(requests[0]["stream"])
            self.assertEqual(requests[0]["messages"][0]["role"], "system")
        finally:
            server.shutdown()
            server.server_close()
            thread.join(timeout=5)

    def test_streaming_rejects_unsupported_provider_kind_before_network(self) -> None:
        config = {"id": "anthropic", "kind": "anthropic", "local": False,
                  "base_url": "https://api.anthropic.com", "model": "synthetic", "api_key_env": ""}
        with self.assertRaisesRegex(ProviderError, "unavailable"):
            invoke_stream(config, "Policy", "Prompt", lambda _: None)


class AgentStreamHttpTests(unittest.TestCase):
    def test_agent_stream_contract_preserves_bounded_final_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "private.sqlite3")
            server = ApiServer(("127.0.0.1", 0), store=store, root=Path(tmp))
            worker = threading.Thread(target=server.serve_forever, daemon=True)
            worker.start()
            try:
                def run(*args, **kwargs):
                    kwargs["on_delta"]("Streaming ")
                    kwargs["on_delta"]("evidence")
                    return {"text": "Streaming evidence", "id": "run-test", "agent_id": "portfolio_planner",
                            "status": "proposed", "usage": {"prompt_tokens": 5}}
                url = f"http://127.0.0.1:{server.server_port}/api/agents/stream"
                with patch("phd_agents.server.run_agent", side_effect=run):
                    request = Request(url, json.dumps({"agent_id": "portfolio_planner",
                        "input_text": "Audit recorded deadlines"}).encode(),
                        headers={"Content-Type": "application/json"}, method="POST")
                    with urlopen(request, timeout=5) as response:
                        self.assertEqual(response.status, 200)
                        self.assertIn("text/event-stream", response.headers["Content-Type"])
                        events = list(sse_events(response))
                self.assertEqual([name for name, _ in events], ["status", "delta", "delta", "result", "done"])
                self.assertEqual(json.loads(events[-2][1])["text"], "Streaming evidence")
                with patch("phd_agents.server.run_agent") as call:
                    request = Request(url, json.dumps({"agent_id": "portfolio_planner"}).encode(),
                        headers={"Content-Type": "application/json", "Idempotency-Key": "valid-long-test-key-12345"},
                        method="POST")
                    with self.assertRaises(HTTPError) as error:
                        urlopen(request, timeout=5)
                    self.assertEqual(error.exception.code, 400)
                    call.assert_not_called()
            finally:
                server.shutdown()
                server.server_close()
                worker.join(timeout=5)
                store.close()


if __name__ == "__main__":
    unittest.main()
