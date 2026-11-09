from __future__ import annotations

import json
import statistics
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from .store import Store


def usage_summary(store: Store, *, sample_limit: int = 2000) -> dict[str, Any]:
    if not 1 <= sample_limit <= 10000:
        raise ValueError("Invalid sample size")
    rows = store.db.execute(
        "SELECT provider_id,status,payload,created_at FROM runs ORDER BY created_at DESC, rowid DESC LIMIT ?",
        (sample_limit,)
    ).fetchall()
    counters: dict[str, dict[str, Any]] = defaultdict(lambda: {
        "calls": 0, "failed": 0, "input_tokens": 0, "output_tokens": 0, "latencies_ms": []
    })
    for row in rows:
        values = json.loads(row["payload"])
        provider = counters[row["provider_id"]]
        provider["calls"] += 1
        provider["failed"] += int(row["status"] == "failed")
        usage = values.get("usage") or {}
        in_tokens = usage.get("prompt_tokens", usage.get("input_tokens", 0))
        out_tokens = usage.get("completion_tokens", usage.get("output_tokens", 0))
        for key, value in (("input_tokens", in_tokens), ("output_tokens", out_tokens)):
            if type(value) is int and value >= 0:
                provider[key] += value
        latency = values.get("latency_ms")
        if type(latency) is int and latency >= 0:
            provider["latencies_ms"].append(latency)
    groups = []
    for provider_id, data in sorted(counters.items(), key=lambda item: (-item[1]["calls"], item[0])):
        latencies = sorted(data.pop("latencies_ms"))
        groups.append({
            "provider_id": provider_id, **data,
            "average_latency_ms": round(statistics.mean(latencies)) if latencies else None,
            "p95_latency_ms": latencies[min(len(latencies) - 1, max(0, int(len(latencies) * 0.95 + 0.9999) - 1))] if latencies else None,
            "measured_calls": len(latencies),
        })
    return {
        "as_of": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "sampled_runs": len(rows), "sample_limit": sample_limit, "limited": len(rows) == sample_limit,
        "total_failed": sum(p["failed"] for p in groups),
        "total_input_tokens": sum(p["input_tokens"] for p in groups),
        "total_output_tokens": sum(p["output_tokens"] for p in groups),
        "provider_usage": groups,
        "cost_estimate": None,
        "caveat": "Observed per-call usage only. No token pricing was inferred; missing usage fields remain unmeasured."
    }
