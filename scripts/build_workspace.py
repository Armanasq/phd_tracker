from __future__ import annotations

import argparse
import json
import re
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

if __package__:
    from .source_policy import classify_deadline_note_strict
else:
    from source_policy import classify_deadline_note_strict

ROOT = Path(__file__).resolve().parents[1]
DOCUMENTS = {
    "academic_cv": "Academic CV",
    "research_statement": "Research statement / SOP",
    "transcripts": "Official transcripts",
    "recommendations": "Reference letters",
    "english_proof": "English proficiency",
    "research_portfolio": "Research portfolio",
}
STATES = {"unconfirmed", "shortlisted", "preparing", "submitted", "interview", "offer", "rejected", "withdrawn", "blocked", "archived"}
DOC_STATES = {"unknown", "ready", "in_progress", "not_started", "not_applicable"}


def load(root: Path, name: str, fallback: dict | None = None) -> dict:
    path = root / "data" / name
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else (fallback or {})


def public_url(value: object) -> str:
    if not isinstance(value, str):
        return ""
    try:
        parsed = urlsplit(value.strip())
    except ValueError:
        return ""
    if parsed.scheme != "https" or not parsed.hostname:
        return ""
    host = parsed.hostname.lower()
    if host in {"mail.google.com", "accounts.google.com", "gmail.com"}:
        return ""
    if parsed.username or parsed.password:
        return ""
    return urlunsplit((parsed.scheme, parsed.netloc, parsed.path, "", ""))


def clean(value: object, limit: int = 1500) -> str:
    text = re.sub(r"[\x00-\x1f\x7f]", " ", str(value or ""))
    text = re.sub(r"\b[A-Z0-9._%+\-]+@[A-Z0-9.\-]+\.[A-Z]{2,}\b", "[email withheld]", text, flags=re.I)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit]


def iso_day(value: object) -> str | None:
    try:
        day = date.fromisoformat(str(value or ""))
        return day.isoformat()
    except ValueError:
        return None


def title_match(left: str, right: str) -> float:
    def normalize(s: str) -> str:
        return re.sub(r"[^a-z0-9]+", " ", s.casefold()).strip()
    return SequenceMatcher(None, normalize(left), normalize(right)).ratio()


def duplicate_advisories(records: list[dict]) -> list[dict]:
    result = []
    for index, left in enumerate(records):
        for right in records[index + 1:]:
            if left["id"] == right["id"]:
                continue
            confidence = title_match(left["name"], right["name"])
            same_url = bool(left["source_url"] and left["source_url"] == right["source_url"])
            if confidence >= 0.94 or (confidence >= 0.84 and same_url):
                result.append({"ids": [left["id"], right["id"]], "reason": "Similar programme title" + (" and shared source URL" if same_url else ""), "similarity": round(confidence, 3), "certainty": "possible_duplicate_not_confirmed"})
    return sorted(result, key=lambda d: -d["similarity"])[:100]


def build(root: Path = ROOT) -> dict:
    experience = load(root, "experience_view.json")
    frontier = load(root, "portfolio_frontier.json")
    details = {str(r["id"]): r for r in load(root, "opportunities.json").get("records", []) if r.get("id")}
    queue = {str(r["id"]): r for r in load(root, "decision_queue.json").get("items", []) if r.get("id")}
    assets = load(root, "application_assets.json")
    discovery = load(root, "discovered_candidates.json")
    provider_report = load(root, "discovery_report.json")
    overrides = load(root, "workspace_overrides.json", {"records": {}})
    excluded = load(root, "exclusion_memory.json")
    planner = load(root, "execution_plan.json")
    notification = load(root, "notification_report.json")
    watchlist = load(root, "watchlist.json")
    workbook_audit = load(root, "workbook_audit.json")
    portfolio = {str(x["source_id"]): x for x in frontier.get("applications", []) if x.get("source_id")}
    by_id = {}
    global_document_status = {
        k: v.get("status", "unknown") for k, v in assets.get("resources", {}).items()
    }

    def make_record(source: dict, record_type: str) -> dict:
        rid = str(source.get("id", ""))
        detail = details.get(rid, {})
        queued = queue.get(rid, {})
        extra = portfolio.get(rid, {})
        owner = overrides.get("records", {}).get(rid, {})
        doc_mentions = source.get("documents", extra.get("document_mentions", []))
        if not doc_mentions and detail.get("documents"):
            words = str(detail["documents"]).casefold()
            doc_mentions = [key for key, hints in {
                "academic_cv": ("cv", "resume"),
                "research_statement": ("statement", "proposal", "motivation"),
                "transcripts": ("transcript", "academic record"),
                "recommendations": ("reference", "referee", "recommendation"),
                "english_proof": ("english", "toefl", "ielts"),
                "research_portfolio": ("publication", "portfolio"),
            }.items() if any(hint in words for hint in hints)]
        doc_mentions = sorted({d for d in doc_mentions if d in DOCUMENTS})
        doc_status = {key: owner.get("documents", {}).get(key, global_document_status.get(key, "unknown")) for key in doc_mentions}
        status = owner.get("status", "unconfirmed")
        if status not in STATES:
            status = "unconfirmed"
        verification = owner.get("verification") or (
            "source_verified" if queued.get("research_status") == "source_verified" else
            "needs_review" if queued.get("research_status") == "human_review_required" else "unverified"
        )
        name = clean(source.get("name") or source.get("title") or detail.get("name"), 350)
        date_str = iso_day(source.get("deadline") or detail.get("deadline"))
        application_link = public_url(detail.get("apply"))
        source_link = public_url(source.get("source") or detail.get("source_url") or queued.get("official_source"))
        secondary_link = public_url(detail.get("secondary_url"))
        contacts = clean(detail.get("contact", ""), 160)
        if contacts == "[email withheld]":
            contacts = ""
        next_step = clean(owner.get("next_step") or source.get("next_step") or queued.get("next_step") or detail.get("next_step"), 650)
        raw_deadline_note = str(detail.get("deadline_kind") or extra.get("deadline_type") or queued.get("deadline_kind") or "")
        deadline_type = classify_deadline_note_strict(raw_deadline_note) if date_str else "unverified"
        explicit_joint = any(phrase in (str(detail.get("blockers", ""))+" "+next_step).casefold() for phrase in (
            "do not submit twice", "not independently", "joint application", "same application", "not a separate application",
            "either application", "via this or", "this or gatsby", "or gatsby application",
        ))
        return {
            "id": rid, "record_type": "tracked" if record_type == "candidate" and owner.get("promoted") is True else record_type, "name": name,
            "country": clean(source.get("country") or "", 70),
            "institution": clean(detail.get("route") or "", 160),
            "deadline": date_str, "deadline_kind": clean(raw_deadline_note, 200),
            "deadline_type": deadline_type, "verification": verification,
            "verification_note": clean(queued.get("obligations", []) if queued else "", 500),
            "status": status, "status_confirmed": bool(owner.get("status")),
            "submission_receipt": "",
            "documents": doc_mentions, "document_states": doc_status,
            "document_requirements_note": clean(detail.get("documents"), 500),
            "followup": iso_day(owner.get("followup")),
            "contact_status": clean(owner.get("contact_status"), 60) or "unrecorded",
            "faculty": contacts or "Not recorded",
            "source_url": source_link, "secondary_url": secondary_link,
            "apply_url": application_link,
            "source_date": iso_day(detail.get("source_date")),
            "evidence": clean(detail.get("evidence") or queued.get("research_status"), 440),
            "funding": clean(detail.get("funding"), 400),
            "eligibility": clean(detail.get("eligibility"), 380),
            "fit": clean(detail.get("fit"), 260),
            "topic": clean(detail.get("field"), 220),
            "next_step": next_step,
            "blockers": clean(detail.get("blockers"), 420),
            "notes": "", "priority": owner.get("priority") if owner.get("priority") in {"normal", "low", "high"} else "normal",
            "decision": clean(source.get("decision") or detail.get("decision") or "", 80),
            "duplicate_submission_advisory": bool(explicit_joint),
            "recheck_required": verification not in {"source_verified", "owner_verified"},
            "updated_at": clean(owner.get("updated_at"), 50),
        }

    records = [make_record(a, "tracked") for a in experience.get("applications", []) if a.get("id")]
    seen = {r["id"] for r in records}
    for rid, value in details.items():
        if rid not in seen:
            records.append(make_record({"id": rid, **value}, "candidate"))
            seen.add(rid)
    leads = []
    for value in discovery.get("records", []):
        rid = str(value.get("id", ""))
        if not rid or rid in seen:
            continue
        leads.append({
            "id": rid, "name": clean(value.get("title"), 350), "deadline": iso_day(value.get("deadline")),
            "source_url": public_url(value.get("url")), "provider": clean(value.get("provider"), 80),
            "evidence_status": clean(value.get("evidence_status") or "unverified", 100),
            "funding": clean(value.get("funding_status"), 280),
            "observed_at": clean(value.get("last_seen") or value.get("observed_at"), 40),
            "record_type": "discovery_unpromoted",
        })
    archive = [{
        "id": clean(x.get("source_id"), 90), "name": clean(x.get("route"), 270),
        "status": clean(x.get("type") or x.get("status") or "Excluded", 70),
        "note": "Historical workbook exclusion; inspect the original record before reinstatement."
    } for x in excluded.get("entries", []) if x.get("source_id") not in seen][:250]
    as_of = iso_day(experience.get("as_of")) or date.today().isoformat()
    tasks = []
    for item in planner.get("all_tasks", []):
        if item.get("type") not in {"timeline_step", "cross_route_task"}:
            continue
        due = iso_day(item.get("due"))
        if not due:
            continue
        days = (date.fromisoformat(due) - date.fromisoformat(as_of)).days
        if not -7 <= days <= 120:
            continue
        tasks.append({
            "id": clean(item.get("task_id") or item.get("task_key"), 80),
            "application_id": clean(item.get("source_id"), 90),
            "name": clean(item.get("name"), 240),
            "action": clean(item.get("action"), 500),
            "due": due, "state": clean(item.get("state") or "unconfirmed", 70),
            "type": clean(item.get("type"), 60),
        })
    tasks.sort(key=lambda item: (item["due"], item["id"]))
    groups = duplicate_advisories(records)
    providers = [{
        "name": name, "health": spec.get("health", "unknown"),
        "observed": spec.get("observed", 0), "new_unique": spec.get("new_unique", 0)
    } for name, spec in provider_report.get("source_yield", {}).items()]
    worksheets = [
        {
            "name": clean(name, 100),
            "populated_rows": int(info.get("populated_rows", 0)),
            "today_count": int(info.get("today_count", 0)),
            "next_7_count": int(info.get("next_7_count", 0)),
        }
        for name, info in workbook_audit.get("sheets", {}).items()
        if isinstance(info, dict)
    ]
    source_files = [
        {"name": "Original application workbook", "path": "PhD_Action_List.xlsx", "description": "The full workbook; worksheet rows are not distinct applications."},
        {"name": "Enriched opportunity notes", "path": "data/opportunities.json", "description": "Reviewed programme records and primary source references."},
        {"name": "Curated application projection", "path": "data/experience_view.json", "description": "Tracked opportunities currently presented in the workspace."},
        {"name": "Workbook structural audit", "path": "data/workbook_audit.json", "description": "Sheet-level counts, dates and workbook structure."},
        {"name": "Full execution plan", "path": "data/execution_plan.json", "description": "Historical and upcoming workbook task events."},
        {"name": "Source discovery report", "path": "data/discovery_report.json", "description": "Feed health and observed discovery limitations."},
        {"name": "Discovered research leads", "path": "data/discovered_candidates.json", "description": "Unpromoted, provisional opportunity candidates."},
        {"name": "Exclusion memory", "path": "data/exclusion_memory.json", "description": "Previously excluded and deferred routes."},
        {"name": "Notification report", "path": "data/notification_report.json", "description": "Notification configuration and recorded delivery summary."},
        {"name": "Source monitoring watchlist", "path": "data/watchlist.json", "description": "Official source links tracked for changes."},
        {"name": "Portfolio evidence frontier", "path": "data/portfolio_frontier.json", "description": "Heuristic research-fit records, not admission probabilities."},
    ]
    coverage = {
        "workbook_audit_as_of": iso_day(workbook_audit.get("as_of")),
        "worksheets": worksheets,
        "files": source_files,
        "totals": {
            "tracked": sum(row["record_type"] == "tracked" for row in records),
            "research_candidates": sum(row["record_type"] == "candidate" for row in records),
            "reviewed_opportunity_notes": len(details),
            "discovery_leads": len(leads),
            "historical_exclusions": len(archive),
            "task_projection": len(tasks),
            "workbook_tabs": len(worksheets),
        },
        "discovery_errors": {
            clean(name, 80): [clean(error, 250) for error in errors[:4]]
            for name, errors in provider_report.get("source_errors", {}).items()
            if isinstance(errors, list) and errors
        },
    }
    return {
        "schema_version": 1, "as_of": as_of,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "timezone": experience.get("timezone", "Europe/Berlin"),
        "policy": "Source snapshot; no live deadline guarantee. Unknown document states are not missing. No applicant submission state is inferred.",
        "privacy": "Public Pages snapshot omits mailbox links, email addresses, personal correspondence bodies and historical exclusion reasons.",
        "meta": {"tracked": sum(r["record_type"] == "tracked" for r in records), "candidates": sum(r["record_type"] == "candidate" for r in records), "unpromoted_leads": len(leads), "discovery_snapshot": provider_report.get("run_date"), "notification_delivery": notification.get("delivery", {})},
        "records": records, "leads": leads, "archive": archive, "tasks": tasks,
        "coverage": coverage,
        "duplicates": groups, "providers": providers,
        "documents": DOCUMENTS, "global_document_states": global_document_status,
        "notes": [
            "Application state is unconfirmed unless the owner records a change.",
            "A document mentioned by a programme is not evidence that the applicant lacks it.",
            "A likely duplicate is a screening lead, not confirmation that submissions are interchangeable.",
            "The interface stores edits locally as drafts until a verified GitHub issue command is committed.",
        ],
        "source_links": {
            "workbook": "https://github.com/Armanasq/phd_tracker/blob/main/PhD_Action_List.xlsx",
            "opportunities": "https://github.com/Armanasq/phd_tracker/blob/main/data/opportunities.json",
            "source_monitor": "https://github.com/Armanasq/phd_tracker/actions/workflows/phd-intelligence.yml",
            "control_issue": "https://github.com/Armanasq/phd_tracker/issues/1",
            "repository": "https://github.com/Armanasq/phd_tracker",
        },
        "watches": [{"id": clean(w.get("id"), 90), "source_url": public_url(w.get("url"))} for w in watchlist.get("watches", [])],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="site/data/workspace.json")
    args = parser.parse_args()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot = build()
    ids = [r["id"] for r in snapshot["records"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source IDs in workspace projection")
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(ids), "tracked": snapshot["meta"]["tracked"], "leads": len(snapshot["leads"]), "duplicates_for_review": len(snapshot["duplicates"]), "output": str(output)}))


if __name__ == "__main__":
    main()
