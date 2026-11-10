from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from phd_agents.server import serve
from phd_agents.store import Store


class NativePrivateRuntimeTests(unittest.TestCase):
    def test_non_posix_store_refuses_to_create_uncoordinated_state(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            target = Path(folder) / "unsafe.sqlite3"
            with patch("phd_agents.store.os", SimpleNamespace(name="nt")):
                with self.assertRaisesRegex(RuntimeError, "POSIX owner-only"):
                    Store(target)
            self.assertFalse(target.exists())

    def test_non_posix_private_server_fails_before_snapshot_or_locks(self) -> None:
        with tempfile.TemporaryDirectory() as folder:
            with patch("phd_agents.server.os", SimpleNamespace(name="nt")):
                with patch("phd_agents.server.runtime_lock") as lock:
                    with patch("phd_agents.server.prepare_public_snapshot") as snapshot:
                        with self.assertRaisesRegex(RuntimeError, "requires POSIX"):
                            serve(root=Path(folder))
                        lock.assert_not_called()
                        snapshot.assert_not_called()


if __name__ == "__main__":
    unittest.main()
