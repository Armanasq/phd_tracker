from __future__ import annotations

import importlib.util
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from phd_agents import recovery_encrypted

from phd_agents.recovery_encrypted import drill_encrypted_backup, export_encrypted_backup, restore_encrypted_backup
from phd_agents.store import ConflictError, Store


@unittest.skipUnless(os.name == "posix" and importlib.util.find_spec("cryptography"),
                     "AES-GCM restore drill requires POSIX permissions and cryptography")
class EncryptedBackupDrillTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.state = self.root / "private" / "state.sqlite3"
        self.state.parent.mkdir(mode=0o700)
        self.checkout = self.root / "repository"
        self.checkout.mkdir()
        self.output = self.root / "offsite-staging.enc"
        self.passphrase = "A long high-entropy synthetic backup phrase 2019 !"

    def make_backup(self):
        store = Store(self.state)
        try:
            store.update_application("APP1", {"notes": "Private data sample"}, 0)
            backup = store.create_backup()
            store.update_application("APP1", {"notes": "Current live data"}, 1)
        finally:
            store.close()
        return backup

    def test_cryptographic_round_trip_private_permissions_and_live_state(self):
        backup = self.make_backup()
        exported = export_encrypted_backup(
            backup["filename"], self.output, self.passphrase,
            state_path=self.state, sha256=backup["sha256"], repo_root=self.checkout,
        )
        self.assertTrue(exported["encrypted"])
        self.assertFalse(exported["off_host_copy_completed"])
        self.assertEqual(stat.S_IMODE(self.output.stat().st_mode), 0o600)
        self.assertNotIn(b"SQLite format 3", self.output.read_bytes())
        self.assertNotIn(b"Private data sample", self.output.read_bytes())
        result = drill_encrypted_backup(
            self.output, self.passphrase, sha256=backup["sha256"],
        )
        self.assertEqual(result["drill"], "passed")
        self.assertFalse(result["off_host_copy_verified"])
        self.assertFalse(result["provider_credentials_restored"])
        original = Store(self.state)
        try:
            self.assertEqual(original.get_application("APP1")["notes"], "Current live data")
        finally:
            original.close()

    def test_wrong_passphrase_and_tampered_archive_fail_authentication(self):
        backup = self.make_backup()
        export_encrypted_backup(
            backup["filename"], self.output, self.passphrase,
            state_path=self.state, repo_root=self.checkout,
        )
        with self.assertRaisesRegex(ValueError, "authentication failed"):
            drill_encrypted_backup(self.output, "Another safe-but-incorrect passphrase 456", sha256=backup["sha256"])
        data = bytearray(self.output.read_bytes())
        data[45] ^= 0x80
        self.output.write_bytes(data)
        with self.assertRaisesRegex(ValueError, "authentication failed"):
            drill_encrypted_backup(self.output, self.passphrase, sha256=backup["sha256"])

    def test_export_rejects_source_mutation_after_verification(self):
        backup = self.make_backup()
        verified = recovery_encrypted.verify_backup

        def mutate_after_verifying(*args, **kwargs):
            result = verified(*args, **kwargs)
            with (self.state.parent / "backups" / backup["filename"]).open("ab") as source:
                source.write(b"modified after integrity verification")
            return result

        with patch("phd_agents.recovery_encrypted.verify_backup", side_effect=mutate_after_verifying):
            with self.assertRaisesRegex(ValueError, "changed between verification"):
                export_encrypted_backup(
                    backup["filename"], self.output, self.passphrase,
                    state_path=self.state, sha256=backup["sha256"], repo_root=self.checkout,
                )
        self.assertFalse(self.output.exists())

    def test_export_rejects_symlink_replacement_after_verification(self):
        backup = self.make_backup()
        source = self.state.parent / "backups" / backup["filename"]
        replacement = self.root / "other-private-file"
        replacement.write_bytes(b"private file must not be followed")
        replacement.chmod(0o600)
        verified = recovery_encrypted.verify_backup

        def replace_after_verifying(*args, **kwargs):
            result = verified(*args, **kwargs)
            source.unlink()
            source.symlink_to(replacement)
            return result

        with patch("phd_agents.recovery_encrypted.verify_backup", side_effect=replace_after_verifying):
            with self.assertRaises(OSError):
                export_encrypted_backup(
                    backup["filename"], self.output, self.passphrase,
                    state_path=self.state, sha256=backup["sha256"], repo_root=self.checkout,
                )
        self.assertFalse(self.output.exists())

    def test_explicit_encrypted_restore_replaces_database_and_preserves_previous_state(self):
        backup = self.make_backup()
        export_encrypted_backup(
            backup["filename"], self.output, self.passphrase,
            state_path=self.state, sha256=backup["sha256"], repo_root=self.checkout,
        )
        result = restore_encrypted_backup(
            self.output, self.passphrase, sha256=backup["sha256"],
            state_path=self.state, confirm=True,
        )
        self.assertTrue(result["restored"])
        self.assertTrue(result["encrypted_source"])
        self.assertFalse(result["off_host_copy_verified"])
        self.assertEqual(result["sha256"], backup["sha256"])
        self.assertIsNotNone(result["previous_state"])
        self.assertTrue((self.state.parent / "backups" / result["previous_state"]).is_file())
        self.assertEqual(stat.S_IMODE(self.state.stat().st_mode), 0o600)
        self.assertEqual(
            sorted(x.name for x in (self.state.parent / "backups").glob("phd-atlas-*.sqlite3")),
            sorted([backup["filename"], result["previous_state"]]),
        )
        restored = Store(self.state)
        try:
            self.assertEqual(restored.get_application("APP1")["notes"], "Private data sample")
        finally:
            restored.close()

    def test_encrypted_restore_denied_without_confirmation_or_with_wrong_passphrase(self):
        backup = self.make_backup()
        export_encrypted_backup(
            backup["filename"], self.output, self.passphrase,
            state_path=self.state, repo_root=self.checkout,
        )
        with self.assertRaisesRegex(PermissionError, "explicit --confirm"):
            restore_encrypted_backup(
                self.output, self.passphrase, sha256=backup["sha256"],
                state_path=self.state,
            )
        with self.assertRaisesRegex(ValueError, "authentication failed"):
            restore_encrypted_backup(
                self.output, "Different but sufficiently long passphrase 2026", sha256=backup["sha256"],
                state_path=self.state, confirm=True,
            )
        existing = Store(self.state)
        try:
            self.assertEqual(existing.get_application("APP1")["notes"], "Current live data")
        finally:
            existing.close()

    def test_encrypted_restore_rejected_while_private_database_is_open(self):
        backup = self.make_backup()
        export_encrypted_backup(
            backup["filename"], self.output, self.passphrase,
            state_path=self.state, repo_root=self.checkout,
        )
        active = Store(self.state)
        try:
            with self.assertRaises(ConflictError):
                restore_encrypted_backup(
                    self.output, self.passphrase, sha256=backup["sha256"],
                    state_path=self.state, confirm=True,
                )
            self.assertEqual(active.get_application("APP1")["notes"], "Current live data")
        finally:
            active.close()

    def test_encrypted_restore_can_recover_fresh_isolated_workspace(self):
        backup = self.make_backup()
        export_encrypted_backup(
            backup["filename"], self.output, self.passphrase,
            state_path=self.state, repo_root=self.checkout,
        )
        recovered_path = self.root / "isolated-owner" / "state.sqlite3"
        result = restore_encrypted_backup(
            self.output, self.passphrase, sha256=backup["sha256"],
            state_path=recovered_path, confirm=True,
        )
        self.assertTrue(result["restored"])
        self.assertIsNone(result["previous_state"])
        restored = Store(recovered_path)
        try:
            self.assertEqual(restored.get_application("APP1")["notes"], "Private data sample")
        finally:
            restored.close()

    def test_export_refuses_git_checkout_and_overwrites(self):
        backup = self.make_backup()
        with self.assertRaises(PermissionError):
            export_encrypted_backup(
                backup["filename"], self.checkout / "private.enc", self.passphrase,
                state_path=self.state, repo_root=self.checkout,
            )
        export_encrypted_backup(
            backup["filename"], self.output, self.passphrase,
            state_path=self.state, repo_root=self.checkout,
        )
        with self.assertRaises(ValueError):
            export_encrypted_backup(
                backup["filename"], self.output, self.passphrase,
                state_path=self.state, repo_root=self.checkout,
            )


if __name__ == "__main__":
    unittest.main()
