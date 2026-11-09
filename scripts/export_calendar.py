from __future__ import annotations

import argparse
import json
import re
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

ROOT=Path(__file__).resolve().parents[1]
PLAN=ROOT/"data"/"execution_plan.json"
OUT=ROOT/"calendar"/"phd_deadlines.ics"
MAX_DAYS=120


def escaped(value):
    val=str(value or "")
    val=val.replace("\\","\\\\").replace("\r\n","\n").replace("\r","\n")
    return val.replace("\n","\\n").replace(";","\\;").replace(",","\\,")


def folded(line):
    fragments=[]
    current=""
    length=0
    for ch in line:
        n=len(ch.encode("utf-8"))
        if length+n>73 and current:
            fragments.append(current)
            current=" "
            length=1
        current+=ch
        length+=n
    if current:
        fragments.append(current)
    return "\r\n".join(fragments)


def make_event(task,today):
    due=task.get("due")
    if not due:
        return []
    event_day=date.fromisoformat(due)
    delta=(event_day-today).days
    if delta<0 or delta>MAX_DAYS or task.get("blocked"):
        return []
    uid=task["task_id"]+"@phd-tracker.local"
    subject=task.get("name") or task.get("source_id") or ""
    task_type=task.get("type")
    if task_type=="application_deadline":
        label="APPLICATION DEADLINE"
        action=task.get("action") or "Check original application"
    elif task_type=="application_priority":
        label="PRIORITY REVIEW DATE (NOT FINAL)"
        action=task.get("action") or "Submit for priority consideration"
    elif task_type=="application_unverified":
        label="UNVERIFIED APPLICATION DATE"
        action=task.get("action") or "Verify institutional deadline"
    elif task_type=="timeline_step":
        label="SCHEDULED APPLICATION STEP"
        action=task.get("action") or "Verify scheduled step"
    elif task_type=="cross_route_task":
        label="SHARED PREPARATION TASK"
        action=task.get("action") or ""
    else:
        return []
    summary=f"{label}: {subject}"
    description="\n".join([
        "Action: "+action,
        "Status: "+str(task.get("state") or "unconfirmed"),
        "Original source: "+str(task.get("sheet") or "")+" row "+str(task.get("row") or ""),
        "Official URL: "+str(task.get("source") or "not linked"),
        "Final programme deadline: "+str(task.get("final_deadline") or "unconfirmed / not applicable"),
        "Original note: "+str(task.get("notes") or ""),
        "All-day date. DO NOT infer a closing time from this event.",
        "Confirm actual portal availability and individual eligibility.",
    ])
    lines=[
        "BEGIN:VEVENT",
        "UID:"+escaped(uid),
        "DTSTAMP:"+today.strftime("%Y%m%d")+"T000000Z",
        "DTSTART;VALUE=DATE:"+event_day.strftime("%Y%m%d"),
        "DTEND;VALUE=DATE:"+(event_day+timedelta(days=1)).strftime("%Y%m%d"),
        "SUMMARY:"+escaped(summary),
        "DESCRIPTION:"+escaped(description),
        "CATEGORIES:"+escaped(label),
        "STATUS:TENTATIVE",
    ]
    uri=task.get("source") or ""
    if uri.startswith("https://") and urlsplit(uri).hostname:
        lines.append("URL:"+escaped(uri))
    durations=("-P7D","-P1D") if task_type in ("application_deadline", "application_priority") else ("-P1D",)
    for duration in durations:
        lines+=["BEGIN:VALARM","TRIGGER:"+duration,"ACTION:DISPLAY",
                "DESCRIPTION:"+escaped(label+" — check original source"),"END:VALARM"]
    lines.append("END:VEVENT")
    return lines


def export(plan,output):
    today=date.fromisoformat(plan["as_of"])
    tasks=plan.get("all_tasks",[])
    entries=[]
    seen=set()
    for task in sorted(tasks,key=lambda t:(t.get("due") or "9999",t.get("task_id") or "")):
        key=task.get("task_id")
        if not key or key in seen:
            continue
        lines=make_event(task,today)
        if lines:
            seen.add(key)
            entries.extend(lines)
    document=[
        "BEGIN:VCALENDAR","VERSION:2.0","PRODID:-//EvidenceGraph//PhD Application Calendar//EN",
        "CALSCALE:GREGORIAN","METHOD:PUBLISH",
        "X-WR-CALNAME:PhD Intelligence - Source-backed dates",
        "X-WR-CALDESC:All-day reminders. Closing times and completion states require verification.",
    ]+entries+["END:VCALENDAR"]
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_bytes(("\r\n".join(folded(line) for line in document)+"\r\n").encode("utf-8"))
    return {"as_of":today.isoformat(),"events":len(seen),"path":str(output),
            "warning":"Private GitHub download is a calendar snapshot; not a automatically updating subscription."}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--plan",default=str(PLAN))
    p.add_argument("--output",default=str(OUT))
    args=p.parse_args()
    data=json.loads(Path(args.plan).read_text(encoding="utf-8"))
    print(json.dumps(export(data,Path(args.output)),ensure_ascii=False))


if __name__=="__main__":
    main()
