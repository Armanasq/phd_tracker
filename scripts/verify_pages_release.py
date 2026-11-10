from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import re
import time
from collections.abc import Callable
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

_SHA = re.compile(r"[0-9a-f]{64}\Z")
_COMMIT = re.compile(r"[0-9a-f]{40}\Z")
_MAX_FILES = 500
_MAX_SINGLE = 50_000_000
_MAX_TOTAL = 110_000_000


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request, fp, code, msg, headers, newurl):
        raise ValueError("Published static assets redirected unexpectedly")


def validate_pages_url(raw: str) -> str:
    if not isinstance(raw, str):
        raise ValueError("Published Pages URL must be HTTPS")
    value = raw.rstrip("/")
    parsed = urlsplit(value)
    if (parsed.scheme != "https" or not parsed.hostname or
            parsed.username or parsed.password or parsed.port is not None or
            parsed.query or parsed.fragment):
        raise ValueError("Published Pages URL must be public HTTPS without credentials or query")
    host = parsed.hostname.casefold()
    if host in {"localhost", "localhost.localdomain"} or host.endswith((".local", ".internal")):
        raise ValueError("Published Pages URL must not be a private hostname")
    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise ValueError("Published Pages URL must use a DNS hostname")
    return value


def verify_published_files(manifest: dict[str, Any], reader: Callable[[str], bytes], commit: str) -> dict:
    if not isinstance(commit, str) or not _COMMIT.fullmatch(commit):
        raise ValueError("Invalid expected release commit")
    if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or manifest.get("commit") != commit:
        raise ValueError("Published release manifest does not match the expected source commit")
    assets = manifest.get("sha256")
    if (not isinstance(assets, dict) or not 1 <= len(assets) <= _MAX_FILES or
            manifest.get("asset_count") != len(assets) or
            "index.html" not in assets or "app.js" not in assets):
        raise ValueError("Published asset inventory is missing or excessive")
    total = 0
    for path, digest in sorted(assets.items()):
        if (not isinstance(path, str) or not path or
                any(segment in {"", ".", ".."} for segment in path.split("/")) or
                any(char in path for char in "\\?#\r\n\x00") or
                path.startswith("/") or not isinstance(digest, str) or not _SHA.fullmatch(digest)):
            raise ValueError("Invalid path or checksum in published manifest")
        raw = reader(path)
        if not isinstance(raw, bytes) or len(raw) > _MAX_SINGLE:
            raise ValueError("Published static asset exceeded size limit: " + path)
        total += len(raw)
        if total > _MAX_TOTAL:
            raise ValueError("Published release exceeded total download budget")
        if hashlib.sha256(raw).hexdigest() != digest:
            raise ValueError("Published asset failed checksum: " + path)
    return {"commit": commit, "verified_assets": len(assets), "verified_bytes": total}


def verify_live(base: str, commit: str) -> dict:
    base = validate_pages_url(base)
    opener = build_opener(_NoRedirect())

    def read(relative: str) -> bytes:
        address = base + "/" + quote(relative, safe="/") + "?revision=" + commit
        request = Request(address, headers={"User-Agent": "PhD-Atlas-Release-Verify/1.0", "Cache-Control": "no-cache"})
        with opener.open(request, timeout=15) as response:
            body = response.read(_MAX_SINGLE + 1)
        if len(body) > _MAX_SINGLE:
            raise ValueError("Published asset is oversized: " + relative)
        return body

    manifest_raw = read("release-manifest.json")
    if len(manifest_raw) > 500_000:
        raise ValueError("Published manifest is too large")
    manifest = json.loads(manifest_raw)
    return verify_published_files(manifest, read, commit)


def main() -> None:
    parser = argparse.ArgumentParser(description="Verify every deployed Pages asset against its commit manifest")
    parser.add_argument("--url", required=True)
    parser.add_argument("--commit", required=True)
    args = parser.parse_args()
    attempts = 4
    for index in range(attempts):
        try:
            result = verify_live(args.url, args.commit)
            print(json.dumps(result, sort_keys=True))
            return
        except (ValueError, OSError, HTTPError, URLError, json.JSONDecodeError) as error:
            if index == attempts - 1:
                raise SystemExit("Published full-asset verification failed: " + str(error)) from error
            time.sleep(3)


if __name__ == "__main__":
    main()
