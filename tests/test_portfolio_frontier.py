from __future__ import annotations

import json
from datetime import date, datetime

import pytest
from openpyxl import Workbook, load_workbook

from scripts.portfolio_frontier import evaluate, extract_assets, run


def make_workbook():
    wb = Workbook()
    ws = wb.active
    ws.title = "Action list"
    for _ in range(3):
        ws.append([None] * 21)
    row = [None] * 21
    row[1] = datetime(2026, 11, 13)
    row[4] = "Go"
    row[6] = "Robotic SLAM doctoral opening"
    row[10] = "Submit CV and research statement; organize transcripts"
    row[19] = "https://institute.edu/job/123"
    row[20] = "doctoral-123"
    ws.append(row)
    return wb


def make_assets(status="unknown"):
    return {"schema_version": 1, "resources": {
        "academic_cv": {"label": "CV", "status": status},
        "research_statement": {"label": "Statement", "status": "ready"},
        "transcripts": {"label": "Transcript", "status": "ready"},
    }}


def test_asset_mentions_are_not_assumed_missing():
    assert set(extract_assets("Submit CV and research statement")) == {
        "academic_cv", "research_statement"
    }
    report = evaluate(make_workbook(), make_assets(), date(2026, 11, 6), [], {})
    item = report["applications"][0]
    assert item["readiness"] == "requires_readiness_confirmation"
    assert item["unknown_resource_states"] == ["academic_cv"]
    assert "research_statement" not in item["unconfirmed_resources"]
    assert any(r["resource_id"] == "academic_cv" for r in report["resource_frontier"])


def test_source_conflict_blocks_unqualified_ready_claim():
    latest = {"source_statuses": [{"id": "portal-check-1", "application_id": "doctoral-123", "status": "contradiction_closed_portal"}]}
    report = evaluate(make_workbook(), make_assets("ready"), date(2026, 11, 6), [], latest)
    item = report["applications"][0]
    assert item["readiness"] == "source_conflict"
    assert item["evidence_proof_obligations"]


def test_reject_invalid_resource_status():
    with pytest.raises(ValueError, match="status"):
        evaluate(make_workbook(), make_assets("invented"), date(2026, 11, 6), [], {})


def test_portfolio_sheet_rerun_is_idempotent(tmp_path):
    wb = make_workbook()
    file = tmp_path / "tracker.xlsx"
    wb.save(file)
    data = tmp_path / "data"
    data.mkdir()
    cfg = data / "application_assets.json"
    cfg.write_text(json.dumps(make_assets()))
    out = data / "portfolio_frontier.json"
    first = run(file, cfg, out, date(2026, 11, 6))
    second = run(file, cfg, out, date(2026, 11, 6))
    assert first["active_opportunities"] == 1
    assert first == second
    updated = load_workbook(file, read_only=True)
    assert updated["Decision frontier"].max_row == 2
    assert updated["Action list"].max_row == 4
