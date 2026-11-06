from __future__ import annotations

import argparse
import copy
import hashlib
import html
import json
import re
import sys
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = Path(__file__).resolve().parents[1]
FILE = ROOT / "PhD_Action_List.xlsx"
OPPORTUNITIES = ROOT / "data" / "opportunities.json"
MAIL_SIGNALS = ROOT / "data" / "mail_signals.json"
WATCHLIST = ROOT / "data" / "watchlist.json"

ALLOWED_HOSTS = {
    "imprs.is.mpg.de",
    "graduate.engineering.gwu.edu",
    "www.humanities.manchester.ac.uk",
    "euraxess.ec.europa.eu",
    "www.epfl.ch",
}
HEADERS = [
    "#", "Deadline", "Date note", "Days left", "Verdict", "Fit", "Route",
    "Funding / eligibility line", "Apply at", "Contact", "Next step",
    "All steps (dated)", "Documents", "Recommenders", "English test",
    "Fee", "Blockers and risks", "Est. hours", "Group", "Info URL", "Source id",
]


def read_records(path: Path, key: str) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))[key]


def dt(value):
    if isinstance(value, datetime):
        return value
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time())
    if isinstance(value, str) and re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return datetime.fromisoformat(value)
    return None


def date_key(value):
    parsed = dt(value)
    return (0, parsed) if parsed else (1, datetime.max)


def make_main_row(rec: dict):
    source = rec["source_url"]
    steps = rec["next_step"]
    return [
        0, dt(rec["deadline"]), rec["deadline_kind"] + ". " + rec["evidence"],
        "", rec["decision"], rec["fit"], rec["name"],
        rec["funding"] + ". " + rec["eligibility"], rec["apply"],
        rec["contact"], steps, steps, rec["documents"], "",
        "Check institution-specific English rules", "", rec["blockers"],
        None, "", source, rec["id"],
    ]


def append_formatted_sheet(wb, name, columns, rows, key_column=None):
    ws = wb[name] if name in wb else wb.create_sheet(name)
    if ws.max_row < 2 or ws.cell(1, 1).value != columns[0]:
        ws.delete_rows(1, ws.max_row)
        for ci, heading in enumerate(columns, 1):
            cell = ws.cell(1, ci, heading)
            cell.fill = PatternFill("solid", fgColor="1B3552")
            cell.font = Font(bold=True, color="FFFFFF", size=10)
            cell.alignment = Alignment(wrap_text=True)
        ws.freeze_panes = "C2"
        ws.sheet_view.showGridLines = False
        ws.row_dimensions[1].height = 32
    if key_column is None:
        known = set()
    else:
        known = {str(ws.cell(i, key_column).value) for i in range(2, ws.max_row + 1)}
    for row in rows:
        if key_column is not None and str(row[key_column - 1]) in known:
            continue
        ws.append(row)
    ws.auto_filter.ref = f"A1:{ws.cell(1,len(columns)).column_letter}{ws.max_row}"
    for i, heading in enumerate(columns, 1):
        width = 12 if heading in ("Date", "Deadline", "Status", "Source ID") else 32
        if heading in ("Route", "Description", "Next step", "Blockers", "Finding"):
            width = 58
        if heading in ("Official URL", "Email URL", "Application link"):
            width = 45
        ws.column_dimensions[ws.cell(1, i).column_letter].width = width
    return ws


def monitor_one(watch: dict):
    url = watch["url"]
    host = (urlparse(url).hostname or "").lower()
    if urlparse(url).scheme != "https" or host not in ALLOWED_HOSTS:
        return watch["id"], "disallowed_host", "", ""
    try:
        req = Request(url, headers={"User-Agent": "PhDTrackerEvidenceMonitor/0.1", "Accept": "text/html"})
        with urlopen(req, timeout=15) as response:
            final_url = response.geturl()
            if (urlparse(final_url).hostname or "").lower() not in ALLOWED_HOSTS:
                return watch["id"], "unsafe_redirect", "", ""
            raw = response.read(800_000)
        s = raw.decode("utf-8", errors="replace")
        s = re.sub(r"(?is)<(script|style|noscript)[^>]*>.*?</\1>", " ", s)
        content = html.unescape(re.sub(r"(?s)<[^>]+>", " ", s))
        normalized = re.sub(r"\s+", " ", content).lower()
        found = watch["anchor"].lower() in normalized
        return watch["id"], "anchor_present" if found else "review_source_changed", hashlib.sha256(normalized.encode()).hexdigest(), ""
    except (HTTPError, URLError, TimeoutError, OSError, ValueError) as e:
        return watch["id"], "unavailable", "", str(e)[:120]


def update_watches(wb, watchlist: list[dict], online: bool, today: date):
    observed = {}
    if online:
        with ThreadPoolExecutor(max_workers=4) as pool:
            observed = {id_: (status, digest, error) for id_,status,digest,error in pool.map(monitor_one, watchlist)}
    cols = ["Source ID", "Official URL", "Expected deadline", "Expected evidence", "Last checked", "Status", "Content SHA256", "Review note"]
    rows = []
    for w in watchlist:
        status, digest, error = observed.get(w["id"], ("not_checked", "", "Offline: run online for status"))
        rows.append([w["id"], w["url"], w["expected_deadline"], w["anchor"], today, status, digest, error])
    ws = append_formatted_sheet(wb, "Source watch", cols, [])
    existing = {str(ws.cell(i, 1).value): i for i in range(2, ws.max_row + 1)}
    for row in rows:
        i = existing.get(row[0])
        if i:
            for j, value in enumerate(row, 1):
                ws.cell(i, j, value)
        else:
            ws.append(row)
    ws.auto_filter.ref = f"A1:H{ws.max_row}"


def refresh(wb, today: date, online: bool):
    opportunities = read_records(OPPORTUNITIES, "records")
    signals = read_records(MAIL_SIGNALS, "signals")
    watches = read_records(WATCHLIST, "watches")
    ws = wb["Action list"]
    if [ws.cell(3,i).value for i in range(1, 22)] != HEADERS:
        raise ValueError("Action list schema changed: refusing mutation")
    ws["B1"] = datetime.combine(today, datetime.min.time())
    current = [list(row) for row in ws.iter_rows(min_row=4, max_col=21, values_only=True) if row[6] and row[20]]
    ids = {str(row[20]) for row in current}
    for rec in opportunities:
        if not rec["id"] or not rec["source_url"].startswith("https://"):
            raise ValueError("Malformed candidate provenance")
        if rec["confidence"] == "official_plus_email" and rec["deadline"] and rec["id"] not in ids:
            current.append(make_main_row(rec))
            ids.add(rec["id"])
    current.sort(key=lambda row: (date_key(row[1]), str(row[6]).casefold()))
    last = 3 + len(current)
    for i, row in enumerate(current, 4):
        row[0] = i - 3
        row[3] = f'=IF(ISNUMBER(B{i}),B{i}-$B$1,"")'
        for j, value in enumerate(row, 1):
            ws.cell(i, j, value)
    for i in range(last + 1, ws.max_row + 1):
        for j in range(1, 22):
            ws.cell(i, j).value = None
    if last > 183:
        for i in range(184, last + 1):
            for j in range(1, 22):
                ws.cell(i,j)._style = copy.copy(ws.cell(183,j)._style)
    ws.auto_filter.ref = f"A3:U{last}"

    qcols = ["Source ID", "Deadline", "Route", "Fit", "Status", "Finding", "Application link", "Official URL", "Email URL", "Next step", "Blockers"]
    qrows = []
    for r in opportunities:
        if r["id"] not in ids:
            qrows.append([r["id"], dt(r["deadline"]), r["name"], r["fit"],
                          r["confidence"], r["evidence"], r["apply"], r["source_url"],
                          r["source_email"], r["next_step"], r["blockers"]])
    append_formatted_sheet(wb, "Research queue", qcols, qrows, 1)

    ecols = ["Source ID", "Date", "Subject", "Status", "Finding", "Email URL", "Next step"]
    erows = [[r["id"], dt(r["date"]), r["subject"], r["status"], r["impact"], r["message_url"], r["action"]] for r in signals]
    append_formatted_sheet(wb, "Mail signals", ecols, erows, 1)

    lcols = ["Source ID", "Date", "Route", "Official URL", "Email URL", "Confidence", "Finding", "Next step"]
    lrows = [[r["id"], dt(r["source_date"]), r["name"], r["source_url"], r["source_email"],
              r["confidence"], r["evidence"], r["next_step"]] for r in opportunities]
    append_formatted_sheet(wb, "Evidence ledger", lcols, lrows, 1)

    timeline = wb["Step timeline"]
    existing_steps = {str(timeline.cell(i,7).value) for i in range(4,timeline.max_row+1)}
    for r in opportunities:
        if r["id"] in ids and r["id"] not in existing_steps:
            timeline.append([dt(r["deadline"]), "", r["name"], r["decision"],
                            r["next_step"] + " [External deadline: " + r["deadline_kind"] + "]",
                            dt(r["deadline"]), r["id"]])
    timeline_rows = [list(v) for v in timeline.iter_rows(min_row=4,max_col=7,values_only=True) if v[2] and v[6]]
    timeline_rows.sort(key=lambda r:(date_key(r[0]),str(r[2]).casefold()))
    for i,r in enumerate(timeline_rows,4):
        r[1] = f'=IF(ISNUMBER(A{i}),A{i}-\'Action list\'!$B$1,"")'
        for j,v in enumerate(r,1):
            timeline.cell(i,j,v)
    timeline.auto_filter.ref=f"A3:G{3+len(timeline_rows)}"

    if "Read me" in wb:
        wb["Read me"]["A17"] = "Research update"
        wb["Read me"]["B17"] = "Evidence-backed 2026-11-06 review: official sources, user-authorized Gmail leads, separate research queue and source change monitoring. Gmail messages do not establish actual submission unless explicitly confirmed."
    update_watches(wb,watches,online,today)
    try:
        from openpyxl.workbook.properties import CalcProperties
        wb.calculation = CalcProperties(calcMode="auto", fullCalcOnLoad=True, forceFullCalc=True)
    except ImportError:
        pass
    return {"main_count":len(current),"new_verified_count":sum(r["id"] in ids for r in opportunities),
            "queue_count":len(qrows),"mail_signals":len(signals),"source_watches":len(watches)}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--date", default=date.today().isoformat())
    p.add_argument("--online", action="store_true")
    args=p.parse_args()
    today=date.fromisoformat(args.date)
    wb=load_workbook(FILE)
    result=refresh(wb,today,args.online)
    wb.save(FILE)
    print(json.dumps({**result,"date":today.isoformat(),"online":args.online},sort_keys=True))


if __name__ == "__main__":
    main()
