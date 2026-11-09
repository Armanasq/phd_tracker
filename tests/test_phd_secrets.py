from __future__ import annotations

import json
import os
import stat
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch
from urllib.request import Request, urlopen

from phd_agents.secrets import read_secret, secret_path, write_secret
from phd_agents.server import ApiServer
from phd_agents.store import Store


class PrivateCredentialTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.env = patch.dict(os.environ, {"PHDAI_PRIVATE_DIR": self.folder.name,
                                           "OPENAI_API_KEY": ""})
        self.env.start()
        self.addCleanup(self.env.stop)

    def test_atomic_private_write_and_delete(self) -> None:
        write_secret("OPENAI_API_KEY", "synthetic-private-token")
        self.assertEqual(read_secret("OPENAI_API_KEY"), "synthetic-private-token")
        self.assertEqual(stat.S_IMODE(secret_path().stat().st_mode), 0o600)
        self.assertNotIn("synthetic-private-token", str(secret_path().parent))
        write_secret("OPENAI_API_KEY", "")
        self.assertEqual(read_secret("OPENAI_API_KEY"), "")
        self.assertNotIn("OPENAI_API_KEY", json.loads(secret_path().read_text()))

    def test_unsafe_permissions_fail_closed(self) -> None:
        write_secret("OPENAI_API_KEY", "demo")
        secret_path().chmod(0o644)
        with self.assertRaises(PermissionError):
            read_secret("OPENAI_API_KEY")
        with self.assertRaises(PermissionError):
            write_secret("OPENAI_API_KEY", "replacement")
        secret_path().chmod(0o600)

    def test_private_api_does_not_echo_credential(self) -> None:
        store = Store(Path(self.folder.name) / "state.sqlite3")
        server = ApiServer(("127.0.0.1", 0), store=store, root=Path(self.folder.name))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            target = "http://127.0.0.1:" + str(server.server_port) + "/api/providers/credential"
            body = json.dumps({"provider_id": "openai",
                               "credential": "synthetic-not-a-real-api-key"}).encode()
            request = Request(target, data=body, method="POST",
                              headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=4) as response:
                returned = response.read().decode()
                self.assertNotIn("synthetic-not-a-real-api-key", returned)
                self.assertTrue(json.loads(returned)["credential_configured"])
            self.assertEqual(read_secret("OPENAI_API_KEY"), "synthetic-not-a-real-api-key")
        finally:
            server.shutdown()
            thread.join(timeout=4)
            server.server_close()
            store.close()


if __name__ == "__main__":
    unittest.main()
