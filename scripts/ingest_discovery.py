from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "PhD_Action_List.xlsx"
DISCOVERED = ROOT / "data" / "discovered_candidates.json"
REPORT = ROOT / "data" / "ingestion_report.json"


def ingest(workbook: Path = BOOK, records_path: Path = DISCOVERED, report_path: Path = REPORT) -> dict:
    if not records_path.is_file():
        raise ValueError("Missing discovery results")
    data = json.loads(records_path.read_text(encoding="utf-8"))
    entries = data.get("records", [])
    wb = load_workbook(workbook)
    if "Research queue" not in wb or "Action list" not in wb:
        raise ValueError("Workbook must contain Research queue and Action list")
    queue = wb["Research queue"]
    action = wb["Action list"]
    known_ids = {str(queue.cell(i, 1).value) for i in range(2, queue.max_row + 1)}
    known_ids.update(str(action.cell(i, 21).value) for i in range(4, action.max_row + 1))
    known_urls = {str(queue.cell(i, 8).value).rstrip("/") for i in range(2, queue.max_row + 1) if queue.cell(i, 8).value}
    known_urls.update(str(action.cell(i, 20).value).rstrip("/") for i in range(4, action.max_row + 1) if action.cell(i, 20).value)
    inserted = 0
    skipped = 0
    for item in sorted(entries, key=lambda r: (-r.get("score", 0), str(r.get("deadline") or "9999"))):
        sid = item.get("id", "")
        url = item.get("url", "")
        if not sid or not url.startswith("https://"):
            skipped += 1
            continue
        if sid in known_ids or url.rstrip("/") in known_urls:
            skipped += 1
            continue
        raw_date = item.get("deadline")
        try:
            deadline = datetime.fromisoformat(raw_date) if raw_date else None
        except ValueError:
            deadline = None
        if deadline and deadline.date() < date.today():
            skipped += 1
            continue
        note = (item.get("deadline_provenance") or "Deadline not validated")
        confidence = item.get("evidence_status") or "search_lead_unverified"
        blockers = "Human review: confirm primary source, application is open, funding, nationality/tuition eligibility and time zone."
        if item.get("deadline_change_needs_review"):
            blockers += " Previously observed deadline differs; DO NOT overwrite existing deadline."
        row = [
            sid, deadline, item.get("title", ""), "Discovery relevance score " + str(item.get("score", 0)) + " (not an eligibility score)",
            "Needs verification — " + confidence,
            (item.get("snippet") or "")[:350] + " | " + note,
            url, url, "",
            "Open the original institution listing and verify requirements; promote only with confirmed evidence",
            blockers,
        ]
        queue.append(row)
        i = queue.max_row
        for c in range(1, 12):
            cell = queue.cell(i, c)
            cell.alignment = Alignment(vertical="top", wrap_text=True)
            cell.font = Font(name="Aptos", size=10, color="17603C" if c in (7, 8) else "222F40")
        queue.cell(i, 2).number_format = "yyyy-mm-dd"
        queue.row_dimensions[i].height = 52
        inserted += 1
        known_ids.add(sid)
        known_urls.add(url.rstrip("/"))
    queue.auto_filter.ref = f"A1:K{queue.max_row}"
    wb.save(workbook)
    report = {"date": date.today().isoformat(), "inspected": len(entries),
              "new_research_queue_rows": inserted, "deduplicated_or_deferred": skipped,
              "main_list_automatically_promoted": 0}
    report_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--workbook", default=str(BOOK))
    p.add_argument("--records", default=str(DISCOVERED))
    options = p.parse_args()
    print(json.dumps(ingest(Path(options.workbook), Path(options.records))))
