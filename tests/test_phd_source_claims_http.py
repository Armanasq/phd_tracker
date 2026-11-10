from __future__ import annotations

import hashlib
import json
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from phd_agents.server import ApiServer
from phd_agents.source_observer import observe_record
from phd_agents.source_text import extract_visible_text
from phd_agents.store import Store


class SourceClaimHttpTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        root = Path(temp.name)
        self.store = Store(root / "state.sqlite3")
        self.addCleanup(self.store.close)
        self.url = "https://university.example/doctoral"
        text = "Doctoral applications close on 15 December 2026."
        self.raw = text.encode("utf-8")
        self.observation = observe_record(
            self.store, "APP1", self.url,
            fetcher=lambda _: {
                "status": "fetched", "http_status": 200,
                "content_length": len(self.raw),
                "content_sha256": hashlib.sha256(self.raw).hexdigest(),
                **extract_visible_text(self.raw, "text/plain"),
            },
        )
        server = ApiServer(("127.0.0.1", 0), store=self.store, root=root)
        self.server = server
        self.thread = threading.Thread(target=server.serve_forever, daemon=True)
        self.thread.start()
        self.addCleanup(self.stop)
        self.base = f"http://127.0.0.1:{server.server_port}"

    def stop(self) -> None:
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)

    def call(self, route: str, payload: dict | None = None, origin: str | None = None) -> tuple[int, dict]:
        headers = {"Content-Type": "application/json"} if payload is not None else {}
        if origin:
            headers["Origin"] = origin
        request = Request(self.base + route,
                          data=json.dumps(payload).encode("utf-8") if payload is not None else None,
                          headers=headers,
                          method="POST" if payload is not None else "GET")
        try:
            with urlopen(request, timeout=5) as response:
                return response.status, json.load(response)
        except HTTPError as error:
            return error.code, json.load(error)

    def test_private_excerpt_and_source_claim_roundtrip(self) -> None:
        status, value = self.call(f"/api/source-observations/{self.observation['id']}/text")
        self.assertEqual(status, 200)
        self.assertEqual(value["observation"]["visible_text"], "Doctoral applications close on 15 December 2026.")
        status, captured = self.call("/api/source-claims/capture", {
            "observation_id": self.observation["id"], "claim_type": "deadline",
            "quote": "Doctoral applications close on 15 December 2026.",
            "candidate_value": "2026-12-15", "expected_digest": self.observation["content_sha256"],
        })
        self.assertEqual(status, 201)
        self.assertEqual(captured["claim"]["verification"], "source_quote_observed_not_fact_verified")
        _, result = self.call("/api/source-claims")
        self.assertEqual(len(result["claims"]), 1)
        self.assertEqual(result["claims"][0]["source_digest"], self.observation["content_sha256"])
        self.assertEqual(self.store.list_applications(), {})

    def test_cannot_forge_claim_or_use_cross_origin(self) -> None:
        data = {
            "observation_id": self.observation["id"], "claim_type": "deadline",
            "quote": "A fabricated deadline not actually present on the source.",
            "candidate_value": "2026-12-15", "expected_digest": self.observation["content_sha256"],
        }
        self.assertEqual(self.call("/api/source-claims/capture", data)[0], 400)
        data["quote"] = "Doctoral applications close on 15 December 2026."
        data["expected_digest"] = "0" * 64
        self.assertEqual(self.call("/api/source-claims/capture", data)[0], 400)
        data["expected_digest"] = self.observation["content_sha256"]
        self.assertEqual(self.call("/api/source-claims/capture", data, origin="https://attacker.example")[0], 403)
        self.assertEqual(self.call("/api/source-claims")[1]["claims"], [])


if __name__ == "__main__":
    unittest.main()
