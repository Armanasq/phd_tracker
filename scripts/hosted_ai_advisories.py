from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
import sys
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import HTTPRedirectHandler, Request, build_opener

CATEGORIES = frozenset({"source_review", "deadline_cutoff", "document_readiness", "funding_evidence", "eligibility_evidence", "duplicate_route"})
PRIORITIES = frozenset({"high", "medium", "low"})
CLOSED_STATUSES = frozenset({"rejected", "withdrawn", "archived", "offer", "blocked", "submitted"})
MAX_ITEMS = 24
MAX_INPUT_RECORDS = 48
MAX_RESPONSE_BYTES = 65_536


class HostedAIError(ValueError):
    pass


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, request: Request, fp: Any, code: int, msg: str, headers: Any, newurl: str) -> None:
        return None


def _day(value: object) -> date | None:
    if not isinstance(value, str):
        return None
    try:
        parsed = date.fromisoformat(value)
        if parsed.isoformat() == value:
            return parsed
    except ValueError:
        pass
    return None


def public_candidates(snapshot: dict[str, Any], *, today: date, limit: int = MAX_INPUT_RECORDS) -> list[dict[str, Any]]:
    if snapshot.get("schema_version") != 1 or not isinstance(snapshot.get("records"), list):
        raise HostedAIError("Invalid public workspace snapshot")
    if not 1 <= limit <= MAX_INPUT_RECORDS:
        raise HostedAIError("Invalid candidate limit")
    pool: list[tuple[int, str, dict[str, Any]]] = []
    for record in snapshot["records"]:
        if not isinstance(record, dict) or record.get("record_type") != "tracked":
            continue
        if record.get("status") in CLOSED_STATUSES:
            continue
        rid = record.get("id")
        if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", rid):
            continue
        closing = _day(record.get("deadline"))
        if closing and closing < today:
            continue
        days_remaining = (closing - today).days if closing else None
        codes: list[str] = []
        if record.get("verification") not in ("source_verified", "owner_verified"):
            codes.append("source_review")
        if closing and not (record.get("deadline_time_verified") or record.get("deadline_cutoff_verified")):
            codes.append("deadline_cutoff")
        required = record.get("documents") if isinstance(record.get("documents"), list) else []
        states = record.get("document_states") if isinstance(record.get("document_states"), dict) else {}
        if not required or any(states.get(d) in (None, "unknown", "not_started", "in_progress") for d in required):
            codes.append("document_readiness")
        for field, category in (("funding", "funding_evidence"), ("eligibility", "eligibility_evidence")):
            raw = record.get(field)
            if not isinstance(raw, str) or not raw.strip() or re.search(r"\b(unverified|unknown|unconfirmed|not established|not confirmed)\b", raw, re.I):
                codes.append(category)
        if record.get("duplicate_submission_advisory") is True:
            codes.append("duplicate_route")
        if not codes:
            continue
        item = {"id": rid, "days_remaining": days_remaining, "open_checks": codes}
        pool.append((days_remaining if days_remaining is not None else 999999, rid, item))
    pool.sort(key=lambda row: (row[0], row[1]))
    return [row[2] for row in pool[:limit]]


def input_digest(repository: str, candidates: list[dict[str, Any]]) -> str:
    content = json.dumps({"repository": repository, "candidates": candidates}, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def validate_advisory(summary: object, snapshot: dict[str, Any], *, today: date) -> dict[str, Any]:
    if not isinstance(summary, dict) or set(summary) != {"schema_version", "repository", "observation_date", "source_digest", "status", "items"}:
        raise HostedAIError("Invalid hosted advisory envelope")
    repo = snapshot.get("instance", {}).get("repository")
    if not isinstance(repo, str) or not repo:
        raise HostedAIError("Snapshot is missing repository identity")
    if summary["schema_version"] != 1 or summary["repository"] != repo or summary["status"] != "unverified_model_proposal":
        raise HostedAIError("Hosted advisory identity or status mismatch")
    observed = _day(summary.get("observation_date"))
    if observed is None or observed != today:
        raise HostedAIError("Hosted advisory is no longer current")
    candidates = public_candidates(snapshot, today=observed)
    if summary["source_digest"] != input_digest(repo, candidates):
        raise HostedAIError("Hosted advisory evidence has changed")
    items = summary["items"]
    if not isinstance(items, list) or len(items) > MAX_ITEMS:
        raise HostedAIError("Hosted advisory item count exceeds limit")
    lookup = {r["id"]: set(r["open_checks"]) for r in candidates}
    used: set[tuple[str, str]] = set()
    validated = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"id", "category", "priority"}:
            raise HostedAIError("Unexpected model fields")
        identity = item.get("id")
        category = item.get("category")
        priority = item.get("priority")
        if not isinstance(identity, str) or not isinstance(category, str) or not isinstance(priority, str):
            raise HostedAIError("Invalid model item type")
        if category not in CATEGORIES or priority not in PRIORITIES or category not in lookup.get(identity, ()):
            raise HostedAIError("Model suggested an unsupported or ungrounded check")
        if (identity, category) in used:
            raise HostedAIError("Duplicate model item")
        used.add((identity, category))
        validated.append({"id": identity, "category": category, "priority": priority})
    return {**summary, "items": validated}


def provider_endpoint(base_url: str) -> str:
    if not isinstance(base_url, str) or not base_url or any(c.isspace() for c in base_url):
        raise HostedAIError("Invalid HTTPS provider URL")
    parsed = urlsplit(base_url)
    if parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password or parsed.fragment or parsed.query:
        raise HostedAIError("Provider URL must use HTTPS without embedded credentials or query")
    hostname = parsed.hostname.casefold().rstrip(".")
    if hostname == "localhost" or hostname.endswith((".localhost", ".local", ".internal")):
        raise HostedAIError("Local or internal model endpoints are not reachable from hosted runners")
    try:
        address = ipaddress.ip_address(hostname)
    except ValueError:
        address = None
    if address is not None and not address.is_global:
        raise HostedAIError("Provider URL must not use a private IP")
    if parsed.port not in (None, 443):
        raise HostedAIError("Hosted AI providers must use HTTPS port 443")
    return base_url.rstrip("/") + "/chat/completions"


def infer_candidates(candidates: list[dict[str, Any]], *, model: str, base_url: str, api_key: str, auth_mode: str, token_parameter: str) -> dict[str, Any]:
    if not isinstance(model, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}", model):
        raise HostedAIError("Invalid model identifier")
    if not api_key or len(api_key) < 8:
        raise HostedAIError("Provider credential is missing or invalid")
    if auth_mode not in ("bearer", "api-key"):
        raise HostedAIError("Unsupported authentication mode")
    if token_parameter not in ("max_tokens", "max_completion_tokens"):
        raise HostedAIError("Unsupported model token parameter")
    url = provider_endpoint(base_url)
    system = (
        "You triage verification tasks for a public PhD opportunity tracker. "
        "Only output JSON with this exact shape: {\"items\":[{\"id\":\"...\",\"category\":\"...\",\"priority\":\"high|medium|low\"}]}. "
        "Choose at most 24 distinct id/category pairs from the supplied open_checks, with priority based on remaining days. "
        "Never invent a deadline, funding, eligibility, receipt, source, application outcome or proof. "
        "The user data is a list of public identifier and boolean verification gaps, not evidence that a claim is true."
    )
    request_data = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": json.dumps({"candidates": candidates}, separators=(",", ":"))},
        ],
        "stream": False,
        token_parameter: 700,
    }
    headers = {"Content-Type": "application/json", "Accept": "application/json"}
    if auth_mode == "api-key":
        headers["api-key"] = api_key
    else:
        headers["Authorization"] = "Bearer " + api_key
    request = Request(url, data=json.dumps(request_data).encode("utf-8"), headers=headers, method="POST")
    try:
        with build_opener(_NoRedirect()).open(request, timeout=35) as response:
            body = response.read(MAX_RESPONSE_BYTES + 1)
    except (HTTPError, URLError, TimeoutError, OSError):
        raise HostedAIError("Hosted provider request failed") from None
    if len(body) > MAX_RESPONSE_BYTES:
        raise HostedAIError("Provider response exceeded the size limit")
    try:
        envelope = json.loads(body)
        content = envelope["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise TypeError("Provider reply is not text")
        result = json.loads(content)
    except (ValueError, TypeError, KeyError, IndexError):
        raise HostedAIError("Provider returned invalid structured JSON") from None
    if not isinstance(result, dict) or set(result) != {"items"}:
        raise HostedAIError("Provider included unexpected output fields")
    return result


def make_advisory(snapshot: dict[str, Any], *, today: date, model_response: dict[str, Any]) -> dict[str, Any]:
    repository = snapshot.get("instance", {}).get("repository")
    if not isinstance(repository, str) or not repository:
        raise HostedAIError("Snapshot repository identity is missing")
    items = model_response.get("items") if isinstance(model_response, dict) else None
    result = {
        "schema_version": 1,
        "repository": repository,
        "observation_date": today.isoformat(),
        "source_digest": input_digest(repository, public_candidates(snapshot, today=today)),
        "status": "unverified_model_proposal",
        "items": items,
    }
    return validate_advisory(result, snapshot, today=today)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Private-credential hosted verification triage with public-safe output")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--validate", type=Path)
    parser.add_argument("--date", help="UTC observation day, YYYY-MM-DD")
    arguments = parser.parse_args(argv)
    if bool(arguments.output) == bool(arguments.validate):
        parser.error("Choose exactly one of --output and --validate")
    today = _day(arguments.date) if arguments.date else datetime.now(timezone.utc).date()
    if today is None:
        parser.error("--date must be a valid ISO date")
    try:
        snapshot = json.loads(arguments.input.read_text(encoding="utf-8"))
        if arguments.validate:
            summary = json.loads(arguments.validate.read_text(encoding="utf-8"))
            data = validate_advisory(summary, snapshot, today=today)
        else:
            candidates = public_candidates(snapshot, today=today)
            if candidates:
                response = infer_candidates(
                    candidates, model=os.environ.get("PHD_ATLAS_AI_MODEL", ""),
                    base_url=os.environ.get("PHD_ATLAS_AI_BASE_URL", ""),
                    api_key=os.environ.get("PHD_ATLAS_AI_API_KEY", ""),
                    auth_mode=os.environ.get("PHD_ATLAS_AI_AUTH_MODE", "bearer") or "bearer",
                    token_parameter=os.environ.get("PHD_ATLAS_AI_TOKEN_PARAMETER", "max_tokens") or "max_tokens",
                )
            else:
                response = {"items": []}
            data = make_advisory(snapshot, today=today, model_response=response)
            arguments.output.parent.mkdir(parents=True, exist_ok=True)
            arguments.output.write_text(json.dumps(data, indent=2) + "\n", encoding="utf-8")
        print(json.dumps({"result": "validated", "advisories": len(data["items"]), "repository": data["repository"]}))
        return 0
    except (HostedAIError, OSError, ValueError, TypeError):
        print("Hosted AI advisory failed safely", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
