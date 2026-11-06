from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from datetime import date, datetime
from openpyxl import Workbook
import scripts.render_readme as dashboard


def test_readme_renderer_is_source_backed_and_valid_xml(tmp_path, monkeypatch):
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Action list"
    for _ in range(3):
        sheet.append([None] * 21)
    row = [None] * 21
    row[1] = datetime(2026, 11, 8)
    row[4] = "Go"
    row[6] = "Research lab & robot SLAM"
    row[19] = "https://example.edu/jobs/123"
    row[20] = "test-research-1"
    sheet.append(row)
    wb.save(tmp_path / "PhD_Action_List.xlsx")
    data = tmp_path / "data"
    data.mkdir()
    (data / "discovery_report.json").write_text(json.dumps({
        "new_count": 1,
        "source_yield": {
            "institutional": {"observed": 3, "new_unique": 1, "health": "ok"},
            "brave": {"observed": 0, "new_unique": 0, "health": "disabled"}
        }
    }))
    (data / "discovered_candidates.json").write_text(json.dumps({"records": [{"id": "test"}]}))
    (data / "latest_run.json").write_text(json.dumps({
        "source_statuses": [{"id": "portal", "status": "contradiction_closed_portal"}]
    }))
    monkeypatch.setattr(dashboard, "ROOT", tmp_path)
    monkeypatch.setattr(dashboard, "ASSETS", tmp_path / "assets" / "readme")
    result = dashboard.render(date(2026, 11, 6))
    assert result["applications"] == 1
    assert result["due_14d"] == 1
    assert result["contradictions"] == 1
    for name in ("hero.svg", "deadlines.svg", "providers.svg"):
        tree = ET.parse(tmp_path / "assets" / "readme" / name)
        assert tree.getroot().tag.endswith("svg")
    readme = (tmp_path / "README.md").read_text()
    assert "Research lab & robot SLAM" in readme
    assert "2026-11-08" in readme
    assert chr(96) * 3 + "mermaid" in readme
    assert "<details>" in readme
    assert "<script" not in readme


def test_readme_rerender_is_idempotent(tmp_path, monkeypatch):
    wb = Workbook()
    sheet = wb.active
    sheet.title = "Action list"
    for _ in range(3):
        sheet.append([None] * 21)
    wb.save(tmp_path / "PhD_Action_List.xlsx")
    monkeypatch.setattr(dashboard, "ROOT", tmp_path)
    monkeypatch.setattr(dashboard, "ASSETS", tmp_path / "assets" / "readme")
    dashboard.render(date(2026, 11, 6))
    before = [(p.name, p.read_bytes()) for p in (tmp_path / "assets" / "readme").glob("*")]
    markdown = (tmp_path / "README.md").read_bytes()
    dashboard.render(date(2026, 11, 6))
    after = [(p.name, p.read_bytes()) for p in (tmp_path / "assets" / "readme").glob("*")]
    assert before == after
    assert markdown == (tmp_path / "README.md").read_bytes()
