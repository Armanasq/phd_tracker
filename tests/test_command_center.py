from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.render_command_center import render, operations_svg, lanes_svg, dashboard_md, todays_md


def record(kind, sid, when, action, verdict="Go"):
    return {"type":kind,"source_id":sid,"name":"Research programme & AI",
            "action":action,"due":when,"days":0,
            "verdict":verdict,"source":"https://university.edu/position",
            "sheet":"Step timeline","row":11,"state":"completion_unconfirmed"}


def plan():
    app=record("application_deadline","A","2026-11-06","Submit application")
    step=record("timeline_step","A","2026-11-06","Request academic reference")
    shared=record("cross_route_task","CROSS-0014","2026-11-06","Write master research plan","To do")
    excluded=record("application_deadline","B","2026-11-06","Do not apply","Not eligible")
    return {
      "as_of":"2026-11-06",
      "today":{
        "counts":{"deadline_actions":1,"excluded_deadlines":1,"timeline_tasks":1,
                  "shared_tasks":1,"total_distinct_scheduled_actions":3},
        "eligible_application_deadlines":[app],
        "excluded_application_deadlines":[excluded],
        "scheduled_timeline_tasks":[step],
        "cross_route_tasks":[shared],
        "linked_past_steps_with_final_deadline_today":[],
      },
      "upcoming_7_day_deadlines":[],
      "overdue_or_unconfirmed":{"total":6,"cross_route":2,"timeline":4,"highest_priority_sample":[]},
      "inventory":{"application_rows":183,"timeline_steps":559,"cross_route_tasks":26,
                   "dropped_routes":6,"not_added_routes":200,"research_queue_rows":24},
      "source_tabs":["Read me","Action list","Step timeline","What I need to do",
                     "Dropped","Not added","Research queue","Source watch","Task ledger"],
    }


def metrics():
    return {"applications":183,"radar":34,"contradictions":2,
            "providers":{"brave":{"observed":0,"new_unique":0,"health":"disabled"},
                         "inria":{"observed":3,"new_unique":0,"health":"ok"}}}


def test_source_date_vs_preparation_date_stays_distinct():
    doc=dashboard_md(plan(),metrics())
    assert "Submission deadlines today" in doc
    assert "Programme-specific steps due today" in doc
    assert "3 deadline" not in doc
    assert "Research programme &amp;" not in doc
    assert "Research programme & AI" in doc
    assert "200 researched-but-not-added routes" in doc or "200 researched-but-not-added" in doc or "200 researched but unadded" in doc
    assert "2026-11-06" in doc
    assert "mermaid" in doc
    assert "<details" in doc
    assert "<script" not in doc


def test_command_center_emits_valid_svg_and_full_agenda(tmp_path):
    data=tmp_path/"data"
    data.mkdir()
    (data/"execution_plan.json").write_text(json.dumps(plan()))
    assets=tmp_path/"assets"/"readme"
    assets.mkdir(parents=True)
    (assets/"metrics.json").write_text(json.dumps(metrics()))
    out=render(tmp_path)
    assert out["task_counts"]["total_distinct_scheduled_actions"]==3
    readme=(tmp_path/"README.md").read_text()
    today=(tmp_path/"docs"/"TODAY.md").read_text()
    assert "Full Task ledger" in readme
    assert "Full machine-readable ledger" in today
    assert "Application submission deadlines today" in today
    assert "Explicitly excluded application deadlines today" in today
    for file in ("operations.svg","lanes.svg"):
        root=ET.parse(assets/file).getroot()
        assert root.tag.endswith("svg")
        assert "text" in (assets/file).read_text()


def test_renderer_is_idempotent(tmp_path):
    data=tmp_path/"data"
    data.mkdir()
    (data/"execution_plan.json").write_text(json.dumps(plan()))
    assets=tmp_path/"assets"/"readme"
    assets.mkdir(parents=True)
    (assets/"metrics.json").write_text(json.dumps(metrics()))
    render(tmp_path)
    a=[p.read_bytes() for p in [tmp_path/"README.md",tmp_path/"docs"/"TODAY.md",assets/"operations.svg"]]
    render(tmp_path)
    b=[p.read_bytes() for p in [tmp_path/"README.md",tmp_path/"docs"/"TODAY.md",assets/"operations.svg"]]
    assert a==b
