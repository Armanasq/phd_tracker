from __future__ import annotations

import http.client
import json
import tempfile
import threading
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from phd_agents.catalog import provider_spec
from phd_agents.server import ApiServer
from phd_agents.store import ConflictError, Store


class AtomicApplicationTests(unittest.TestCase):
    def test_concurrent_update_has_exactly_one_winner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.sqlite3"
            first, second = Store(path), Store(path)
            try:
                first.update_application("APP-1", {"notes": "initial"}, 0)
                original = Store.get_application
                barrier = threading.Barrier(2)

                def synchronized_read(store: Store, identity: str) -> dict:
                    value = original(store, identity)
                    if identity == "APP-1":
                        barrier.wait(timeout=4)
                    return value

                def update(store: Store, note: str) -> str:
                    try:
                        store.update_application("APP-1", {"notes": note}, 1)
                        return "saved"
                    except ConflictError:
                        return "conflict"

                with patch.object(Store, "get_application", synchronized_read):
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        a = pool.submit(update, first, "alpha")
                        b = pool.submit(update, second, "beta")
                        outcomes = sorted([a.result(timeout=8), b.result(timeout=8)])
                self.assertEqual(outcomes, ["conflict", "saved"])
                latest = first.get_application("APP-1")
                self.assertEqual(latest["version"], 2)
                self.assertIn(latest["notes"], {"alpha", "beta"})
                self.assertEqual(
                    sum(item["action"] == "application:update" for item in first.activity()), 2
                )
            finally:
                first.close()
                second.close()

    def test_first_insert_conflict_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            first, second = Store(Path(tmp) / "state.sqlite3"), Store(Path(tmp) / "state.sqlite3")
            barrier = threading.Barrier(2)
            original = Store.get_application

            def synchronized_read(store: Store, identity: str) -> dict:
                value = original(store, identity)
                if identity == "NEW":
                    barrier.wait(timeout=4)
                return value

            def update(store: Store) -> str:
                try:
                    store.update_application("NEW", {"notes": "ready"}, 0)
                    return "saved"
                except ConflictError:
                    return "conflict"

            try:
                with patch.object(Store, "get_application", synchronized_read):
                    with ThreadPoolExecutor(max_workers=2) as pool:
                        outcomes = [pool.submit(update, s) for s in (first, second)]
                        self.assertEqual(
                            sorted(f.result(timeout=8) for f in outcomes), ["conflict", "saved"]
                        )
                self.assertEqual(first.get_application("NEW")["version"], 1)
            finally:
                first.close()
                second.close()

    def test_document_states_must_have_text_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            store = Store(Path(tmp) / "state.sqlite3")
            try:
                for state in ({3: "ready"}, {"x": []}, {"": "ready"}):
                    with self.subTest(state=state), self.assertRaises(ValueError):
                        store.update_application("A", {"document_states": state}, 0)
            finally:
                store.close()


class ProviderCredentialPolicyTests(unittest.TestCase):
    def test_custom_credentials_cannot_reuse_runtime_token(self) -> None:
        values = {
            "id": "example_gateway", "kind": "openai_compatible",
            "base_url": "https://api.example.org/v1", "model": "model",
            "local": False,
        }
        for env in ("PHDAI_API_TOKEN", "AWS_SECRET_ACCESS_KEY", "GITHUB_TOKEN"):
            with self.subTest(env=env), self.assertRaises(ValueError):
                provider_spec({**values, "api_key_env": env})
        self.assertEqual(
            provider_spec({**values, "api_key_env": "EXAMPLE_GATEWAY_API_KEY"})["api_key_env"],
            "EXAMPLE_GATEWAY_API_KEY",
        )


class HttpBoundaryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.store = Store(Path(self.temp.name) / "state.sqlite3")
        self.server = ApiServer(("127.0.0.1", 0), store=self.store, root=Path(self.temp.name))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.store.close)
        self.addCleanup(self.server.server_close)
        self.addCleanup(self.thread.join, 5)
        self.addCleanup(self.server.shutdown)

    def _status(self, host: str, origin: str | None = None) -> int:
        connection = http.client.HTTPConnection("127.0.0.1", self.server.server_port, timeout=3)
        try:
            connection.putrequest("GET", "/api/health", skip_host=True)
            connection.putheader("Host", host)
            if origin is not None:
                connection.putheader("Origin", origin)
            connection.endheaders()
            result = connection.getresponse()
            result.read()
            return result.status
        finally:
            connection.close()

    def test_host_and_origin_require_exact_local_port(self) -> None:
        port = self.server.server_port
        self.assertEqual(self._status(f"127.0.0.1:{port}"), 200)
        self.assertEqual(self._status(f"localhost:{port}"), 200)
        self.assertEqual(self._status(f"127.0.0.1:{port+1}"), 403)
        self.assertEqual(self._status(f"evil.example:{port}"), 403)
        self.assertEqual(self._status(f"127.0.0.1:{port}", "https://example.org"), 403)
        self.assertEqual(self._status(f"localhost:{port}", f"http://localhost:{port}"), 200)
        self.assertEqual(self._status(f"localhost:{port}", f"http://localhost:{port+1}"), 403)

    def test_rejects_ambiguous_transfer_framing(self) -> None:
        port = self.server.server_port
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=3)
        try:
            connection.putrequest("POST", "/api/settings")
            connection.putheader("Content-Type", "application/json")
            connection.putheader("Content-Length", "2")
            connection.putheader("Content-Length", "2")
            connection.endheaders(b"{}")
            response = connection.getresponse()
            self.assertEqual(response.status, 400)
            self.assertIn("Content-Length", response.read().decode())
        finally:
            connection.close()


if __name__ == "__main__":
    unittest.main()
