from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

_MAX_FILES = 2000
_MAX_FILE_BYTES = 50_000_000
_SECRET_BASENAMES = frozenset({
    "credentials.json", "secrets.json", "service-account.json",
    "service_account.json", "id_rsa", "id_ed25519",
    ".pypirc", ".npmrc",
})
_SECRET_SUFFIXES = frozenset({".sqlite", ".sqlite3", ".db", ".pem", ".key", ".p12", ".pfx"})
_PUBLIC_SUFFIXES = frozenset({
    ".html", ".htm", ".js", ".mjs", ".css", ".json", ".svg", ".xml",
    ".md", ".txt", ".webmanifest", ".ico", ".png", ".jpg", ".jpeg",
    ".webp", ".woff2", ".wasm",
})
_PRIVATE_NAME_TOKENS = frozenset({"secret", "secrets", "private", "credential", "credentials", "password", "passwords", "token", "tokens", "backup", "backups"})
_SHA40 = re.compile(r"[0-9a-fA-F]{40}\Z")


def site_digests(root: Path) -> dict[str, str]:
    if not root.is_dir() or root.is_symlink():
        raise ValueError("Static site root must be an ordinary directory")
    results: dict[str, str] = {}
    for entry in sorted(root.rglob("*")):
        if entry.is_symlink():
            raise ValueError("Static site must not contain symbolic links")
        if not entry.is_file():
            continue
        relative = entry.relative_to(root).as_posix()
        if relative == "release-manifest.json":
            continue
        name = entry.name.casefold()
        components = [part.casefold() for part in entry.relative_to(root).parts]
        if (name in _SECRET_BASENAMES or name == ".env" or name.startswith(".env.")
                or entry.suffix.casefold() in _SECRET_SUFFIXES
                or any(part.startswith(".") for part in components)
                or any(token in component.replace("-", "_").split("_")
                       for component in components for token in _PRIVATE_NAME_TOKENS)):
            raise ValueError("Private or credential file cannot be included in GitHub Pages: " + relative)
        if entry.suffix.casefold() not in _PUBLIC_SUFFIXES:
            raise ValueError("Unsupported public asset type in GitHub Pages: " + relative)
        if len(results) >= _MAX_FILES:
            raise ValueError("Static site exceeded the asset-count limit")
        if entry.stat().st_size > _MAX_FILE_BYTES:
            raise ValueError("Static asset exceeded the per-file size limit: " + relative)
        results[relative] = hashlib.sha256(entry.read_bytes()).hexdigest()
    if "index.html" not in results or "app.js" not in results:
        raise ValueError("Static site is missing its application entrypoints")
    return results


def build_manifest(root: Path, commit: str) -> dict[str, Any]:
    if not isinstance(commit, str) or not _SHA40.fullmatch(commit):
        raise ValueError("Release commit must be a 40-character Git SHA")
    digests = site_digests(root)
    return {
        "schema_version": 1,
        "commit": commit.lower(),
        "asset_count": len(digests),
        "sha256": digests,
    }


def verify_manifest(root: Path, manifest: dict[str, Any]) -> None:
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1:
        raise ValueError("Unsupported static release manifest")
    if not isinstance(manifest.get("commit"), str) or not _SHA40.fullmatch(manifest["commit"]):
        raise ValueError("Missing release commit identity")
    expected = manifest.get("sha256")
    actual = site_digests(root)
    if not isinstance(expected, dict) or manifest.get("asset_count") != len(actual) or actual != expected:
        raise ValueError("Published asset inventory or content differs from the release manifest")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a private-file-safe, commit-bound static asset manifest")
    parser.add_argument("--site", type=Path, default=Path("site"))
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    manifest = build_manifest(args.site, args.commit)
    output = args.site / "release-manifest.json"
    output.write_text(json.dumps(manifest, sort_keys=True, indent=2) + "\n", encoding="utf-8")
    verify_manifest(args.site, manifest)
    print(json.dumps({"commit": manifest["commit"], "asset_count": manifest["asset_count"]}))


if __name__ == "__main__":
    main()
