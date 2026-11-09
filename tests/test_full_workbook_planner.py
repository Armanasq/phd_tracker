from __future__ import annotations

import json
from datetime import date, datetime

from openpyxl import Workbook, load_workbook

from scripts.full_workbook_planner import plan, run


def book(tmp_path):
    wb=Workbook()
    main=wb.active
    main.title="Action list"
    for _ in range(3):
        main.append([None]*21)
    def add(sid,name,due,verdict,source):
        row=[None]*21
        row[1]=datetime.fromisoformat(due) if due else "Rolling"
        row[4]=verdict
        row[6]=name
        row[10]="Prepare application"
        row[19]=source
        row[20]=sid
        main.append(row)
    add("A","Vision PhD","2026-11-06","Go - urgent","https://university.edu/vision")
    add("B","Domestic restricted award","2026-11-06","Not eligible","https://university.edu/restricted")
    add("C","Space PhD","2026-11-15","Go","https://university.edu/space")
    add("D","Rolling doctoral lead",None,"Check first","https://university.edu/rolling")
    timeline=wb.create_sheet("Step timeline")
    for _ in range(3):
        timeline.append([None]*7)
    timeline.append([datetime(2026,11,6),None,"Vision PhD","Go","Submit final form",datetime(2026,11,6),"A"])
    timeline.append([datetime(2026,11,4),None,"Vision PhD","Go","Prepare documents",datetime(2026,11,6),"A"])
    timeline.append([datetime(2026,11,6),None,"Domestic restricted award","Not eligible","Do not submit",datetime(2026,11,6),"B"])
    timeline.append([datetime(2026,11,6),None,"Space PhD","Go","Contact referee",datetime(2026,11,15),"C"])
    cross=wb.create_sheet("What I need to do")
    for _ in range(3):
        cross.append([None]*5)
    cross.append([datetime(2026,11,6),None,"Write standard research plan","Multiple programmes","To do"])
    cross.append([datetime(2026,11,5),None,"Scan transcripts","Multiple programmes","To do"])
    cross.append([datetime(2026,11,6),None,"Already completed","Multiple programmes","Done"])
    drop=wb.create_sheet("Dropped")
    drop.append(["Route","Status found","Reason","Source id"])
    drop.append(["Domestic restricted award","Not eligible","Domestic funding","B"])
    no=wb.create_sheet("Not added")
    no.append(["Route","Why not added"])
    no.append(["Old PhD","Expired"])
    wb.create_sheet("Read me")
    file=tmp_path/"tracker.xlsx"
    wb.save(file)
    return wb,file


def test_due_today_is_distinct_from_linked_final_deadlines(tmp_path):
    wb,_=book(tmp_path)
    result=plan(wb,date(2026,11,6))
    counts=result["today"]["counts"]
    assert counts["deadline_actions"]==1
    assert counts["excluded_deadlines"]==1
    assert counts["timeline_tasks"]==2
    assert counts["shared_tasks"]==1
    assert counts["linked_past_steps_not_recounted"]==1
    assert any(t["source_id"]=="A" for t in result["today"]["scheduled_timeline_tasks"])
    assert not any(t["source_id"]=="B" for t in result["today"]["scheduled_timeline_tasks"])
    assert result["inventory"]["dropped_routes"]==1
    assert result["inventory"]["not_added_routes"]==1


def test_overdue_unconfirmed_is_not_equivalent_to_incomplete(tmp_path):
    wb,_=book(tmp_path)
    result=plan(wb,date(2026,11,6))
    backlog=result["overdue_or_unconfirmed"]
    assert backlog["total"]==2
    assert backlog["cross_route"]==1
    assert backlog["timeline"]==1
    assert "completion_unconfirmed" in result["classification"]["overdue"] or "unconfirmed" in result["classification"]["overdue"]


def test_planner_rerun_preserves_original_sheets_and_sources(tmp_path):
    wb,file=book(tmp_path)
    cfg=tmp_path/"execution_plan.json"
    before=load_workbook(file)
    origin=[(r[0].value,r[1].value,r[2].value,r[3].value,r[4].value,r[5].value,r[6].value)
            for r in before["Step timeline"].iter_rows(min_row=4,max_col=7)]
    a=run(file,cfg,date(2026,11,6))
    b=run(file,cfg,date(2026,11,6))
    after=load_workbook(file)
    assert a==b
    assert "Execution board" in after and "Task ledger" in after
    assert [(r[0].value,r[1].value,r[2].value,r[3].value,r[4].value,r[5].value,r[6].value)
            for r in after["Step timeline"].iter_rows(min_row=4,max_col=7)]==origin
    assert after["Action list"].max_row==7
    assert after["Task ledger"].max_row>=10
    assert json.loads(cfg.read_text())["today"]["counts"]["deadline_actions"]==1


def test_owner_completion_overlay_is_persistent_and_source_preserving(tmp_path):
    wb,file=book(tmp_path)
    output=tmp_path/"data"/"execution_plan.json"
    output.parent.mkdir()
    first=run(file,output,date(2026,11,6))
    initial=json.loads(output.read_text())
    task=next(t for t in initial["today"]["scheduled_timeline_tasks"]
              if t["source_id"]=="C")
    identity=task["task_id"]
    assert identity.startswith("tsk-")
    (output.parent/"task_completion.json").write_text(json.dumps({
        "schema_version":1,"done":{identity:{"at":"2026-11-06T08:00:00+00:00","comment_id":"77"}}
    }))
    before=load_workbook(file)["Step timeline"]["E7"].value
    result=run(file,output,date(2026,11,6))
    refreshed=json.loads(output.read_text())
    assert result["today"]["timeline_tasks"]==first["today"]["timeline_tasks"]-1
    assert any(t["task_id"]==identity and t["state"]=="confirmed_done"
               for t in refreshed["all_tasks"])
    assert load_workbook(file)["Step timeline"]["E7"].value==before

def test_priority_review_does_not_create_final_deadline_or_duplicate_generated_step(tmp_path):
    wb, _ = book(tmp_path)
    ws = wb["Action list"]
    ws["C6"] = "Priority review by 15 Nov 2026; final application date is later."
    timeline = wb["Step timeline"]
    timeline.append([
        datetime(2026, 11, 15), None, "Space PhD", "Go",
        "Submit for priority review [External deadline: priority review]",
        datetime(2026, 11, 15), "C",
    ])
    result = plan(wb, date(2026, 11, 15))
    assert not any(t["source_id"] == "C" for t in result["today"]["eligible_application_deadlines"])
    priority = next(t for t in result["today"]["priority_review_dates"] if t["source_id"] == "C")
    assert priority["type"] == "application_priority"
    assert priority["state"] == "priority_review_date"
    assert priority["final_deadline"] is None
    assert result["today"]["counts"]["priority_reviews"] == 1
    assert not any(t["source_id"] == "C" and t["due"] == "2026-11-15"
                   for t in result["today"]["scheduled_timeline_tasks"])
    linked = next(t for t in result["all_tasks"]
                  if t["source_id"] == "C" and t["type"] == "timeline_step"
                  and t["due"] == "2026-11-15")
    assert linked["state"] == "linked_priority_note" and linked["blocked"]
