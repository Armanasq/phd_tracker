from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PREFERENCES = ROOT / "data" / "notification_preferences.json"
COMMAND = re.compile(r"^/(snooze|unsnooze|mute|unmute|priority|unpriority)\s+([A-Za-z0-9:_-]{1,80})(?:\s+([1-9]|[12][0-9]|30)d)?\s*$", re.I)
ASSET_COMMAND = re.compile(r"^/asset\s+([a-z][a-z0-9_]{2,60})\s+(ready|in_progress|not_started|unknown|not_applicable)\s*$", re.I)
MARKER = "<!-- phd-intelligence-action-center-v1 -->"


def known_ids(data: Path) -> set[str]:
    identifiers = set()
    for file, key in (
        ("discovered_candidates.json", "records"),
        ("opportunities.json", "records"),
    ):
        source = data / file
        if source.exists():
            identifiers.update(str(r["id"]) for r in json.loads(source.read_text(encoding="utf-8")).get(key, []) if r.get("id"))
    watchlist = data / "watchlist.json"
    if watchlist.exists():
        for w in json.loads(watchlist.read_text(encoding="utf-8")).get("watches", []):
            identifiers.add(str(w["id"]))
            identifiers.add(str(w.get("application_id", w["id"])))
    from openpyxl import load_workbook
    workbook = data.parent / "PhD_Action_List.xlsx"
    if workbook.exists():
        ws = load_workbook(workbook, read_only=True)["Action list"]
        identifiers.update(str(row[20]) for row in ws.iter_rows(min_row=4,max_col=21,values_only=True) if row[20])
    return identifiers


def parse(event: dict, owner: str, allowed: set[str], today: date, state: dict, asset_keys: set[str] | None = None) -> tuple[dict, dict]:
    comment = event.get("comment") or {}
    issue = event.get("issue") or {}
    comment_id = str(comment.get("id") or "")
    details = {"accepted": False, "reason": "ignored", "comment_id": comment_id}
    if event.get("action") != "created":
        return state, details
    if str((comment.get("user") or {}).get("login") or "").casefold() != owner.casefold():
        return state, details
    if MARKER not in str(issue.get("body") or "") or issue.get("pull_request"):
        return state, details
    if comment_id in {str(x) for x in state.get("processed_comment_ids", [])}:
        return state, {**details, "reason": "duplicate"}
    match = COMMAND.fullmatch(str(comment.get("body") or "").strip())
    if not match:
        asset = ASSET_COMMAND.fullmatch(str(comment.get("body") or "").strip())
        if not asset:
            return state, {**details, "reason": "unsupported_command"}
        resource, new_status = (x.lower() for x in asset.groups())
        if resource not in (asset_keys or set()):
            return state, {**details, "reason": "unknown_resource"}
        current = json.loads(json.dumps(state))
        current["processed_comment_ids"] = list(dict.fromkeys(current.get("processed_comment_ids", []) + [comment_id]))[-3000:]
        current["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        return current, {"accepted": True, "operation": "asset", "source_id": resource,
                         "new_status": new_status, "comment_id": comment_id}
    operation, source_id, days_text = match.groups()
    operation = operation.lower()
    if source_id not in allowed:
        return state, {**details, "reason": "unknown_application_id"}
    if operation == "snooze" and not days_text:
        return state, {**details, "reason": "snooze_requires_duration"}
    if operation != "snooze" and days_text:
        return state, {**details, "reason": "duration_only_valid_for_snooze"}
    current = json.loads(json.dumps(state))
    if operation == "snooze":
        current.setdefault("snoozed_until", {})[source_id] = (today + timedelta(days=int(days_text))).isoformat()
    if operation == "unsnooze":
        current.setdefault("snoozed_until", {}).pop(source_id, None)
    field = "muted" if operation in ("mute", "unmute") else "priority"
    if operation in ("mute", "priority"):
        current[field] = sorted(set(current.get(field, []) + [source_id]))
    if operation in ("unmute", "unpriority"):
        current[field] = sorted(set(current.get(field, [])) - {source_id})
    current["processed_comment_ids"] = list(dict.fromkeys(current.get("processed_comment_ids", []) + [comment_id]))[-3000:]
    current["updated_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return current, {"accepted": True, "operation": operation, "source_id": source_id,
                     "until": current.get("snoozed_until", {}).get(source_id), "comment_id": comment_id}


def apply(event_path: Path, preferences: Path, output: Path, owner: str, today: date) -> dict:
    event = json.loads(event_path.read_text(encoding="utf-8"))
    state = json.loads(preferences.read_text(encoding="utf-8"))
    assets_path = preferences.parent / "application_assets.json"
    assets = json.loads(assets_path.read_text(encoding="utf-8"))
    updated, result = parse(event, owner, known_ids(preferences.parent), today, state,
                            asset_keys=set(assets.get("resources", {})))
    if result["accepted"]:
        if result["operation"] == "asset":
            status = result["new_status"]
            if status not in assets["valid_statuses"]:
                raise ValueError("Invalid resource state")
            assets["resources"][result["source_id"]]["status"] = status
            assets_path.write_text(json.dumps(assets, indent=2) + "\n", encoding="utf-8")
        preferences.write_text(json.dumps(updated, indent=2) + "\n", encoding="utf-8")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--event", required=True)
    parser.add_argument("--owner", required=True)
    parser.add_argument("--preferences", default=str(PREFERENCES))
    parser.add_argument("--output", default=str(ROOT / "data" / "last_control_result.json"))
    args = parser.parse_args()
    print(json.dumps(apply(Path(args.event),Path(args.preferences),Path(args.output),
                           args.owner,date.today()),ensure_ascii=False))


if __name__ == "__main__":
    main()
