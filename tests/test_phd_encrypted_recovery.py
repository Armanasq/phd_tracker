from __future__ import annotations

import importlib.util
import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from phd_agents import recovery_encrypted

from phd_agents.recovery_encrypted import drill_encrypted_backup, export_encrypted_backup
from phd_agents.store import Store


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
