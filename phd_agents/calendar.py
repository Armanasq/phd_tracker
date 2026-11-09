from __future__ import annotations

import re
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

def clean(value: object) -> str:
    return re.sub(r"[\\,;\r\n]", lambda m: {"\\": "\\\\", ",": "\\,", ";": "\\;", "\r": "", "\n": "\\n"}[m.group(0)], str(value or ""))[:300]

def line_items(records: list[dict[str, Any]], events: list[dict[str, Any]],
               references: list[dict[str, Any]]) -> str:
    catalog = {r["id"]: r["name"] for r in records}
    entries: list[str] = []
    def append(identifier: str, title: str, day: str, clock: str | None = None, tz: str | None = None, note: str = "") -> None:
        start = date.fromisoformat(day)
        uid = re.sub(r"[^a-zA-Z0-9_.-]", "-", identifier) + "@phd-atlas-private"
        if clock and tz:
            local = datetime.fromisoformat(day + "T" + clock).replace(tzinfo=ZoneInfo(tz))
            stamp = "DTSTART:" + local.astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
            finish = "DTEND:" + (local + timedelta(minutes=30)).astimezone(ZoneInfo("UTC")).strftime("%Y%m%dT%H%M%SZ")
        else:
            stamp = "DTSTART;VALUE=DATE:" + start.strftime("%Y%m%d")
            finish = "DTEND;VALUE=DATE:" + (start + timedelta(days=1)).strftime("%Y%m%d")
        entries.append("\r\n".join(["BEGIN:VEVENT", "UID:" + uid, stamp, finish,
                                   "SUMMARY:" + clean(title), "DESCRIPTION:" + clean(note), "END:VEVENT"]))
    for event in events:
        if not event.get("date"):
            continue
        title = catalog.get(event.get("application_id"), event.get("application_id", "Application"))
        clock = event.get("time") if event.get("cutoff_fully_verified") else None
        tz = event.get("timezone") if clock else None
        append("milestone-" + str(event.get("id")), event.get("kind", "Deadline") + ": " + title,
               event["date"], clock, tz,
               "Source: " + str(event.get("source_url") or "unverified") +
               "; exact cutoff: " + ("verified" if clock else "not independently verified"))
    for ref in references:
        if ref.get("deadline"):
            append("reference-" + ref["id"], "Referee deadline: " + catalog.get(ref["application_id"], ref["application_id"]),
                   ref["deadline"], note="Referee request status: " + ref.get("status", "unknown"))
    for r in records:
        if r.get("followup"):
            append("followup-" + r["id"], "Faculty / application follow-up: " + r["name"],
                   r["followup"], note="Recorded owner follow-up; do not infer a completed contact")
    return "BEGIN:VCALENDAR\r\nVERSION:2.0\r\nCALSCALE:GREGORIAN\r\nPRODID:-//PhD Atlas//Private Applicant Operations//EN\r\n" + ("\r\n".join(entries) + "\r\n" if entries else "") + "END:VCALENDAR\r\n"
