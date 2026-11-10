from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.request import ProxyHandler, Request, build_opener

from .egress import PinnedHTTPSHandler
from .engine import owner_records
from .providers import NoRedirect, ProviderError, validate_url
from .store import Store

_ALLOWED_MEDIA = frozenset({"text/html", "text/plain"})
_VERIFIED_RECORDS = frozenset({"source_verified", "owner_verified"})
_DIGEST = re.compile(r"[0-9a-f]{64}\Z")


def fetch_public_source(url: str, *, timeout: int = 15, max_bytes: int = 1_000_000) -> dict[str, Any]:
    if type(timeout) is not int or not 1 <= timeout <= 25:
        raise ValueError("Invalid source timeout")
    if type(max_bytes) is not int or not 1024 <= max_bytes <= 2_000_000:
        raise ValueError("Invalid source byte limit")
    destination = validate_url(url, False)
    if not destination.startswith("https://"):
        raise ValueError("Official source observations require HTTPS")
    request = Request(destination, method="GET", headers={
        "User-Agent": "PhD-Atlas-Source-Observer/1.0", "Accept": "text/html,text/plain;q=0.9",
    })
    opener = build_opener(NoRedirect(), ProxyHandler({}), PinnedHTTPSHandler(local=False))
    try:
        with opener.open(request, timeout=timeout) as response:
            mime = response.headers.get("Content-Type", "").split(";")[0].strip().lower()
            if mime not in _ALLOWED_MEDIA:
                return {"status": "unsupported_media_type", "http_status": 200,
                        "content_sha256": None, "content_length": 0}
            raw = response.read(max_bytes + 1)
    except HTTPError as error:
        return {"status": "http_error", "http_status": error.code,
                "content_sha256": None, "content_length": 0}
    except ProviderError:
        return {"status": "redirect_denied", "http_status": None,
                "content_sha256": None, "content_length": 0}
    except (URLError, TimeoutError, OSError):
        return {"status": "connection_error", "http_status": None,
                "content_sha256": None, "content_length": 0}
    if len(raw) > max_bytes:
        return {"status": "oversize", "http_status": 200,
                "content_sha256": None, "content_length": len(raw)}
    return {"status": "fetched", "http_status": 200,
            "content_sha256": hashlib.sha256(raw).hexdigest(), "content_length": len(raw)}


def observe_record(
    store: Store, application_id: str, source_url: str, *,
    observed_at: datetime | None = None,
    fetcher: Callable[[str], dict[str, Any]] | None = None,
) -> dict[str, Any]:
    if not isinstance(application_id, str) or not 1 <= len(application_id) <= 120:
        raise ValueError("Invalid source observation identifier")
    validated = validate_url(source_url, False)
    if not validated.startswith("https://"):
        raise ValueError("Official observations require HTTPS")
    instant = observed_at or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("Observation requires a timezone-aware time")
    result = (fetcher or fetch_public_source)(validated)
    if not isinstance(result, dict) or result.get("status") not in {
        "fetched", "http_error", "redirect_denied", "connection_error",
        "unsupported_media_type", "oversize",
    }:
        raise ValueError("Invalid source observation result")
    fingerprint = result.get("content_sha256")
    if fingerprint is not None and (not isinstance(fingerprint, str)
                                    or not _DIGEST.fullmatch(fingerprint)):
        raise ValueError("Invalid source digest")
    if result["status"] == "fetched" and not fingerprint:
        raise ValueError("Successful source observation requires a digest")
    previous = store.db.execute(
        "SELECT content_sha256 FROM source_observations "
        "WHERE application_id=? AND source_url=? AND status='fetched' "
        "ORDER BY id DESC LIMIT 1", (application_id, validated),
    ).fetchone()
    if result["status"] != "fetched":
        drift = "unavailable_no_source_conclusion"
    elif previous is None:
        drift = "baseline_only"
    elif previous["content_sha256"] == fingerprint:
        drift = "unchanged_bytes"
    else:
        drift = "source_bytes_changed_needs_review"
    timestamp = instant.astimezone(timezone.utc).isoformat(timespec="seconds")
    with store.db:
        store.db.execute(
            "INSERT INTO source_observations(application_id,source_url,status,"
            "content_sha256,observed_at,http_status,content_length,drift) VALUES(?,?,?,?,?,?,?,?)",
            (application_id, validated, result["status"], fingerprint, timestamp,
             result.get("http_status"), result.get("content_length"), drift),
        )
        store.db.execute(
            "DELETE FROM source_observations WHERE id NOT IN "
            "(SELECT id FROM source_observations ORDER BY id DESC LIMIT 2000)"
        )
        store._audit("source:observed", application_id)
    return {
        "application_id": application_id, "source_url": validated, "observed_at": timestamp,
        "status": result["status"], "http_status": result.get("http_status"),
        "content_sha256": fingerprint, "content_length": result.get("content_length"),
        "drift": drift, "conclusion": (
            "A website request and content hash do not verify an admissions deadline, "
            "funding eligibility or whether an application portal is open."
        ),
    }


def recent_observations(store: Store, *, limit: int = 50) -> list[dict[str, Any]]:
    if type(limit) is not int or not 1 <= limit <= 100:
        raise ValueError("Invalid source observation limit")
    rows = store.db.execute(
        "SELECT o.id,o.application_id,o.source_url,o.status,o.content_sha256,"
        "o.observed_at,o.http_status,o.content_length,o.drift,"
        "r.decision AS review_decision,r.reviewed_at "
        "FROM source_observations AS o LEFT JOIN source_observation_reviews AS r "
        "ON r.id=(SELECT MAX(v.id) FROM source_observation_reviews AS v "
        "WHERE v.observation_id=o.id) ORDER BY o.id DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return [dict(row) for row in rows]


def run_source_observations(
    store: Store, root: Path, *, limit: int = 8,
    application_id: str | None = None,
) -> dict[str, Any]:
    if type(limit) is not int or not 1 <= limit <= 20:
        raise ValueError("Source observation limit must be 1–20")
    _, records = owner_records(store, root)
    if application_id is not None and not any(r.get("id") == application_id for r in records):
        raise ValueError("Unknown application ID")
    eligible = []
    skipped = []
    for record in records:
        if application_id is not None and record.get("id") != application_id:
            continue
        identity = record.get("id")
        if record.get("record_type") != "tracked" or record.get("verification") not in _VERIFIED_RECORDS:
            skipped.append({"application_id": str(identity)[:120], "reason": "source_not_reviewed"})
            continue
        try:
            url = validate_url(record.get("source_url"), False)
            if not url.startswith("https://"):
                raise ValueError("Unencrypted source URL")
        except ValueError:
            skipped.append({"application_id": str(identity)[:120], "reason": "unsafe_or_missing_url"})
            continue
        eligible.append((identity, url))
        if len(eligible) >= limit:
            break
    observed = [observe_record(store, identity, url) for identity, url in eligible]
    return {"observations": observed, "skipped": skipped[:100],
            "manual_execution": True, "network_requests": len(observed),
            "limit": limit, "result_type": "byte_drift_not_field_verification"}
