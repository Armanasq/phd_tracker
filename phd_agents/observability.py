from __future__ import annotations

import json
import math
import re
from datetime import datetime, timedelta, timezone
from typing import Any

from .store import Store

_ERROR_CODE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,79}\Z")
_SUCCESS = "proposed"
_FAILURE = "failed"


def _nonnegative_integer(value: object) -> int | None:
    return value if type(value) is int and 0 <= value <= 3_600_000 else None


def _utc(value: str) -> datetime | None:
    try:
        point = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return point.astimezone(timezone.utc) if point.tzinfo else None


def report_observability(
    store: Store, *, now: datetime | None = None,
    sample_limit: int = 500, window_hours: int = 24,
    max_error_rate: float = 0.05, max_p95_ms: int = 60000,
    min_observations: int = 20,
) -> dict[str, Any]:
    if type(sample_limit) is not int or not 1 <= sample_limit <= 2000:
        raise ValueError("Invalid observability sample limit")
    if type(window_hours) is not int or not 1 <= window_hours <= 168:
        raise ValueError("Invalid observability window")
    if type(max_error_rate) is not float or not 0 <= max_error_rate <= 1:
        raise ValueError("Invalid error budget")
    if type(max_p95_ms) is not int or not 1000 <= max_p95_ms <= 3600000:
        raise ValueError("Invalid latency objective")
    if type(min_observations) is not int or not 1 <= min_observations <= 2000:
        raise ValueError("Invalid minimum sample")
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        raise ValueError("Observability clock must be timezone-aware")
    instant = instant.astimezone(timezone.utc)
    start = instant - timedelta(hours=window_hours)
    rows = store.db.execute(
        "SELECT id,kind,agent_id,provider_id,status,payload,created_at "
        "FROM runs ORDER BY created_at DESC,rowid DESC LIMIT ?",
        (sample_limit,),
    ).fetchall()
    traces: list[dict[str, Any]] = []
    window_count = failures = 0
    latencies: list[int] = []
    for row in rows:
        try:
            payload = json.loads(row["payload"])
        except (ValueError, TypeError) as error:
            raise ValueError("Private run trace contains malformed JSON") from error
        if not isinstance(payload, dict):
            raise ValueError("Private run trace is not a JSON object")
        elapsed = _nonnegative_integer(payload.get("latency_ms"))
        usage = payload.get("usage")
        if not isinstance(usage, dict):
            usage = {}
        trace: dict[str, Any] = {
            "run_id": row["id"],
            "kind": row["kind"],
            "agent_id": row["agent_id"],
            "provider_id": row["provider_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "latency_ms": elapsed,
            "input_tokens": _nonnegative_integer(
                usage.get("prompt_tokens", usage.get("input_tokens"))
            ),
            "output_tokens": _nonnegative_integer(
                usage.get("completion_tokens", usage.get("output_tokens"))
            ),
        }
        if row["status"] == _FAILURE:
            code = payload.get("error_type")
            trace["error_type"] = code if isinstance(code, str) and _ERROR_CODE.fullmatch(code) else "Unclassified"
        if len(traces) < 50:
            traces.append(trace)
        timestamp = _utc(row["created_at"])
        if timestamp is None or not start <= timestamp <= instant:
            continue
        if row["status"] not in {_SUCCESS, _FAILURE}:
            continue
        window_count += 1
        failures += row["status"] == _FAILURE
        if elapsed is not None:
            latencies.append(elapsed)

    latencies.sort()
    p95 = latencies[math.ceil(len(latencies) * 0.95) - 1] if latencies else None
    rate = round(failures / window_count, 4) if window_count else None
    sufficient = window_count >= min_observations and len(latencies) >= min_observations
    if not sufficient:
        health = "insufficient_data"
    elif rate is not None and (rate > max_error_rate or (p95 is not None and p95 > max_p95_ms)):
        health = "breached"
    else:
        health = "within_objectives"
    return {
        "schema_version": 1,
        "as_of": instant.isoformat(timespec="seconds"),
        "window_hours": window_hours,
        "scanned_runs": len(rows),
        "sample_truncated": len(rows) == sample_limit,
        "window": {
            "completed_calls": window_count,
            "failed_calls": failures,
            "error_rate": rate,
            "p95_latency_ms": p95,
            "measured_latencies": len(latencies),
        },
        "objectives": {
            "status": health,
            "min_observations": min_observations,
            "max_error_rate": max_error_rate,
            "max_p95_latency_ms": max_p95_ms,
            "scope": "operator_defaults_private_runtime_only",
        },
        "recent_traces": traces,
        "privacy": "allowlist_only_no_prompts_responses_sources_credentials_or_application_identifiers",
        "limitations": "Read-only local inference observations; not a continuous hosted SLO or external provider certification.",
    }
