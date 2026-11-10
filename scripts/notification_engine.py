from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import date, datetime
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from openpyxl import load_workbook

if __package__:
    from .source_policy import classify_deadline_note
else:
    from source_policy import classify_deadline_note

ROOT = Path(__file__).resolve().parents[1]
STATE_PATH = ROOT / "data" / "notification_state.json"
REPORT_PATH = ROOT / "data" / "notification_report.json"
MARKER = "<!-- phd-intelligence-action-center-v1 -->"
MILESTONES = (0, 1, 3, 7, 14, 30)
CLOSED = {"submitted", "withdrawn", "rejected", "skipped", "not eligible", "accepted"}
ASSETS = {
    "CV": ("cv", "curriculum vitae", "resume"),
    "Research statement": ("sop", "statement of purpose", "motivation", "research proposal"),
    "Transcripts": ("transcript", "academic record", "diploma"),
    "Recommendations": ("referee", "reference letter", "recommendation"),
    "English proficiency": ("toefl", "ielts", "english test", "language certificate"),
}


def load(path: Path, fallback: dict) -> dict:
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else fallback


def clean(value: object, limit: int = 200) -> str:
    text = re.sub(r"[\r\n\t|]+", " ", str(value or "")).strip()[:limit]
    return text.replace("<", "&lt;").replace(">", "&gt;")


def date_value(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and re.fullmatch(r"20\d{2}-\d{2}-\d{2}", value):
        return date.fromisoformat(value)
    return None


def key_event(kind: str, source_id: str, date_label: str) -> str:
    return hashlib.sha256((kind + "|" + source_id + "|" + date_label).encode("utf-8")).hexdigest()[:20]


def milestone_for(days: int) -> int | None:
    return min((m for m in MILESTONES if days <= m), default=None) if days >= 0 else None


def evaluate(today: date, workbook: Path, data_dir: Path) -> dict:
    wb = load_workbook(workbook, read_only=True, data_only=False)
    if "Action list" not in wb:
        raise ValueError("Missing Action list")
    ws = wb["Action list"]
    upcoming: list[dict] = []
    potential_assets: dict[str, list[int]] = {}
    events: list[dict] = []
    for row in ws.iter_rows(min_row=4, max_col=21, values_only=True):
        due = date_value(row[1])
        if not due or not row[6] or not row[20]:
            continue
        if str(row[4] or "").strip().lower() in CLOSED:
            continue
        days = (due - today).days
        if days < 0:
            continue
        sid = str(row[20])
        deadline_type = classify_deadline_note(row[2])
        kind = {"final": "deadline", "priority": "priority", "unverified": "unverified_date"}[deadline_type]
        item = {"source_id": sid, "name": clean(row[6], 135), "deadline": due.isoformat(),
                "date_type": deadline_type, "days": days,
                "source": clean(row[19], 300), "next_step": clean(row[10], 250)}
        if days <= 45:
            upcoming.append(item)
        milestone = milestone_for(days)
        if milestone is None:
            continue
        events.append({**item, "kind": kind, "milestone": milestone,
                       "id": key_event(kind, sid, due.isoformat() + ":" + str(milestone))})
        all_text = " ".join(str(row[i] or "") for i in (10, 11, 12, 13, 14)).lower()
        for document, triggers in ASSETS.items():
            if any(term in all_text for term in triggers):
                potential_assets.setdefault(document, []).append(days)
    execution = load(data_dir / "execution_plan.json", {})
    daily = execution.get("today", {}).get("counts", {})
    if daily.get("total_distinct_scheduled_actions", 0) > 0:
        events.append({
            "id": key_event("daily_plan", today.isoformat(), "scheduled"),
            "kind":"daily_plan", "source_id":"daily-plan",
            "name":"Today's source-backed task agenda",
            "source":"docs/TODAY.md",
            "days":0,
            "evidence_status":"multiple_original_workbook_sheets",
            "counts":daily,
        })
    discovered = load(data_dir / "discovered_candidates.json", {"records": []})
    for hit in discovered.get("records", []):
        try:
            age = (today - date.fromisoformat(hit.get("first_seen", "")[:10])).days
        except ValueError:
            continue
        if not (0 <= age <= 21) or hit.get("score", 0) < 5:
            continue
        if hit.get("deadline") and hit["deadline"] < today.isoformat():
            continue
        sid = hit["id"]
        events.append({
            "id": key_event("new_lead", sid, "first-discovery"),
            "kind": "new_lead", "source_id": sid, "name": clean(hit["title"], 150),
            "deadline": hit.get("deadline"), "source": clean(hit.get("url"), 300),
            "evidence_status": "unverified_research_lead",
            "score": hit.get("score", 0),
        })
    radar = load(data_dir / "research_radar.json", {"papers": []})
    papers = []
    for paper in radar.get("papers", []):
        try:
            age = (today - date.fromisoformat(paper.get("first_seen", "")[:10])).days
        except ValueError:
            continue
        if 0 <= age <= 21 and paper.get("relevance_score", 0) >= 7:
            papers.append(paper)
    papers.sort(key=lambda p: (p.get("relevance_score", 0), p.get("published", "")), reverse=True)
    for paper in papers[:30]:
        events.append({
            "id": key_event("paper", paper["id"], "first-observed"),
            "kind": "research_signal", "source_id": paper["id"],
            "name": clean(paper["title"], 155), "source": paper["paper_url"],
            "evidence_status": "research_paper_not_vacancy",
        })
    run = load(data_dir / "latest_run.json", {})
    for record in run.get("source_statuses", []):
        status = record.get("status")
        if status in {"contradiction_closed_portal", "review_source_changed", "contradiction_deadline_mismatch"}:
            kind = "conflict"
        elif status in {"unavailable", "response_too_large", "disallowed_host", "unsafe_redirect"}:
            kind = "source_health"
        else:
            continue
        sid = record["id"]
        application = record.get("application_id", sid)
        events.append({
            "id": key_event(kind, sid, status),
            "kind": kind, "source_id": application, "monitor_id": sid, "name": application,
            "source": clean(record.get("source_url"), 300),
            "evidence_status": status,
        })
    discovery_health = load(data_dir / "discovery_report.json", {})
    for provider, stats in discovery_health.get("source_yield", {}).items():
        if stats.get("health") not in ("disabled", "degraded"):
            continue
        reason = "; ".join(discovery_health.get("source_errors", {}).get(provider, [])[:2])
        events.append({
            "id": key_event("coverage", provider, str(stats["health"])),
            "kind": "coverage_gap", "source_id": "provider:" + provider,
            "name": provider, "source": provider,
            "evidence_status": stats["health"], "detail": clean(reason, 210),
        })
    radar_health = load(data_dir / "research_radar_report.json", {})
    if radar_health.get("source_errors"):
        events.append({
            "id": key_event("coverage", "arxiv", "degraded"),
            "kind": "coverage_gap", "source_id": "provider:arxiv",
            "name": "arXiv research radar", "source": "arXiv",
            "evidence_status": "degraded",
            "detail": clean("; ".join(radar_health["source_errors"][:2]), 210),
        })
    assets = [
        {"document": name, "potential_applications": len(days),
         "nearest_deadline_days": min(days),
         "leverage_index": round(len(days) / (min(days) + 1), 4)}
        for name, days in potential_assets.items()
    ]
    assets.sort(key=lambda x: (-x["leverage_index"], -x["potential_applications"], x["document"]))
    events.sort(key=lambda x: (0 if x["kind"] == "conflict" else 1 if x["kind"] == "source_health" else 2 if x["kind"] == "deadline" else 3,
                               x.get("days", 9999), x["source_id"]))
    upcoming.sort(key=lambda x: (x["days"], x["source_id"]))
    return {"as_of": today.isoformat(), "upcoming": upcoming, "assets": assets, "events": events}


def apply_policy(events: list[dict], policy: dict, today: date) -> list[dict]:
    muted = set(policy.get("muted", []))
    priority = set(policy.get("priority", []))
    snoozes = policy.get("snoozed_until", {})
    selected = []
    for event in events:
        sid = event["source_id"]
        critical = event["kind"] in ("deadline", "priority") and event.get("days", 99) <= 1
        if not critical:
            if sid in muted:
                continue
            until = snoozes.get(sid)
            if until:
                try:
                    if date.fromisoformat(until) >= today:
                        continue
                except ValueError:
                    raise ValueError("Invalid snooze date for " + sid)
        selected.append(event)
    selected.sort(key=lambda x: (
        0 if x["kind"] == "conflict" else 1 if x["kind"] == "source_health" else 2,
        0 if x["source_id"] in priority else 1,
        0 if x["kind"] in ("deadline", "priority") else 1 if x["kind"] == "new_lead" else 2,
        x.get("days", 9999),
        x["source_id"],
    ))
    return selected


def outstanding(events: list[dict], state: dict, channel: str, limit: int = 30) -> list[dict]:
    previous = set(state.get(channel, []))
    return [r for r in events if r["id"] not in previous][:limit]


def distinct_daily_actions(daily: dict, *, limit: int = 13) -> list[str]:
    if not isinstance(daily, dict) or not 1 <= limit <= 100:
        raise ValueError("Invalid action digest input")
    sections = ("eligible_application_deadlines", "priority_review_dates",
                "unverified_application_dates", "cross_route_tasks", "scheduled_timeline_tasks")
    seen: set[tuple[str, str, str]] = set()
    lines: list[str] = []
    for section in sections:
        for task in daily.get(section, []):
            if not isinstance(task, dict):
                continue
            action = clean(task.get("action"), 150)
            name = clean(task.get("name"), 85)
            due = str(task.get("due") or task.get("deadline") or "")
            key = (" ".join(action.casefold().split()), " ".join(name.casefold().split()), due)
            if not action or key in seen:
                continue
            seen.add(key)
            lines.append("- " + action + " — " + name)
            if len(lines) >= limit:
                return lines
    return lines


def digest(evaluated: dict, selected: list[dict]) -> str:
    lines = [MARKER, "# PhD Intelligence — Action Center", "",
             "As of " + evaluated["as_of"] + " (UTC). A live page indicator is not a guarantee of eligibility.", "",
             "## Dated application milestones in the next 45 days", "",
             "| Days | Date | Type | Opportunity |", "|---:|---|---|---|"]
    for row in evaluated["upcoming"][:35]:
        lines.append(f'| {row["days"]} | {row["deadline"]} | {row["date_type"]} | {row["name"]} |')
    if not evaluated["upcoming"]:
        lines.append("| — | — | — | None in the next 45 days |")
    lines += ["", "## Portfolio leverage — documents to prepare once", "",
              "These are potentially required, not verified as missing. Rank = reuse count / (1 + closest deadline days).",
              "", "| Document | Relevant applications | Closest deadline |",
              "|---|---:|---:|"]
    for doc in evaluated["assets"][:8]:
        lines.append(f'| {doc["document"]} | {doc["potential_applications"]} | {doc["nearest_deadline_days"]}d |')
    frontier = load(ROOT / "data" / "portfolio_frontier.json", {})
    if frontier.get("applications"):
        lines += ["", "## Evidence debt and readiness unknowns", "",
                  "Flags describe evidence to verify, not conclusions about applicant eligibility or missing documents.", ""]
        flagged = [x for x in frontier["applications"] if x.get("evidence_proof_obligations") or x.get("unknown_resource_states")]
        for row in flagged[:10]:
            obligations = ", ".join(row.get("evidence_proof_obligations", [])[:2])
            resources = ", ".join(row.get("unknown_resource_states", [])[:3])
            detail = " | ".join(v for v in [obligations, "Unconfirmed: " + resources if resources else ""] if v)
            lines.append("- " + clean(row["opportunity"], 100) + " (" + str(row["days_to_deadline"]) + "d): " + clean(detail, 230))
    source_report = load(ROOT / "data" / "discovery_report.json", {})
    if source_report.get("source_yield"):
        lines += ["", "## Source coverage and discovery quality", "",
                  "| Source | Health | Observed | New unique |", "|---|---|---:|---:|"]
        for name, value in sorted(source_report["source_yield"].items()):
            lines.append(f'| {clean(name, 35)} | {clean(value["health"], 18)} | {value["observed"]} | {value["new_unique"]} |')
        lines += ["", "Disabled or degraded coverage is a real blind spot, not evidence of zero opportunities."]
    daily = load(ROOT / "data" / "execution_plan.json", {}).get("today", {})
    if daily:
        counted = daily.get("counts", {})
        lines += ["", "## Full-workbook execution plan — " + evaluated["as_of"], "",
                  "**" + str(counted.get("deadline_actions", 0)) + "** final application deadlines · " +
                  "**" + str(counted.get("priority_reviews", 0)) + "** priority-review dates · " +
                  "**" + str(counted.get("unverified_dates", 0)) + "** unverified dates · " +
                  "**" + str(counted.get("timeline_tasks", 0)) + "** scheduled programme steps · " +
                  "**" + str(counted.get("shared_tasks", 0)) + "** explicit cross-route tasks.",
                  "",
                  "These are separate clocks. Earlier steps associated with today's final deadline are not counted as tasks due today.",
                  ""]
        lines.extend(distinct_daily_actions(daily))
        lines += ["", "[Complete source-linked daily agenda](../blob/main/docs/TODAY.md)",
                  "[Editable Execution board and full Task ledger](../blob/main/PhD_Action_List.xlsx)"]
    lines += ["", "## Recently triggered notifications", ""]
    for item in selected[:20]:
        if item["kind"] == "deadline":
            lines.append(f'- Final deadline in {item["days"]}d: {item["name"]} ({item["deadline"]})')
        elif item["kind"] == "priority":
            lines.append(f'- Priority-review date (not final) in {item["days"]}d: {item["name"]} ({item["deadline"]})')
        elif item["kind"] == "unverified_date":
            lines.append(f'- Unverified application date in {item["days"]}d: {item["name"]} ({item["deadline"]})')
        elif item["kind"] == "daily_plan":
            lines.append("- Daily workbook task agenda ready: " + str(item["counts"].get("total_distinct_scheduled_actions", 0)) + " scheduled actions across all original sources.")
        elif item["kind"] == "new_lead":
            lines.append(f'- New unverified research lead: {item["name"]} ({item["source"]})')
        elif item["kind"] == "research_signal":
            lines.append(f'- Research paper, not a PhD vacancy: {item["name"]} ({item["source"]})')
        elif item["kind"] == "coverage_gap":
            lines.append(f'- Discovery coverage degraded or disabled: {item["name"]} — {item["detail"]}')
        elif item["kind"] == "source_health":
            lines.append(f'- Source monitor unavailable or unsafe: {item["source_id"]} ({item["evidence_status"]})')
        else:
            lines.append(f'- Conflicting evidence: {item["source_id"]} ({item["evidence_status"]})')
    if not selected:
        lines.append("- No new threshold crossings or conflicting evidence since the last notification.")
    lines += ["", "## Controls", "",
              "- Edit the workbook for application decisions. A research lead is never automatically marked eligible or submitted.",
              "- Sources: data/discovered_candidates.json and data/latest_run.json in the repository. Published repository contents are public when this fork is public.",
              "- To silence a completed application, set its verdict to Submitted, Skipped or Withdrawn.",
              "- Owner-only Issue controls: /priority APPLICATION_ID; /snooze APPLICATION_ID 3d; /mute APPLICATION_ID; /unsnooze APPLICATION_ID.",
              "- Explicit readiness controls: /asset academic_cv ready; /asset research_statement in_progress; /asset transcripts unknown.",
              "- Valid readiness states: unknown, ready, in_progress, not_started, not_applicable. These commands do not change submission status.",
              "- This Issue is maintained by a scheduled GitHub workflow. External messaging is disabled unless configured."]
    return "\n".join(lines)[:60000]


def comment_body(selected: list[dict]) -> str:
    lines = ["### New research signals and deadline thresholds", ""]
    for item in selected:
        if item["kind"] == "deadline":
            lines.append(f'- **{item["days"]} days to final deadline:** {item["name"]} — {item["deadline"]}')
        elif item["kind"] == "priority":
            lines.append(f'- **{item["days"]} days to priority review (NOT final):** {item["name"]} — {item["deadline"]}')
        elif item["kind"] == "unverified_date":
            lines.append(f'- **Unverified date in {item["days"]} days:** {item["name"]} — {item["deadline"]}')
        elif item["kind"] == "daily_plan":
            lines.append("- **Today\'s full-workbook agenda:** " + str(item["counts"].get("total_distinct_scheduled_actions", 0)) + " dated actions; see docs/TODAY.md (application deadlines and preparation tasks are distinct).")
        elif item["kind"] == "new_lead":
            lines.append(f'- **Needs verification:** {item["name"]} — {item["source"]}')
        elif item["kind"] == "research_signal":
            lines.append(f'- **Research only (not recruitment):** {item["name"]} — {item["source"]}')
        elif item["kind"] == "coverage_gap":
            lines.append(f'- **Discovery blind spot:** {item["name"]} — {item["detail"]}')
        elif item["kind"] == "source_health":
            lines.append(f'- **Source monitor outage:** {item["source_id"]}: {item["evidence_status"]} — {item["source"]}')
        else:
            lines.append(f'- **Contradiction:** {item["source_id"]}: {item["evidence_status"]} — {item["source"]}')
    lines.append("")
    lines.append("<!-- phd-notification-ids:" + ",".join(x["id"] for x in selected) + " -->")
    return "\n".join(lines)[:33000]


def gh_api(path: str, method: str = "GET", body: dict | None = None) -> object:
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    token = os.environ.get("GITHUB_TOKEN", "")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo) or not token:
        raise RuntimeError("GITHUB_REPOSITORY and GITHUB_TOKEN are required")
    payload = json.dumps(body).encode("utf-8") if body is not None else None
    request = Request("https://api.github.com/repos/" + repo + path, data=payload, method=method)
    request.add_header("Accept", "application/vnd.github+json")
    request.add_header("Authorization", "Bearer " + token)
    request.add_header("X-GitHub-Api-Version", "2022-11-28")
    with urlopen(request, timeout=25) as result:
        return json.loads(result.read(500000)) if result.status != 204 else {}


def github_issue(evaluated: dict, selected: list[dict]) -> None:
    issues = gh_api("/issues?state=all&per_page=100")
    old = next((x for x in issues if MARKER in (x.get("body") or "") and "pull_request" not in x), None)
    body = digest(evaluated, selected)
    if old:
        number = old["number"]
        if old.get("state") != "open":
            gh_api(f"/issues/{number}", "PATCH", {"state": "open"})
        if old.get("body") != body:
            gh_api(f"/issues/{number}", "PATCH", {"body": body})
    else:
        owner = os.environ["GITHUB_REPOSITORY"].split("/")[0]
        try:
            created = gh_api("/issues", "POST", {"title": "PhD Intelligence — Action Center",
                           "body": body, "assignees": [owner]})
        except HTTPError as exc:
            if exc.code != 422:
                raise
            created = gh_api("/issues", "POST", {"title": "PhD Intelligence — Action Center", "body": body})
        number = created["number"]
    if selected:
        recent = gh_api(f"/issues/{number}/comments?per_page=100")
        already = set()
        for item in recent:
            for block in re.findall(r"<!-- phd-notification-ids:([\w,]+) -->", item.get("body") or ""):
                already.update(block.split(","))
        new = [x for x in selected if x["id"] not in already]
        if new:
            gh_api(f"/issues/{number}/comments", "POST", {"body": comment_body(new)})


def external_notification(selected: list[dict]) -> bool:
    endpoint = os.environ.get("APPRISE_URLS", "").strip()
    if not endpoint or not selected:
        return False
    from apprise import Apprise
    app = Apprise()
    for line in endpoint.splitlines():
        if line.strip():
            app.add(line.strip())
    if not app:
        raise RuntimeError("APPRISE_URLS did not contain a valid destination")
    return bool(app.notify(title="PhD Intelligence — deadlines and new research", body=comment_body(selected)))


def run(today: date, send: bool, root: Path = ROOT) -> dict:
    evaluated = evaluate(today, root / "PhD_Action_List.xlsx", root / "data")
    state_path = root / "data" / "notification_state.json"
    state = load(state_path, {"version": 1, "github": [], "apprise": []})
    for key in ("github", "apprise"):
        state.setdefault(key, [])
    policy = load(root / "data" / "notification_preferences.json", {})
    active = apply_policy(evaluated["events"], policy, today)
    github_pending = outstanding(active, state, "github")
    apprise_pending = outstanding(active, state, "apprise")
    delivery = {"github": "not_requested", "apprise": "not_configured"}
    if send:
        github_issue(evaluated, github_pending)
        state["github"] = list(dict.fromkeys(state["github"] + [x["id"] for x in github_pending]))[-4000:]
        delivery["github"] = "delivered"
        if os.environ.get("APPRISE_URLS", "").strip():
            success = external_notification(apprise_pending)
            delivery["apprise"] = "delivered" if success else "failed"
            if success:
                state["apprise"] = list(dict.fromkeys(state["apprise"] + [x["id"] for x in apprise_pending]))[-4000:]
    report = {
        "as_of": today.isoformat(), "reminder_candidates": len(evaluated["events"]),
        "suppressed_by_user_policy": len(evaluated["events"]) - len(active),
        "github_new_events": len(github_pending), "apprise_new_events": len(apprise_pending),
        "upcoming_count": len(evaluated["upcoming"]), "potential_document_leverage": evaluated["assets"],
        "delivery": delivery,
    }
    (root / "data").mkdir(exist_ok=True)
    if send:
        state_path.write_text(json.dumps(state, indent=2) + "\n", encoding="utf-8")
    (root / "data" / "notification_report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as file:
            file.write(digest(evaluated, github_pending) + "\n")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    parser.add_argument("--send", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(date.fromisoformat(args.date), args.send), sort_keys=True))


if __name__ == "__main__":
    main()
