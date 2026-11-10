from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.site_manifest import build_manifest, site_digests, verify_manifest

COMMIT = "a" * 40


class SiteManifestTests(unittest.TestCase):
    def setUp(self) -> None:
        temp = tempfile.TemporaryDirectory()
        self.addCleanup(temp.cleanup)
        self.root = Path(temp.name) / "site"
        self.root.mkdir()
        (self.root / "index.html").write_text("<!doctype html><title>Test</title>", encoding="utf-8")
        (self.root / "app.js").write_text("console.log('safe')", encoding="utf-8")
        (self.root / "modules").mkdir()
        (self.root / "modules" / "source-claims.mjs").write_text("export const claim = true;", encoding="utf-8")

    def test_manifest_covers_all_assets_and_detects_tampering(self) -> None:
        manifest = build_manifest(self.root, COMMIT)
        self.assertEqual(manifest["asset_count"], 3)
        self.assertEqual(manifest["commit"], COMMIT)
        self.assertIn("modules/source-claims.mjs", manifest["sha256"])
        verify_manifest(self.root, manifest)
        (self.root / "release-manifest.json").write_text("ignored", encoding="utf-8")
        verify_manifest(self.root, manifest)
        (self.root / "modules" / "source-claims.mjs").write_text("export const claim = false;", encoding="utf-8")
        with self.assertRaises(ValueError):
            verify_manifest(self.root, manifest)

    def test_new_assets_and_deleted_assets_fail_inventory_verification(self) -> None:
        manifest = build_manifest(self.root, COMMIT)
        extra = self.root / "modules" / "unexpected.mjs"
        extra.write_text("export const extra=1;", encoding="utf-8")
        with self.assertRaises(ValueError):
            verify_manifest(self.root, manifest)
        extra.unlink()
        (self.root / "app.js").unlink()
        with self.assertRaises(ValueError):
            verify_manifest(self.root, manifest)

    def test_secret_material_and_symlinks_are_rejected(self) -> None:
        for name in [".env", ".env.local", "credentials.json", "state.sqlite3", "secret.pem"]:
            extra = self.root / name
            extra.write_text("SECRET_TEST_PLACEHOLDER", encoding="utf-8")
            with self.subTest(name=name), self.assertRaises(ValueError):
                site_digests(self.root)
            extra.unlink()
        pointer = self.root / "private.link"
        pointer.symlink_to(self.root / "app.js")
        with self.assertRaises(ValueError):
            site_digests(self.root)

    def test_unsupported_private_artifacts_and_hidden_dirs_fail_closed(self) -> None:
        for name in ("application.sqlite-wal", "app.log", "app.xlsx", "records.csv",
                     "private_records.json", "credentials-backup.txt", ".aws/config",
                     "account_token.json", "old_backup/site.json"):
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(b"UNTRUSTED_INTERNAL_TEST")
            with self.subTest(name=name), self.assertRaises(ValueError):
                site_digests(self.root)
            target.unlink()

    def test_allowlisted_static_media_can_be_published(self) -> None:
        images = self.root / "images"
        images.mkdir()
        (images / "research-diagram.webp").write_bytes(b"static-image-test")
        (images / "logo.svg").write_bytes(b"<svg xmlns='http://www.w3.org/2000/svg'/>")
        manifest = build_manifest(self.root, COMMIT)
        self.assertIn("images/research-diagram.webp", manifest["sha256"])
        verify_manifest(self.root, manifest)

    def test_invalid_commit_or_missing_entrypoint_rejected(self) -> None:
        with self.assertRaises(ValueError):
            build_manifest(self.root, "latest")
        (self.root / "index.html").unlink()
        with self.assertRaises(ValueError):
            build_manifest(self.root, COMMIT)


if __name__ == "__main__":
    unittest.main()
