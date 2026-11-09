from __future__ import annotations

import hashlib
import os
import sqlite3
import stat
import tempfile
import unittest
from pathlib import Path

from phd_agents.recovery import restore_backup, runtime_lock, verify_backup
from phd_agents.store import ConflictError, Store


@unittest.skipUnless(os.name == "posix", "Offline restore uses POSIX advisory locks")
class VerifiedRestoreTests(unittest.TestCase):
    def setUp(self) -> None:
        self.folder = tempfile.TemporaryDirectory()
        self.addCleanup(self.folder.cleanup)
        self.path = Path(self.folder.name) / "state.sqlite3"

    def test_restores_verified_backup_and_preserves_previous_private_state(self) -> None:
        store = Store(self.path)
        try:
            store.update_application("APP-1", {"notes": "before"}, 0)
            report = store.create_backup()
            store.update_application("APP-1", {"notes": "after"}, 1)
        finally:
            store.close()
        inspected = verify_backup(report["filename"], state_path=self.path, sha256=report["sha256"])
        self.assertEqual(inspected["integrity"], "ok")
        self.assertEqual(inspected["sha256"], report["sha256"])
        restored = restore_backup(
            report["filename"], state_path=self.path, sha256=report["sha256"], confirm=True,
        )
        self.assertTrue(restored["restored"])
        self.assertFalse(restored["credentials_restored"])
        self.assertTrue(restored["restart_required"])
        self.assertIsNotNone(restored["previous_state"])
        self.assertEqual(stat.S_IMODE(self.path.stat().st_mode), 0o600)
        reopened = Store(self.path)
        try:
            self.assertEqual(reopened.get_application("APP-1")["notes"], "before")
        finally:
            reopened.close()

    def test_actual_data_round_trip_and_preserved_safety_copy(self) -> None:
        state = Store(self.path)
        state.update_application("P", {"notes": "old"}, 0)
        entry = state.create_backup()
        state.update_application("P", {"notes": "new"}, 1)
        state.close()
        result = restore_backup(entry["filename"], state_path=self.path, confirm=True)
        current = Store(self.path)
        try:
            self.assertEqual(current.get_application("P")["notes"], "old")
        finally:
            current.close()
        old = verify_backup(result["previous_state"], state_path=self.path)
        self.assertEqual(old["integrity"], "ok")
        with sqlite3.connect(self.path.parent / "backups" / result["previous_state"]) as database:
            saved = database.execute("SELECT payload FROM applications WHERE id='P'").fetchone()[0]
        self.assertIn('"new"', saved)
        restored_state = Store(self.path)
        try:
            rotated = restored_state.create_backup(retain=1)
            self.assertEqual(rotated["retained"], 1)
        finally:
            restored_state.close()
        self.assertTrue((self.path.parent / "backups" / result["previous_state"]).is_file())
        self.assertEqual(
            verify_backup(result["previous_state"], state_path=self.path)["integrity"], "ok"
        )

    def test_requires_confirmation_and_matching_hash(self) -> None:
        state = Store(self.path)
        entry = state.create_backup()
        state.close()
        with self.assertRaises(PermissionError):
            restore_backup(entry["filename"], state_path=self.path)
        with self.assertRaises(ValueError):
            verify_backup(entry["filename"], state_path=self.path, sha256="0" * 64)
        with self.assertRaises(ValueError):
            verify_backup("../" + entry["filename"], state_path=self.path)

    def test_refuses_active_runtime_and_journal_sidecars(self) -> None:
        state = Store(self.path)
        entry = state.create_backup()
        state.close()
        with runtime_lock(self.path):
            with self.assertRaises(ConflictError):
                restore_backup(entry["filename"], state_path=self.path, confirm=True)
        marker = Path(str(self.path) + "-wal")
        marker.touch()
        with self.assertRaises(ConflictError):
            restore_backup(entry["filename"], state_path=self.path, confirm=True)
        marker.unlink()

    def test_rejects_corrupt_and_unsafe_backup(self) -> None:
        state = Store(self.path)
        entry = state.create_backup()
        state.close()
        directory = self.path.parent / "backups"
        forged = "phd-atlas-20261109T220000Z-0123456789.sqlite3"
        (directory / forged).write_text("not a SQLite database")
        (directory / forged).chmod(0o600)
        with self.assertRaises(ValueError):
            verify_backup(forged, state_path=self.path)
        actual = directory / entry["filename"]
        actual.chmod(0o644)
        with self.assertRaises(PermissionError):
            restore_backup(entry["filename"], state_path=self.path, confirm=True)
        actual.chmod(0o600)
        alias = directory / "phd-atlas-20261109T230000Z-0123456789.sqlite3"
        alias.symlink_to(actual)
        with self.assertRaises(ValueError):
            verify_backup(alias.name, state_path=self.path)


if __name__ == "__main__":
    unittest.main()
