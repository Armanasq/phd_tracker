from __future__ import annotations

import argparse
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

MARKER = "<!-- phd-intelligence-action-center-v1 -->"
STATUS = {"unconfirmed", "shortlisted", "preparing", "submitted", "interview", "offer", "rejected", "withdrawn", "blocked", "archived"}
VERIFY = {"unverified", "needs_review", "source_verified", "owner_verified"}
CONTACT = {"unrecorded", "to_contact", "contacted", "awaiting_reply", "followup_due", "replied", "declined", "completed"}
DOC = {"unknown", "ready", "in_progress", "not_started", "not_applicable"}
DOCUMENT_KEYS = {"academic_cv", "research_statement", "transcripts", "recommendations", "english_proof", "research_portfolio"}
FIELDS = {"id", "status", "verification", "followup", "contact_status", "next_step", "documents", "priority", "promoted", "expected_updated_at"}
ROOT = Path(__file__).resolve().parents[1]


def text(value: object, limit: int) -> str:
    if not isinstance(value, str):
        raise ValueError("Expected string")
    if len(value) > limit or any(ord(char) < 32 and char not in "\n\t" for char in value):
        raise ValueError("Invalid text length or control characters")
    return value.strip()


def url(value: object) -> str:
    if value in (None, ""):
        return ""
    item = text(value, 1000)
    parts = urlsplit(item)
    if parts.scheme != "https" or not parts.netloc or parts.username or parts.password:
        raise ValueError("Receipt URL must be HTTPS without user credentials")
    return item


def valid_date(value: object) -> str | None:
    if not value:
        return None
    v = text(value, 10)
    if not re.fullmatch(r"20\d\d-\d\d-\d\d", v):
        raise ValueError("Invalid follow-up date")
    from datetime import date
    date.fromisoformat(v)
    return v


def transform(event: dict, owner: str, known_ids: set[str], previous: dict) -> tuple[dict, dict]:
    comment = event.get("comment") or {}
    issue = event.get("issue") or {}
    body = str(comment.get("body") or "").strip()
    result = {"accepted": False, "reason": "not_workspace_command"}
    if not body.startswith("/workspace "):
        return previous, result
    if event.get("action") != "created" or issue.get("pull_request") or MARKER not in str(issue.get("body") or ""):
        return previous, {"accepted": False, "reason": "invalid_issue"}
    if str((comment.get("user") or {}).get("login") or "").casefold() != owner.casefold():
        return previous, {"accepted": False, "reason": "not_repository_owner"}
    cid = str(comment.get("id") or "")
    if not cid or cid in {str(x) for x in previous.get("processed_comment_ids", [])}:
        return previous, {"accepted": False, "reason": "duplicate_comment_or_missing_id"}
    if len(body) > 7000:
        return previous, {"accepted": False, "reason": "command_too_large"}
    try:
        payload = json.loads(body[len("/workspace "):])
        if not isinstance(payload, dict) or set(payload) - FIELDS:
            raise ValueError("Unknown command fields")
        rid = payload.get("id")
        if not isinstance(rid, str) or rid not in known_ids:
            raise ValueError("Application ID not in source registry")
        expected = payload.get("expected_updated_at")
        current_state = previous.get("records", {}).get(rid, {})
        if expected is not None:
            if not isinstance(expected, str) or len(expected) > 60:
                raise ValueError("Invalid source version")
            actual = str(current_state.get("updated_at") or "")
            if expected != actual:
                raise ValueError("source_version_conflict: reload source, compare edits, and reconcile")
        record = {}
        if "priority" in payload:
            level = text(payload["priority"], 12)
            if level not in {"low", "normal", "high"}:
                raise ValueError("Invalid priority")
            record["priority"] = level
        if "promoted" in payload:
            if payload["promoted"] is not True:
                raise ValueError("Promotion must be explicitly true")
            confirmation = payload.get("verification", current_state.get("verification", "unverified"))
            if confirmation not in {"source_verified", "owner_verified"}:
                raise ValueError("Verified official evidence is required before promotion")
            record["promoted"] = True
        for key in ("status", "verification", "contact_status"):
            if key in payload:
                value = text(payload[key], 50)
                if value not in {"status": STATUS, "verification": VERIFY, "contact_status": CONTACT}[key]:
                    raise ValueError("Unknown "+key)
                record[key] = value
        if "followup" in payload:
            record["followup"] = valid_date(payload["followup"])
        if "next_step" in payload:
            record["next_step"] = text(payload["next_step"], 650)
        if "documents" in payload:
            docs = payload["documents"]
            if not isinstance(docs, dict) or set(docs)-DOCUMENT_KEYS:
                raise ValueError("Unknown document keys")
            record["documents"] = {}
            for key,value in docs.items():
                if value not in DOC:
                    raise ValueError("Unknown document state")
                record["documents"][key] = value
        if len(record) == 0:
            raise ValueError("No changes supplied")
        output = json.loads(json.dumps(previous))
        current = output.setdefault("records", {}).get(rid, {})
        current.update(record)
        current["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        current["updated_from_issue_comment"] = cid
        output["records"][rid] = current
        output["processed_comment_ids"] = list(dict.fromkeys(output.get("processed_comment_ids", [])+[cid]))[-2000:]
        output["schema_version"] = 1
        return output, {"accepted": True, "id": rid, "fields": sorted(record), "comment_id": cid}
    except (ValueError, TypeError, json.JSONDecodeError) as exc:
        return previous, {"accepted": False, "reason": str(exc)[:180]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--output", default="data/workspace_control_result.json")
    parser.add_argument("--state", default="data/workspace_overrides.json")
    args = parser.parse_args()
    event = json.loads(Path(args.event).read_text(encoding="utf-8"))
    state_path = Path(args.state)
    existing = json.loads(state_path.read_text(encoding="utf-8")) if state_path.exists() else {"schema_version":1,"records":{},"processed_comment_ids":[]}
    exp = json.loads((ROOT/"data/experience_view.json").read_text(encoding="utf-8"))
    opp = json.loads((ROOT/"data/opportunities.json").read_text(encoding="utf-8"))
    ids = {x["id"] for x in exp["applications"] if x.get("id")} | {x["id"] for x in opp["records"] if x.get("id")}
    changed, result = transform(event, args.owner, ids, existing)
    if result["accepted"]:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(json.dumps(changed, indent=2, ensure_ascii=False)+"\n", encoding="utf-8")
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(result, indent=2)+"\n", encoding="utf-8")
    print(json.dumps(result))


if __name__ == "__main__":
    main()
