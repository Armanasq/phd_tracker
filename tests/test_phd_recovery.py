from __future__ import annotations

import hashlib
import json
import sqlite3
import stat
import tempfile
import threading
import unittest
from pathlib import Path
from urllib.request import Request, urlopen

from phd_agents.server import ApiServer
from phd_agents.store import Store


class LocalRecoveryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / "state.sqlite3"
        self.store = Store(self.path)
        self.addCleanup(self.store.close)

    def test_online_backup_is_consistent_private_and_retained(self) -> None:
        self.store.update_application("A", {"notes": "private state"}, 0)
        first = self.store.create_backup(retain=1)
        directory = Path(first["directory"])
        target = directory / first["filename"]
        self.assertTrue(target.is_file())
        self.assertEqual(first["integrity"], "ok")
        self.assertEqual(first["includes_credentials"], False)
        self.assertEqual(stat.S_IMODE(target.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(directory.stat().st_mode), 0o700)
        self.assertEqual(hashlib.sha256(target.read_bytes()).hexdigest(), first["sha256"])
        with sqlite3.connect(target) as database:
            self.assertEqual(database.execute("PRAGMA quick_check(1)").fetchone()[0], "ok")
            self.assertEqual(database.execute("SELECT version FROM applications WHERE id='A'").fetchone()[0], 1)
        self.store.update_application("A", {"notes": "updated"}, 1)
        second = self.store.create_backup(retain=1)
        self.assertEqual(second["retained"], 1)
        self.assertFalse(target.exists())
        with sqlite3.connect(directory / second["filename"]) as database:
            row = database.execute("SELECT payload FROM applications WHERE id='A'").fetchone()[0]
            self.assertEqual(json.loads(row)["notes"], "updated")
        diagnostic = self.store.diagnostics()
        self.assertEqual(diagnostic["status"], "ok")
        self.assertEqual(diagnostic["backups"]["count"], 1)
        self.assertEqual(diagnostic["database"]["private_file_mode"], "0o600")

    def test_unsafe_legacy_file_or_symlink_is_rejected(self) -> None:
        self.store.close()
        self.path.chmod(0o644)
        with self.assertRaises(PermissionError):
            Store(self.path)
        self.path.chmod(0o600)
        alias = self.path.parent / "alias.sqlite3"
        alias.symlink_to(self.path)
        with self.assertRaises(PermissionError):
            Store(alias)

    def test_backup_input_is_validated(self) -> None:
        for amount in (0, 31, 3.5, True, "7"):
            with self.subTest(amount=amount), self.assertRaises(ValueError):
                self.store.create_backup(retain=amount)

    def test_runtime_backup_endpoint_and_diagnostics(self) -> None:
        server = ApiServer(("127.0.0.1", 0), store=self.store, root=Path(self.temp.name))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_port}"
        try:
            with urlopen(base + "/api/diagnostics", timeout=4) as response:
                diagnostic = json.load(response)
            self.assertEqual(diagnostic["status"], "ok")
            self.assertNotIn("private state", json.dumps(diagnostic))
            payload = json.dumps({"retain": 3}).encode("utf-8")
            request = Request(base + "/api/maintenance/backup", data=payload, method="POST",
                              headers={"Content-Type": "application/json"})
            with urlopen(request, timeout=4) as response:
                backup = json.load(response)["backup"]
            self.assertTrue((Path(backup["directory"]) / backup["filename"]).is_file())
            self.assertNotIn("private state", json.dumps(backup))
        finally:
            server.shutdown()
            thread.join(timeout=4)
            server.server_close()


if __name__ == "__main__":
    unittest.main()
