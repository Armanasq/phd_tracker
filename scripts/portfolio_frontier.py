from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

if __package__:
    from .source_policy import classify_deadline_note, primary_source_verified, summarize_watch_statuses
else:
    from source_policy import classify_deadline_note, primary_source_verified, summarize_watch_statuses

ROOT = Path(__file__).resolve().parents[1]
ASSETS_FILE = ROOT / "data" / "application_assets.json"
REPORT = ROOT / "data" / "portfolio_frontier.json"
BOOK = ROOT / "PhD_Action_List.xlsx"
TERMS = {
    "academic_cv": (" cv", "curriculum vitae", "resume", "academic cv"),
    "research_statement": ("sop", "statement of purpose", "motivation", "research statement", "research proposal"),
    "transcripts": ("transcript", "academic record", "diploma"),
    "recommendations": ("referee", "recommendation", "reference letter", "referees"),
    "english_proof": ("toefl", "ielts", "english proof", "language certificate", "english test"),
    "research_portfolio": ("publication", "research portfolio", "writing sample", "research papers"),
}
CLOSED = {"submitted", "withdrawn", "skipped", "rejected", "accepted", "not eligible"}
STATUSES = {"unknown", "ready", "in_progress", "not_started", "not_applicable"}


def extract_assets(text: str) -> list[str]:
    normalized = " " + re.sub(r"[\s\-]+", " ", text.casefold()).strip()
    return [k for k, parts in TERMS.items() if any(part in normalized for part in parts)]


def to_date(value: object) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str) and re.fullmatch(r"20\d{2}-\d{2}-\d{2}", value):
        return date.fromisoformat(value)
    return None


def evaluate(wb, assets: dict, today: date, opportunity_records: list[dict], latest: dict) -> dict:
    resources = assets["resources"]
    if any(v.get("status") not in STATUSES for v in resources.values()):
        raise ValueError("Application asset status outside allowed states")
    known = {r["id"]: r for r in opportunity_records}
    watches = summarize_watch_statuses(latest.get("source_statuses", []))
    entries = []
    leverage = defaultdict(lambda: {"mention_count": 0, "within_30_days": 0, "urgency_index": 0.0})
    ws = wb["Action list"]
    for row in ws.iter_rows(min_row=4, max_col=21, values_only=True):
        due = to_date(row[1])
        if not due or not row[6] or not row[20]:
            continue
        if str(row[4] or "").strip().casefold() in CLOSED:
            continue
        days = (due - today).days
        if days < 0:
            continue
        sid = str(row[20])
        deadline_type = classify_deadline_note(row[2])
        signals = extract_assets(" ".join(str(row[i] or "") for i in (10, 11, 12, 13, 14)))
        unresolved = [r for r in signals if resources.get(r, {}).get("status") not in ("ready", "not_applicable")]
        unknown = [r for r in unresolved if resources.get(r, {}).get("status", "unknown") == "unknown"]
        actionable = [r for r in unresolved if resources.get(r, {}).get("status") in ("in_progress", "not_started")]
        for item in unresolved:
            leverage[item]["mention_count"] += 1
            if days <= 30:
                leverage[item]["within_30_days"] += 1
                leverage[item]["urgency_index"] += 1 / (days + 1)
        evidence = []
        if sid in known:
            record = known[sid]
            if not primary_source_verified(record.get("confidence")):
                evidence.append("Position has not passed primary-source verification")
            if any(token in str(record.get("eligibility", "")).lower() for token in ("confirm", "not stated", "unverified")):
                evidence.append("Verify personal funding / eligibility before application")
        if deadline_type == "priority":
            evidence.append("This is a priority-review milestone, NOT the final application deadline")
        elif deadline_type == "unverified":
            evidence.append("Official final application date requires confirmation")
        watch_status = watches.get(sid)
        if watch_status in {"contradiction_closed_portal", "review_source_changed", "contradiction_deadline_mismatch"}:
            evidence.append("Official page requires rechecking: " + watch_status)
        elif watch_status in {"unavailable", "response_too_large", "disallowed_host", "unsafe_redirect"}:
            evidence.append("Source monitor unable to validate live page: " + watch_status)
        readiness = (
            "source_conflict" if any("Official page" in item for item in evidence) else
            "source_health_unverified" if any("Source monitor" in item for item in evidence) else
            "explicit_tasks_remaining" if actionable else
            "requires_readiness_confirmation" if unknown else
            "no_unresolved_detected_requirements"
        )
        entries.append({
            "source_id": sid,
            "deadline": due.isoformat(),
            "deadline_type": deadline_type,
            "days_to_deadline": days,
            "opportunity": str(row[6])[:230],
            "decision": str(row[4] or ""),
            "readiness": readiness,
            "document_mentions": signals,
            "unconfirmed_resources": unresolved,
            "unknown_resource_states": unknown,
            "explicit_tasks_remaining": actionable,
            "evidence_proof_obligations": evidence,
            "next_step": str(row[10] or "")[:400],
            "source_url": str(row[19] or "")[:500],
        })
    entries.sort(key=lambda x: (x["days_to_deadline"], len(x["evidence_proof_obligations"]), x["source_id"]))
    impact = [{"resource_id": key, "label": resources.get(key, {}).get("label", key),
               "current_state": resources.get(key, {}).get("status", "unknown"),
               "potential_applications": info["mention_count"],
               "near_term_applications": info["within_30_days"],
               "urgency_index": round(info["urgency_index"], 4)}
              for key, info in leverage.items()]
    impact.sort(key=lambda x: (-x["urgency_index"], -x["near_term_applications"], x["resource_id"]))
    return {
        "schema_version": 1,
        "as_of": today.isoformat(),
        "explicit_readiness_policy": "Unknown inputs remain unknown. Mentioned documents are not evidence of missing documents.",
        "active_future_opportunities": len(entries),
        "source_conflict_count": sum(x["readiness"] == "source_conflict" for x in entries),
        "source_health_warning_count": sum(x["readiness"] == "source_health_unverified" for x in entries),
        "resource_frontier": impact,
        "applications": entries,
    }


def workbook_frontier(wb, report: dict) -> None:
    name = "Decision frontier"
    ws = wb[name] if name in wb else wb.create_sheet(name)
    if ws.max_row:
        ws.delete_rows(1, ws.max_row)
    header = ["Source ID", "Deadline", "Days", "Opportunity", "Current decision",
              "Evidence/readiness state", "Resources mentioned", "Readiness to confirm",
              "Provenance obligations", "Next step", "Source URL"]
    ws.append(header)
    for item in report["applications"]:
        ws.append([
            item["source_id"], datetime.fromisoformat(item["deadline"]),
            item["days_to_deadline"], item["opportunity"], item["decision"],
            item["readiness"], ", ".join(item["document_mentions"]),
            ", ".join(item["unconfirmed_resources"]),
            " | ".join(item["evidence_proof_obligations"]),
            item["next_step"], item["source_url"],
        ])
    ws.freeze_panes = "D2"
    ws.sheet_view.showGridLines = False
    ws.auto_filter.ref = f"A1:K{ws.max_row}"
    for j in range(1, 12):
        cell = ws.cell(1, j)
        cell.fill = PatternFill("solid", fgColor="132D4E")
        cell.font = Font(name="Aptos", color="FFFFFF", bold=True, size=10)
        cell.alignment = Alignment(vertical="center", wrap_text=True)
    ws.row_dimensions[1].height = 34
    widths = [25, 15, 10, 76, 22, 33, 50, 48, 62, 70, 55]
    for col, width in enumerate(widths, 1):
        ws.column_dimensions[ws.cell(1, col).column_letter].width = width
    for i in range(2, ws.max_row + 1):
        ws.row_dimensions[i].height = 49
        ws.cell(i, 2).number_format = "yyyy-mm-dd"
        state = str(ws.cell(i, 6).value or "")
        ws.cell(i, 6).font = Font(
            name="Aptos", size=10,
            color="B45309" if state.startswith("requires") or state.startswith("source") else "155E75")
        for j in range(1, 12):
            ws.cell(i, j).alignment = Alignment(vertical="top", wrap_text=True)


def run(workbook: Path = BOOK, config: Path = ASSETS_FILE, report_path: Path = REPORT, today: date | None = None) -> dict:
    today = today or date.today()
    assets = json.loads(config.read_text(encoding="utf-8"))
    root = config.resolve().parent
    opportunities = json.loads((root / "opportunities.json").read_text(encoding="utf-8")).get("records", []) if (root / "opportunities.json").exists() else []
    latest = json.loads((root / "latest_run.json").read_text(encoding="utf-8")) if (root / "latest_run.json").exists() else {}
    wb = load_workbook(workbook)
    result = evaluate(wb, assets, today, opportunities, latest)
    workbook_frontier(wb, result)
    wb.save(workbook)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"as_of":result["as_of"],"active_opportunities":result["active_future_opportunities"],
            "source_conflicts":result["source_conflict_count"],"resource_frontier":result["resource_frontier"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    opts = parser.parse_args()
    print(json.dumps(run(today=date.fromisoformat(opts.date)), ensure_ascii=False))
