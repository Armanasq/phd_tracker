from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit, urlunsplit

_FIELDS = (
    "deadline", "deadline_type", "verification", "apply_url", "source_url",
    "funding", "eligibility", "documents",
)


def load_snapshot(path: Path, *, max_bytes: int = 8_000_000) -> dict[str, Any]:
    target = Path(path).expanduser()
    if target.is_symlink() or not target.is_file() or target.stat().st_size > max_bytes:
        raise ValueError("Source snapshot must be an ordinary local JSON file under 8 MB")
    parsed = json.loads(target.read_text(encoding="utf-8"))
    if not isinstance(parsed, dict):
        raise ValueError("Source snapshot must contain a JSON object")
    return parsed


def _records(snapshot: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if not isinstance(snapshot, dict) or not isinstance(snapshot.get("records"), list):
        raise ValueError("Snapshot requires a records array")
    rows = snapshot["records"]
    if len(rows) > 10000:
        raise ValueError("Snapshot exceeds record count limit")
    indexed: dict[str, dict[str, Any]] = {}
    for item in rows:
        if not isinstance(item, dict):
            raise ValueError("Malformed source snapshot record")
        identity = item.get("id")
        if not isinstance(identity, str) or not 1 <= len(identity) <= 120:
            raise ValueError("Source record IDs must be 1–120 characters")
        if identity in indexed:
            raise ValueError("Duplicate source record ID: " + identity[:30])
        indexed[identity] = item
    return indexed


def _snapshot_day(snapshot: dict[str, Any]) -> date | None:
    stamp = snapshot.get("as_of")
    if not isinstance(stamp, str) or not stamp:
        return None
    try:
        return date.fromisoformat(stamp[:10])
    except ValueError:
        return None


def _source_link(record: dict[str, Any] | None) -> str | None:
    if not isinstance(record, dict):
        return None
    raw = record.get("source_url")
    if not isinstance(raw, str):
        return None
    try:
        parsed = urlsplit(raw)
    except ValueError:
        return None
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password:
        return None
    host = parsed.hostname.casefold()
    if host in {"localhost", "127.0.0.1"} or host.endswith((".local", ".internal")):
        return None
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))[:500]


def _value(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return text[:300] + (" [display truncated]" if len(text) > 300 else "")


def compare_sources(
    previous: dict[str, Any], current: dict[str, Any], *,
    today: date | None = None, freshness_days: int = 7,
) -> dict[str, Any]:
    if type(freshness_days) is not int or not 1 <= freshness_days <= 90:
        raise ValueError("Invalid source snapshot freshness window")
    old, new = _records(previous), _records(current)
    now = today or datetime.now(timezone.utc).date()
    observed = _snapshot_day(current)
    age = (now - observed).days if observed else None
    freshness = (
        "unknown" if age is None else "future_dated" if age < 0
        else "stale_snapshot" if age > freshness_days else "recent_snapshot"
    )
    changes: list[dict[str, Any]] = []
    for identity in sorted(set(old) | set(new)):
        before, after = old.get(identity), new.get(identity)
        if before is None or after is None:
            kind = "candidate_added" if before is None else "record_missing_from_new_snapshot"
            fields = [("record_presence", "absent" if before is None else "present",
                       "present" if after is not None else "absent")]
        else:
            kind = "field_changed"
            fields = [(field, before.get(field), after.get(field))
                      for field in _FIELDS if before.get(field) != after.get(field)]
        for field, prior, updated in fields:
            link = _source_link(after) or _source_link(before)
            digest = hashlib.sha256(
                json.dumps([identity, field, prior, updated], sort_keys=True,
                           ensure_ascii=False, allow_nan=False, default=str).encode("utf-8")
            ).hexdigest()[:24]
            changes.append({
                "event_id": digest,
                "application_id": identity,
                "field": field,
                "kind": kind,
                "before": _value(_source_link({"source_url": prior}) if field in {"source_url", "apply_url"} else prior),
                "after": _value(_source_link({"source_url": updated}) if field in {"source_url", "apply_url"} else updated),
                "source_url": link,
                "review_status": "needs_primary_recheck" if link else "missing_primary_source",
                "requires_review": True,
                "snapshot_freshness": freshness,
            })
    return {
        "schema_version": 1,
        "previous_as_of": previous.get("as_of"),
        "current_as_of": current.get("as_of"),
        "observed_on": now.isoformat(),
        "current_snapshot_age_days": age,
        "snapshot_freshness": freshness,
        "previous_count": len(old),
        "current_count": len(new),
        "changed_items": len(changes),
        "changes": changes[:1000],
        "truncated": len(changes) > 1000,
        "conclusions": "Candidate disappearance is not proof a vacancy closed; a changed deadline is not official until independently rechecked.",
        "source_policy": "Compares locally supplied observations only. Does not fetch official portals, establish site freshness, or edit admission records.",
    }
