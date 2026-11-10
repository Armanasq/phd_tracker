from __future__ import annotations

import json
import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .store import Store

_SAMPLE_LIMIT = 500
_MAX_METRIC = 100_000_000
_KNOWN_STATES = frozenset({"proposed", "failed"})


def _amount(value: object) -> int | None:
    if type(value) is int and 0 <= value <= _MAX_METRIC:
        return value
    if type(value) is float and math.isfinite(value) and 0 <= value <= _MAX_METRIC:
        return round(value)
    return None


def _percentile(values: list[int], percentile: float) -> int | None:
    if not values:
        return None
    ordered = sorted(values)
    return ordered[math.ceil(len(ordered) * percentile) - 1]


def _metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counted = [row for row in rows if row["status"] in _KNOWN_STATES]
    latencies = [row["latency_ms"] for row in counted if row["latency_ms"] is not None]
    usage = [row for row in counted if row["input_tokens"] is not None or row["output_tokens"] is not None]
    audits = [row["claim_audit"] for row in counted if row["claim_audit"] is not None]
    failures = sum(row["status"] == "failed" for row in counted)
    return {
        "calls": len(counted),
        "completed_proposals": len(counted) - failures,
        "failed": failures,
        "failure_rate": round(failures / len(counted), 4) if counted else None,
        "latency_p50_ms": _percentile(latencies, 0.50),
        "latency_p95_ms": _percentile(latencies, 0.95),
        "latency_measured": len(latencies),
        "usage_reported": len(usage),
        "input_tokens_reported": sum(row["input_tokens"] or 0 for row in usage),
        "output_tokens_reported": sum(row["output_tokens"] or 0 for row in usage),
        "citation_audits": len(audits),
        "unknown_reference_links": sum(item["unknown_reference_links"] for item in audits),
        "unverified_reference_links": sum(item["linked_to_unverified_records"] for item in audits),
        "linked_reviewed_records": sum(item["linked_to_reviewed_records"] for item in audits),
        "unlinked_text_blocks": sum(item["unlinked_text_blocks"] for item in audits),
        "semantic_entailment_verified": False,
    }


def evaluation_report(store: Store, *, limit: int = _SAMPLE_LIMIT) -> dict[str, Any]:
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise ValueError("Evaluation sample limit must be an integer in [1,1000]")
    raw_rows = store.db.execute(
        "SELECT id,kind,agent_id,provider_id,status,payload,created_at FROM runs "
        "WHERE kind IN ('agent','workflow','workflow_summary') "
        "ORDER BY created_at DESC,rowid DESC LIMIT ?",
        (limit + 1,),
    ).fetchall()
    rows: list[dict[str, Any]] = []
    workflow_summaries: list[dict[str, Any]] = []
    for raw in raw_rows[:limit]:
        try:
            payload = json.loads(raw["payload"])
        except (TypeError, ValueError) as error:
            raise ValueError("Run ledger contains unreadable evaluation data") from error
        if not isinstance(payload, dict):
            raise ValueError("Run ledger evaluation data must be an object")
        if raw["kind"] == "workflow_summary":
            workflow_summaries.append({
                "run_id": raw["id"],
                "workflow_id": raw["agent_id"],
                "status": raw["status"],
                "stage_count": _amount(payload.get("stage_count")),
                "failed_stage": _amount(payload.get("failed_stage")),
                "completed_stages": len(payload.get("completed_run_ids", []))
                if isinstance(payload.get("completed_run_ids"), list) else None,
            })
            continue
        usage = payload.get("usage") if isinstance(payload.get("usage"), dict) else {}
        claim_audit = payload.get("claim_audit")
        if not isinstance(claim_audit, dict) or claim_audit.get("schema_version") != 1:
            claim_audit = None
        else:
            claim_audit = {
                field: _amount(claim_audit.get(field)) or 0
                for field in (
                    "unknown_reference_links", "linked_to_unverified_records",
                    "linked_to_reviewed_records", "unlinked_text_blocks",
                )
            }
        rows.append({
            "run_id": raw["id"],
            "kind": raw["kind"],
            "agent_id": str(raw["agent_id"])[:100],
            "provider_id": str(raw["provider_id"] or "")[:100],
            "status": raw["status"],
            "created_at": raw["created_at"],
            "model": str(payload.get("model") or "")[:128],
            "latency_ms": _amount(payload.get("latency_ms")),
            "input_tokens": _amount(usage.get("prompt_tokens", usage.get("input_tokens"))),
            "output_tokens": _amount(usage.get("completion_tokens", usage.get("output_tokens"))),
            "claim_audit": claim_audit,
            "prompt_contract_id": str(payload.get("prompt_contract_id") or "")[:100],
        })
    by_provider: dict[str, list[dict[str, Any]]] = defaultdict(list)
    by_agent: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        by_provider[row["provider_id"]].append(row)
        by_agent[row["agent_id"]].append(row)
    return {
        "schema_version": 1,
        "scope": "single_owner_local_run_ledger",
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sample_limit": limit,
        "sample_truncated": len(raw_rows) > limit,
        "sampled_runs": len(rows),
        "summary": _metrics(rows),
        "providers": [
            {"provider_id": key, **_metrics(group)}
            for key, group in sorted(by_provider.items(), key=lambda item: (-len(item[1]), item[0]))
        ],
        "agents": [
            {"agent_id": key, **_metrics(group)}
            for key, group in sorted(by_agent.items(), key=lambda item: (-len(item[1]), item[0]))
        ],
        "workflow_summaries": workflow_summaries[:30],
        "recent_traces": [
            {key: value for key, value in row.items() if key != "claim_audit"}
            for row in rows[:40]
        ],
        "status": "descriptive_only" if rows else "no_observations",
        "privacy": "aggregates_and_allowlisted_identifiers_only_no_prompts_responses_or_applicant_records",
        "limitations": (
            "Descriptive measurements from retained local runs; missing usage and citations are unknown. "
            "Citations are identifier matches, not semantic entailment. "
            "Provider pricing, admission outcomes, external reliability, and live model quality are not inferred."
        ),
    }
