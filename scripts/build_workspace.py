from __future__ import annotations

import argparse
import json
import os
import re
from datetime import date, datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

if __package__:
    from .source_policy import classify_deadline_note_strict
    from .instance_config import DEFAULT_REPOSITORY, action_center_url, pages_url, repository_url, resolve_data_mode, resolve_repository
    from .deadline_cutoffs import normalize_cutoff
    from .hosted_ai_advisories import validate_advisory, HostedAIError
else:
    from source_policy import classify_deadline_note_strict
    from instance_config import DEFAULT_REPOSITORY, action_center_url, pages_url, repository_url, resolve_data_mode, resolve_repository
    from deadline_cutoffs import normalize_cutoff
    from hosted_ai_advisories import validate_advisory, HostedAIError

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


def source_links(repo: str) -> dict:
    base = repository_url(repo)
    independent = repo.casefold() != DEFAULT_REPOSITORY.casefold()
    return {
        "workbook": "" if independent else base + "/blob/main/PhD_Action_List.xlsx",
        "opportunities": base + "/blob/main/data/" + ("user_opportunities.json" if independent else "opportunities.json"),
        "source_monitor": base + "/actions/workflows/phd-intelligence.yml",
        "control_issue": action_center_url(repo),
        "repository": base,
    }


def instance_details(repo: str, mode: str) -> dict:
    return {
        "repository": repo,
        "type": "upstream" if repo.casefold() == DEFAULT_REPOSITORY.casefold() else "independent",
        "site_url": pages_url(repo, os.environ.get("PHD_ATLAS_SITE_URL")),
        "data_policy": "public_committed_snapshot",
        "data_mode": mode,
    }


def starter_snapshot(repo: str) -> dict:
    return {
        "schema_version": 1,
        "as_of": None,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "timezone": "UTC",
        "policy": "Independent starter workspace. No opportunity evidence has been imported or verified.",
        "privacy": "GitHub Pages is public; private applicant records belong in the local runtime.",
        "instance": instance_details(repo, "starter"),
        "meta": {
            "tracked": 0, "candidates": 0, "unpromoted_leads": 0,
            "discovery_snapshot": None, "notification_delivery": {},
        },
        "records": [], "leads": [], "archive": [], "tasks": [],
        "task_ledger": [], "duplicates": [], "providers": [], "watches": [],
        "coverage": {
            "workbook_audit_as_of": None, "worksheets": [], "files": [],
            "totals": {
                "tracked": 0, "research_candidates": 0, "reviewed_opportunity_notes": 0,
                "discovery_leads": 0, "historical_exclusions": 0, "task_projection": 0,
                "full_task_ledger": 0, "workbook_tabs": 0,
            },
            "discovery_errors": {},
        },
        "documents": DOCUMENTS, "global_document_states": {},
        "notes": [
            "The starter workspace intentionally contains no original maintainer application data.",
            "Provide your own reviewed source records and enable source mode before publishing them.",
            "Unknown evidence must remain unknown; no portal submission is inferred.",
        ],
        "source_links": source_links(repo),
    }


def independent_snapshot(root: Path, repo: str) -> dict:
    source = root / "data" / "user_opportunities.json"
    if not source.is_file():
        raise ValueError("Independent source mode requires data/user_opportunities.json; copied upstream records are never used")
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload, dict) or payload.get("schema_version") != 1 or not isinstance(payload.get("records"), list):
        raise ValueError("Independent source must contain schema_version=1 and a records array")
    if set(payload) - {"schema_version", "as_of", "timezone", "records"}:
        raise ValueError("Independent source has unexpected top-level fields")
    if len(payload["records"]) > 5000:
        raise ValueError("Independent source exceeds 5000 application records")
    from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
    timezone_name = payload.get("timezone", "UTC")
    if not isinstance(timezone_name, str) or len(timezone_name) > 80:
        raise ValueError("Invalid IANA timezone")
    try:
        ZoneInfo(timezone_name)
    except (ValueError, ZoneInfoNotFoundError) as exc:
        raise ValueError("Unrecognized IANA timezone") from exc
    if payload.get("as_of") and not iso_day(payload["as_of"]):
        raise ValueError("Invalid independent source observation date")
    allowed_fields = {
        "id", "record_type", "name", "institution", "country", "deadline", "deadline_kind",
        "deadline_type", "source_url", "apply_url", "source_date", "evidence", "verification",
        "status", "followup", "contact_status", "faculty", "funding", "eligibility",
        "fit", "topic", "next_step", "blockers", "decision", "documents", "document_states",
        "priority", "duplicate_submission_advisory",
        "deadline_time", "deadline_timezone", "deadline_cutoff_verified", "deadline_cutoff_evidence",
    }
    contacts = {"unrecorded", "to_contact", "contacted", "awaiting_reply", "followup_due", "replied", "declined", "completed"}
    verification_states = {"unverified", "needs_review", "source_verified", "owner_verified"}
    valid_deadlines = {"unverified", "final", "rolling", "internal", "other"}
    states = {"unknown", "ready", "in_progress", "not_started", "not_applicable"}
    overrides = load(root, "user_workspace_overrides.json").get("records", {})
    if not isinstance(overrides, dict):
        raise ValueError("Independent owner override data must be a mapping")
    results = []
    ids = set()
    for index, raw in enumerate(payload["records"]):
        if not isinstance(raw, dict) or set(raw) - allowed_fields:
            raise ValueError(f"Independent record {index + 1}: unsupported or private fields")
        rid = raw.get("id")
        if not isinstance(rid, str) or not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,79}", rid) or rid in ids:
            raise ValueError(f"Independent record {index + 1}: missing, unsafe or duplicate ID")
        ids.add(rid)
        name = clean(raw.get("name"), 350)
        if not name:
            raise ValueError(f"Independent record {rid}: name is required")
        if raw.get("record_type", "tracked") not in {"tracked", "candidate"}:
            raise ValueError(f"Independent record {rid}: invalid record type")
        owner = overrides.get(rid, {})
        if not isinstance(owner, dict):
            raise ValueError(f"Independent record {rid}: invalid owner override")
        status = owner.get("status", raw.get("status", "unconfirmed"))
        if status not in STATES:
            raise ValueError(f"Independent record {rid}: invalid status")
        verification = owner.get("verification", raw.get("verification", "unverified"))
        if verification not in verification_states:
            raise ValueError(f"Independent record {rid}: invalid verification state")
        deadline = iso_day(raw.get("deadline"))
        followup = iso_day(owner.get("followup", raw.get("followup")))
        source_date = iso_day(raw.get("source_date"))
        for key, val, parsed in (("deadline", raw.get("deadline"), deadline),
                                 ("followup", owner.get("followup", raw.get("followup")), followup),
                                 ("source_date", raw.get("source_date"), source_date)):
            if val not in (None, "") and parsed is None:
                raise ValueError(f"Independent record {rid}: invalid {key} date")
        source_url = public_url(raw.get("source_url"))
        apply_url = public_url(raw.get("apply_url"))
        for key, original, url in (("source_url", raw.get("source_url"), source_url),
                                   ("apply_url", raw.get("apply_url"), apply_url)):
            if original not in (None, "") and not url:
                raise ValueError(f"Independent record {rid}: {key} must be public HTTPS without credentials")
        evidence = clean(raw.get("evidence"), 440)
        if verification in {"source_verified", "owner_verified"} and not (source_url and source_date and evidence):
            raise ValueError(f"Independent record {rid}: verified status requires primary URL, observation date and evidence note")
        raw_docs = raw.get("documents", [])
        if not isinstance(raw_docs, list) or len(raw_docs) > len(DOCUMENTS) or any(doc not in DOCUMENTS for doc in raw_docs):
            raise ValueError(f"Independent record {rid}: invalid document requirements")
        documents = list(dict.fromkeys(raw_docs))
        raw_doc_states = raw.get("document_states", {})
        if not isinstance(raw_doc_states, dict) or any(k not in documents or v not in DOC_STATES for k, v in raw_doc_states.items()):
            raise ValueError(f"Independent record {rid}: invalid document states")
        owner_docs = owner.get("documents", {})
        if not isinstance(owner_docs, dict) or any(k not in DOCUMENTS or v not in DOC_STATES for k, v in owner_docs.items()):
            raise ValueError(f"Independent record {rid}: invalid confirmed document override")
        documents = sorted(set(documents) | set(owner_docs))
        doc_states = {key: owner_docs.get(key, raw_doc_states.get(key, "unknown")) for key in documents}
        priority = owner.get("priority", raw.get("priority", "normal"))
        if priority not in {"low", "normal", "high"}:
            raise ValueError(f"Independent record {rid}: invalid priority")
        contact_status = owner.get("contact_status", raw.get("contact_status", "unrecorded"))
        if contact_status not in contacts:
            raise ValueError(f"Independent record {rid}: invalid contact status")
        deadline_type = raw.get("deadline_type", "unverified")
        if deadline_type not in valid_deadlines:
            raise ValueError(f"Independent record {rid}: invalid deadline type")
        advisory = raw.get("duplicate_submission_advisory", False)
        if not isinstance(advisory, bool):
            raise ValueError(f"Independent record {rid}: invalid duplicate advisory")
        try:
            cutoff = normalize_cutoff(
                raw, deadline=deadline, verification=verification, source_url=source_url,
                source_date=source_date, deadline_type=deadline_type, evidence=evidence,
            )
        except ValueError as exc:
            raise ValueError(f"Independent record {rid}: {exc}") from exc
        cutoff["deadline_cutoff_evidence"] = clean(cutoff["deadline_cutoff_evidence"], 400)
        results.append({
            "id": rid, "record_type": "tracked" if raw.get("record_type") == "candidate" and owner.get("promoted") is True else raw.get("record_type", "tracked"),
            "name": name, "institution": clean(raw.get("institution"), 160),
            "country": clean(raw.get("country"), 70), "deadline": deadline,
            "deadline_kind": clean(raw.get("deadline_kind"), 200),
            "deadline_type": deadline_type, **cutoff,
            "verification": verification, "verification_note": evidence,
            "status": status, "status_confirmed": "status" in owner or "status" in raw,
            "submission_receipt": "", "documents": documents, "document_states": doc_states,
            "document_requirements_note": "", "followup": followup,
            "contact_status": contact_status,
            "faculty": clean(raw.get("faculty"), 160) or "Not recorded",
            "source_url": source_url, "secondary_url": "", "apply_url": apply_url,
            "source_date": source_date, "evidence": evidence,
            "funding": clean(raw.get("funding"), 400),
            "eligibility": clean(raw.get("eligibility"), 380),
            "fit": clean(raw.get("fit"), 260), "topic": clean(raw.get("topic"), 220),
            "next_step": clean(owner.get("next_step", raw.get("next_step")), 650),
            "blockers": clean(raw.get("blockers"), 420), "notes": "",
            "priority": priority, "decision": clean(raw.get("decision"), 80),
            "duplicate_submission_advisory": advisory,
            "recheck_required": verification not in {"source_verified", "owner_verified"},
            "updated_at": clean(owner.get("updated_at"), 50),
        })
    snapshot = starter_snapshot(repo)
    snapshot["instance"] = {**instance_details(repo, "source"), "source_file": "data/user_opportunities.json"}
    snapshot["as_of"] = iso_day(payload.get("as_of"))
    snapshot["timezone"] = timezone_name
    snapshot["policy"] = "Independent owner-supplied source snapshot. Verification claims require direct review of primary evidence."
    snapshot["records"] = results
    snapshot["meta"]["tracked"] = sum(r["record_type"] == "tracked" for r in results)
    snapshot["meta"]["candidates"] = sum(r["record_type"] == "candidate" for r in results)
    snapshot["duplicates"] = duplicate_advisories(results)
    snapshot["coverage"]["files"] = [
        {"name": "Independent owner opportunity source", "path": "data/user_opportunities.json",
         "description": "Public, owner-provided opportunities; review primary sources."}
    ]
    snapshot["coverage"]["totals"]["tracked"] = snapshot["meta"]["tracked"]
    snapshot["coverage"]["totals"]["research_candidates"] = snapshot["meta"]["candidates"]
    snapshot["notes"] = [
        "This snapshot was built from the current repository's independent opportunity source.",
        "Verified source claims must retain their primary URL and observation details.",
        "Private applicant correspondence and receipts are never permitted in this source format.",
    ]
    return snapshot


def attach_hosted_ai(root: Path, snapshot: dict) -> dict:
    path = root / "data" / "hosted_ai_advisories.json"
    snapshot["hosted_ai"] = {"state": "not_configured", "items": []}
    if not path.is_file():
        return snapshot
    try:
        entry = json.loads(path.read_text(encoding="utf-8"))
        validated = validate_advisory(entry, snapshot, today=datetime.now(timezone.utc).date())
    except (OSError, ValueError, TypeError, KeyError, HostedAIError):
        snapshot["hosted_ai"] = {"state": "stale_or_invalid", "items": []}
        return snapshot
    snapshot["hosted_ai"] = {
        "state": "current",
        "status": validated["status"],
        "observation_date": validated["observation_date"],
        "source_digest": validated["source_digest"],
        "items": validated["items"],
    }
    return snapshot


def build(root: Path = ROOT, *, repository: str | None = None, data_mode: str | None = None) -> dict:
    repo = resolve_repository(repository, root=root)
    mode = resolve_data_mode(repo, data_mode)
    if mode == "starter":
        return attach_hosted_ai(root, starter_snapshot(repo))
    if repo.casefold() != DEFAULT_REPOSITORY.casefold():
        return attach_hosted_ai(root, independent_snapshot(root, repo))
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
    full_task_ledger = [
        {
            "id": clean(item.get("task_id") or item.get("task_key"), 80),
            "application_id": clean(item.get("source_id"), 90),
            "name": clean(item.get("name"), 350),
            "action": clean(item.get("action"), 850),
            "due": iso_day(item.get("due")),
            "type": clean(item.get("type"), 60),
            "state": clean(item.get("state") or "unconfirmed", 80),
            "sheet": clean(item.get("sheet"), 90),
            "row": item.get("row") if isinstance(item.get("row"), int) else None,
            "source_url": public_url(item.get("source")),
        }
        for item in planner.get("all_tasks", [])
        if isinstance(item, dict) and (item.get("task_id") or item.get("task_key"))
    ]
    full_task_ledger.sort(key=lambda row: (row["due"] or "9999-12-31", row["id"]))
    if len({row["id"] for row in full_task_ledger}) != len(full_task_ledger):
        raise ValueError("Duplicate workbook task IDs in source ledger")
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
    source_files = [item for item in source_files if (root / item["path"]).is_file()]
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
            "full_task_ledger": len(full_task_ledger),
            "workbook_tabs": len(worksheets),
        },
        "discovery_errors": {
            clean(name, 80): [clean(error, 250) for error in errors[:4]]
            for name, errors in provider_report.get("source_errors", {}).items()
            if isinstance(errors, list) and errors
        },
    }
    return attach_hosted_ai(root, {
        "schema_version": 1, "as_of": as_of,
        "generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "timezone": experience.get("timezone", "Europe/Berlin"),
        "policy": "Source snapshot; no live deadline guarantee. Unknown document states are not missing. No applicant submission state is inferred.",
        "privacy": "Public Pages snapshot omits mailbox links, email addresses, personal correspondence bodies and historical exclusion reasons.",
        "instance": instance_details(repo, mode),
        "meta": {"tracked": sum(r["record_type"] == "tracked" for r in records), "candidates": sum(r["record_type"] == "candidate" for r in records), "unpromoted_leads": len(leads), "discovery_snapshot": provider_report.get("run_date"), "notification_delivery": notification.get("delivery", {})},
        "records": records, "leads": leads, "archive": archive, "tasks": tasks,
        "task_ledger": full_task_ledger,
        "coverage": coverage,
        "duplicates": groups, "providers": providers,
        "documents": DOCUMENTS, "global_document_states": global_document_status,
        "notes": [
            "Application state is unconfirmed unless the owner records a change.",
            "A document mentioned by a programme is not evidence that the applicant lacks it.",
            "A likely duplicate is a screening lead, not confirmation that submissions are interchangeable.",
            "The interface stores edits locally as drafts until a verified GitHub issue command is committed.",
        ],
        "source_links": source_links(repo),
        "watches": [{"id": clean(w.get("id"), 90), "source_url": public_url(w.get("url"))} for w in watchlist.get("watches", [])],
    })


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out", default="site/data/workspace.json")
    parser.add_argument("--repository", help="GitHub owner/repository (automatically detected in GitHub Actions)")
    parser.add_argument("--data-mode", choices=("starter", "source"), help="Public data mode; forks start without inherited applications")
    args = parser.parse_args()
    output = Path(args.out)
    output.parent.mkdir(parents=True, exist_ok=True)
    snapshot = build(repository=args.repository, data_mode=args.data_mode)
    ids = [r["id"] for r in snapshot["records"]]
    if len(ids) != len(set(ids)):
        raise ValueError("Duplicate source IDs in workspace projection")
    output.write_text(json.dumps(snapshot, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"records": len(ids), "tracked": snapshot["meta"]["tracked"], "leads": len(snapshot["leads"]), "duplicates_for_review": len(snapshot["duplicates"]), "output": str(output)}))


if __name__ == "__main__":
    main()
