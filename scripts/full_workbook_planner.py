from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections import Counter
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "PhD_Action_List.xlsx"
REPORT = ROOT / "data" / "execution_plan.json"
CLOSED = {"submitted", "skipped", "rejected", "accepted", "withdrawn", "not eligible"}
DONE = {"done", "completed", "complete", "skipped", "cancelled", "canceled"}
REVIEW = {"check first", "go with risk", "long shot"}
COLUMNS = [
    "Category", "Due date", "Days", "State", "Application / context",
    "Action and requirements", "Final application deadline", "Verdict",
    "Source ID", "Original worksheet", "Original row", "Primary URL",
    "Evidence / caveats", "Stable task ID",
]


def local_today() -> date:
    return datetime.now(ZoneInfo("Europe/Berlin")).date()


def as_date(value) -> date | None:
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        value = value.strip()
        if re.fullmatch(r"20\d\d-\d\d-\d\d", value):
            try:
                return date.fromisoformat(value)
            except ValueError:
                return None
    return None


def text(value, limit=900):
    if value is None:
        return ""
    return str(value).strip()[:limit]


def clean_state(value):
    return text(value, 90).casefold()


def link_for_parent(app, fallback=""):
    return text(app.get("source") or app.get("apply_url") or fallback, 500)


def read_inputs(wb, today: date):
    if not {"Action list", "Step timeline", "What I need to do", "Dropped", "Not added"} <= set(wb.sheetnames):
        raise ValueError("Original workbook sheets missing; refusing partial planning")
    applications = {}
    app_rows = []
    for row in wb["Action list"].iter_rows(min_row=4, max_col=21):
        v = [c.value for c in row]
        if not v[6] or not v[20]:
            continue
        sid = text(v[20], 100)
        if sid in applications:
            raise ValueError("Duplicate application source ID: " + sid)
        a = {
            "source_id": sid, "name": text(v[6], 320),
            "deadline": as_date(v[1]), "deadline_note": text(v[2], 550),
            "verdict": text(v[4], 95), "fit": text(v[5], 460),
            "source": text(v[19], 500), "apply_url": text(v[8], 500),
            "next_step": text(v[10], 900), "documents": text(v[12], 550),
            "blockers": text(v[16], 570), "group": text(v[18], 90),
            "row":row[0].row,
        }
        applications[sid] = a
        app_rows.append(a)
    all_tasks = []
    for a in app_rows:
        d = a["deadline"]
        days = (d - today).days if d else None
        excluded = clean_state(a["verdict"]) in CLOSED
        all_tasks.append({
            "type":"application_deadline" if d else "application_unposted",
            "sheet":"Action list","row":a["row"],
            "source_id":a["source_id"],"name":a["name"],
            "action":a["next_step"] or "Verify the official portal and deadline",
            "due":d.isoformat() if d else None,"days":days,
            "final_deadline":d.isoformat() if d else None,
            "verdict":a["verdict"],"source":a["source"],"notes":a["deadline_note"],
            "state":"excluded" if excluded else "deadline_unconfirmed" if d else "date_not_posted",
            "blocked":excluded,"group":a["group"],
        })
    for row in wb["Step timeline"].iter_rows(min_row=4, max_col=7):
        v = [c.value for c in row]
        if not v[2] or not v[4]:
            continue
        sid = text(v[6], 100)
        parent=applications.get(sid, {})
        due = as_date(v[0])
        final = as_date(v[5])
        status = clean_state(parent.get("verdict") or v[3])
        excluded = status in CLOSED
        days = (due - today).days if due else None
        all_tasks.append({
            "type":"timeline_step", "sheet":"Step timeline", "row":row[0].row,
            "source_id":sid, "name":text(v[2], 320), "action":text(v[4], 1000),
            "due":due.isoformat() if due else None,"days":days,
            "final_deadline":final.isoformat() if final else None,
            "verdict":text(parent.get("verdict") or v[3], 95),
            "source":link_for_parent(parent), "notes":text(v[5], 110),
            "state":"excluded_parent" if excluded else "completion_unconfirmed",
            "blocked":excluded,"group":text(parent.get("group"), 90),
        })
    for row in wb["What I need to do"].iter_rows(min_row=4, max_col=5):
        v = [c.value for c in row]
        if not v[2]:
            continue
        due=as_date(v[0])
        status=text(v[4], 90)
        days=(due - today).days if due else None
        all_tasks.append({
            "type":"cross_route_task", "sheet":"What I need to do", "row":row[0].row,
            "source_id":f"CROSS-{row[0].row:04d}", "name":text(v[3], 450),
            "action":text(v[2], 1000), "due":due.isoformat() if due else None,
            "days":days,"final_deadline":None, "verdict":status,"source":"",
            "notes":text(v[3], 550),
            "state":"completed" if clean_state(v[4]) in DONE else
                    "explicit_to_do" if clean_state(v[4]) in ("to do", "todo") else
                    "status_unconfirmed",
            "blocked":clean_state(v[4]) in DONE, "group":"cross-route",
        })
    dropped = []
    for row in wb["Dropped"].iter_rows(min_row=2, max_col=4, values_only=True):
        if not row[0]:
            continue
        dropped.append({"route":text(row[0], 260), "status":text(row[1],80),
                        "reason":text(row[2],400),"source_id":text(row[3],100)})
    not_added = []
    for row in wb["Not added"].iter_rows(min_row=2, max_col=2, values_only=True):
        if row[0]:
            not_added.append({"route":text(row[0],260),"reason":text(row[1],460)})
    return applications, all_tasks, dropped, not_added


def plan(wb, today: date, completion_state=None):
    apps,tasks,dropped,not_added=read_inputs(wb,today)
    done = (completion_state or {}).get("done", {})
    for task in tasks:
        normalized = " ".join(task["action"].casefold().split())
        material = "|".join((task["type"],task["source_id"],task["due"] or "",normalized))
        task["task_id"] = "tsk-" + hashlib.sha256(material.encode("utf-8")).hexdigest()[:16]
        if task["type"] in ("timeline_step","cross_route_task") and task["task_id"] in done:
            task["state"] = "confirmed_done"
            task["blocked"] = True
            task["confirmed_at"] = done[task["task_id"]].get("at", "")
    included=[t for t in tasks if not t["blocked"]]
    today_apps=[t for t in included if t["type"]=="application_deadline" and t["days"]==0]
    excluded_deadlines=[t for t in tasks if t["type"]=="application_deadline" and t["days"]==0 and t["blocked"]]
    step_today=[t for t in included if t["type"]=="timeline_step" and t["days"]==0]
    shared_today=[t for t in included if t["type"]=="cross_route_task" and t["days"]==0]
    future_week=[t for t in included if t["type"]=="application_deadline" and t["days"] is not None and 0<t["days"]<=7]
    past_unconfirmed=[t for t in included if t["type"]!="application_deadline" and t["days"] is not None and t["days"]<0
                      and (not t["final_deadline"] or t["final_deadline"]>=today.isoformat())]
    parent_final_today=[t for t in included if t["type"]=="timeline_step"
                        and t["days"] is not None and t["days"]<0 and t["final_deadline"]==today.isoformat()]
    negative_ids={x["source_id"] for x in dropped if x["source_id"]}
    potentially_excluded=[x for x in apps.values() if x["source_id"] in negative_ids]
    by_type=Counter(t["type"] for t in tasks)
    by_state=Counter(t["state"] for t in tasks)
    for t in tasks:
        t["task_key"]=f'{t["sheet"]}!{t["row"]}'
    for seq in (today_apps,excluded_deadlines,step_today,shared_today,future_week,past_unconfirmed,parent_final_today):
        seq.sort(key=lambda x: (x["days"] if x["days"] is not None else 999999,
                                0 if x["verdict"]=="Go - urgent" else 1, x["source_id"],x["row"]))
    return {
        "schema_version":2, "as_of":today.isoformat(), "timezone":"Europe/Berlin",
        "classification": {
            "submission_deadline": "Application list B is the final deadline; exclude rows marked Not eligible / Submitted / Skipped",
            "scheduled_task": "Step timeline A is a task date; F is the final application deadline and must not be counted as another scheduled task",
            "shared_task": "What I need to do A is an explicit cross-application task date; E is its user-maintained status",
            "overdue": "Past scheduled dates have no completion state in Step timeline: they are unconfirmed, not asserted unfinished",
        },
        "today": {
            "eligible_application_deadlines":today_apps,
            "excluded_application_deadlines":excluded_deadlines,
            "scheduled_timeline_tasks":step_today,
            "cross_route_tasks":shared_today,
            "linked_past_steps_with_final_deadline_today":parent_final_today,
            "counts": {
                "deadline_actions":len(today_apps),
                "excluded_deadlines":len(excluded_deadlines),
                "timeline_tasks":len(step_today),
                "shared_tasks":len(shared_today),
                "total_distinct_scheduled_actions":len(today_apps)+len(step_today)+len(shared_today),
                "source_row_events_scheduled_today":len(today_apps)+len(step_today)+len(shared_today),
                "linked_past_steps_not_recounted":len(parent_final_today),
            }
        },
        "upcoming_7_day_deadlines":future_week,
        "overdue_or_unconfirmed": {
            "total":len(past_unconfirmed),
            "cross_route":sum(t["type"]=="cross_route_task" for t in past_unconfirmed),
            "timeline":sum(t["type"]=="timeline_step" for t in past_unconfirmed),
            "highest_priority_sample":past_unconfirmed[:35],
        },
        "inventory": {
            "application_rows":len(apps),
            "application_dates_unposted_or_rolling":by_type["application_unposted"],
            "timeline_steps":by_type["timeline_step"],
            "cross_route_tasks":by_type["cross_route_task"],
            "dropped_routes":len(dropped),
            "not_added_routes":len(not_added),
            "task_states":dict(by_state),
            "owner_completed_tasks":sum(t["state"]=="confirmed_done" for t in tasks),
            "tracked_source_ids_in_dropped":len(potentially_excluded),
            "research_queue_rows":max(0, wb["Research queue"].max_row-1) if "Research queue" in wb else 0,
            "mail_signal_rows":max(0, wb["Mail signals"].max_row-1) if "Mail signals" in wb else 0,
            "evidence_ledger_rows":max(0, wb["Evidence ledger"].max_row-1) if "Evidence ledger" in wb else 0,
            "research_radar_rows":max(0, wb["Research radar"].max_row-1) if "Research radar" in wb else 0,
        },
        "excluded_today":excluded_deadlines,
        "source_tabs":list(wb.sheetnames),
        "all_tasks":tasks,
    }


def regenerate_sheet(wb, result):
    sheet="Execution board"
    ws=wb[sheet] if sheet in wb else wb.create_sheet(sheet)
    if ws.max_row:
        ws.delete_rows(1, ws.max_row)
    ws.append(COLUMNS)
    palette={"application_deadline":"DCEEEA","timeline_step":"EAF1FB","cross_route_task":"FFF0D9"}
    sections=[
        ("Today — application submissions",result["today"]["eligible_application_deadlines"]),
        ("Today — shared cross-route tasks",result["today"]["cross_route_tasks"]),
        ("Today — scheduled preparation",result["today"]["scheduled_timeline_tasks"]),
        ("Next seven days — application deadlines",result["upcoming_7_day_deadlines"]),
        ("Past dates — completion unconfirmed",result["overdue_or_unconfirmed"]["highest_priority_sample"]),
    ]
    row_number=1
    for heading,rows in sections:
        ws.append([heading])
        header=ws.cell(ws.max_row,1)
        header.fill=PatternFill("solid",fgColor="254D66")
        header.font=Font(name="Aptos",bold=True,color="FFFFFF",size=11)
        ws.row_dimensions[ws.max_row].height=23
        for t in rows:
            d=as_date(t["due"]) if t["due"] else None
            end=as_date(t["final_deadline"]) if t["final_deadline"] else None
            ws.append([t["type"],d,t["days"],t["state"],t["name"],
                t["action"],end,t["verdict"],t["source_id"],t["sheet"],t["row"],
                t["source"],t["notes"],t["task_id"]])
            r=ws.max_row
            for col in range(1,len(COLUMNS)+1):
                c=ws.cell(r,col)
                c.font=Font(name="Aptos",size=10,color="135D53" if col==12 else "21344C")
                c.alignment=Alignment(vertical="top",wrap_text=True)
                if col in (1,4):
                    c.fill=PatternFill("solid",fgColor=palette.get(t["type"],"FFFFFF"))
            for col in (2,7):
                ws.cell(r,col).number_format="yyyy-mm-dd"
            ws.row_dimensions[r].height=43
    for j,title in enumerate(COLUMNS,1):
        cell=ws.cell(1,j)
        cell.fill=PatternFill("solid",fgColor="152A45")
        cell.font=Font(bold=True,color="FFFFFF",name="Aptos",size=10)
        cell.alignment=Alignment(wrap_text=True)
    widths=[19,16,10,26,64,90,18,19,19,24,12,62,70,28]
    for j,w in enumerate(widths,1):
        ws.column_dimensions[get_column_letter(j)].width=w
    ws.freeze_panes="F2"
    ws.sheet_view.showGridLines=False
    ws.sheet_properties.pageSetUpPr.fitToPage=True

    ledger=wb["Task ledger"] if "Task ledger" in wb else wb.create_sheet("Task ledger")
    ledger.delete_rows(1,ledger.max_row)
    ledger.append(COLUMNS)
    sorted_tasks=sorted(result["all_tasks"],key=lambda t:(
        t["days"] is None,t["days"] if t["days"] is not None else 999999,t["type"],t["source_id"],t["row"]))
    for t in sorted_tasks:
        ledger.append([t["type"],as_date(t["due"]) if t["due"] else None,t["days"],
                      t["state"],t["name"],t["action"],
                      as_date(t["final_deadline"]) if t["final_deadline"] else None,
                      t["verdict"],t["source_id"],t["sheet"],t["row"],t["source"],t["notes"],t["task_id"]])
        for j in (2,7):
            ledger.cell(ledger.max_row,j).number_format="yyyy-mm-dd"
    ledger.freeze_panes="F2"
    ledger.auto_filter.ref=f"A1:N{ledger.max_row}"
    ledger.sheet_view.showGridLines=False
    for j,title in enumerate(COLUMNS,1):
        c=ledger.cell(1,j)
        c.fill=PatternFill("solid",fgColor="152A45")
        c.font=Font(name="Aptos",size=10,bold=True,color="FFFFFF")
        c.alignment=Alignment(wrap_text=True)
        ledger.column_dimensions[get_column_letter(j)].width=widths[j-1]
    return {"execution_rows":ws.max_row,"ledger_rows":ledger.max_row}


def run(workbook=BOOK,output=REPORT,today=None):
    today=today or local_today()
    wb=load_workbook(workbook)
    status_file=output.parent/"task_completion.json"
    completion_state=json.loads(status_file.read_text(encoding="utf-8")) if status_file.exists() else {}
    summary=plan(wb,today,completion_state)
    summary.update(regenerate_sheet(wb,summary))
    wb.save(workbook)
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(summary,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return {"as_of":summary["as_of"],"today":summary["today"]["counts"],
            "inventory":summary["inventory"],"execution_rows":summary["execution_rows"],
            "ledger_rows":summary["ledger_rows"]}


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--as-of",default=local_today().isoformat())
    args=p.parse_args()
    print(json.dumps(run(today=date.fromisoformat(args.as_of)),ensure_ascii=False))


if __name__=="__main__":
    main()
