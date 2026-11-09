from __future__ import annotations

import json
from typing import Any


def _trim(value: Any, *, string_limit: int, list_limit: int, key_limit: int, depth: int = 0) -> Any:
    if depth > 12:
        return "[Nested source data omitted]"
    if isinstance(value, str):
        return value if len(value) <= string_limit else value[:string_limit] + " [text truncated]"
    if isinstance(value, list):
        out = [_trim(item, string_limit=string_limit, list_limit=list_limit,
                     key_limit=key_limit, depth=depth+1) for item in value[:list_limit]]
        if len(value) > list_limit:
            out.append({"_omitted_items": len(value)-list_limit})
        return out
    if isinstance(value, dict):
        out = {}
        for key,item in list(value.items())[:key_limit]:
            out[str(key)[:100]] = _trim(item, string_limit=string_limit, list_limit=list_limit,
                                       key_limit=key_limit, depth=depth+1)
        if len(value)>key_limit:
            out["_omitted_fields"] = len(value)-key_limit
        return out
    if value is None or isinstance(value, (bool,int,float)):
        return value
    return str(value)[:string_limit]


def bounded_evidence(payload: dict[str, Any], max_chars: int = 15500) -> str:
    if not isinstance(payload, dict) or not 500 <= max_chars <= 100000:
        raise ValueError("Invalid evidence payload or character budget")
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
    if len(raw) <= max_chars:
        return raw
    for string_limit,list_limit,key_limit in [
        (900,25,60), (600,15,45), (350,10,32),
        (220,6,22), (120,4,16), (70,2,12), (40,1,8)
    ]:
        candidate = {"_evidence_truncated": True, **_trim(payload, string_limit=string_limit,
                        list_limit=list_limit,key_limit=key_limit)}
        packed = json.dumps(candidate, ensure_ascii=False, separators=(",", ":"), allow_nan=False)
        if len(packed) <= max_chars:
            return packed
    summary = {"_evidence_truncated": True, "_evidence_budget_exhausted": True,
               "warning": "Detailed evidence omitted to preserve valid bounded JSON",
               "record_id": str(payload.get("record", {}).get("id",""))[:80]
                  if isinstance(payload.get("record"),dict) else ""}
    return json.dumps(summary, ensure_ascii=False, separators=(",", ":"))
