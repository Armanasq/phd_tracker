from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.experience_engine import (generate, make_view, orbit_svg, safe_url, operational_insights, lineage_jsonld, isometric_calendar_svg, dependency_svg, research_map_svg)


def write_fixture(root: Path, *, duplicate: bool = False, mismatch: bool = False) -> None:
    data = root / "data"
    data.mkdir()
    records = [{
        "source_id": "P1",
        "deadline": "2026-11-08",
        "opportunity": 'PhD <script>alert("x")</script>',
        "decision": "Go",
        "document_mentions": ["academic_cv", "not_configured"],
        "evidence_proof_obligations": ["Confirm funding"],
        "source_url": "https://university.example/apply",
    }]
    if duplicate:
        records.append(dict(records[0]))
    payloads = {
        "execution_plan.json": {"as_of": "2026-11-07", "timezone": "Europe/Berlin"},
        "portfolio_frontier.json": {
            "as_of": "2026-11-06" if mismatch else "2026-11-07",
            "source_conflict_count": 1, "applications": records,
            "resource_frontier": [{
                "resource_id": "academic_cv", "label": "Academic CV",
                "current_state": "unknown", "potential_applications": 1,
                "near_term_applications": 1,
            }],
        },
        "application_assets.json": {"resources": {"academic_cv": {"status": "unknown"}}},
        "discovery_report.json": {"source_yield": {"inria": {"health": "ok", "observed": 2, "new_unique": 1}}},
        "research_radar.json": {"papers": [{"title": "Navigation", "id": "arxiv:123"}]},
        "latest_run.json": {"source_statuses": [{"status": "review_source_changed"}]},
    }
    for filename, value in payloads.items():
        (data / filename).write_text(json.dumps(value), encoding="utf-8")


def test_view_preserves_unknown_and_provenance(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    view = make_view(tmp_path)
    assert view["as_of"] == "2026-11-07"
    assert view["metrics"]["next_seven_days"] == 1
    assert view["applications"][0]["unknown_documents"] == ["academic_cv"]
    assert view["applications"][0]["documents"] == ["academic_cv"]
    assert view["applications"][0]["source"] == "https://university.example/apply"
    assert view["applications"][0]["proof_obligations"] == ["Confirm funding"]
    assert view["metrics"]["research_papers"] == 1
    assert "&lt;script&gt;" in orbit_svg(view)
    assert "<script>alert" not in orbit_svg(view)


def test_mismatched_snapshots_are_rejected(tmp_path: Path) -> None:
    write_fixture(tmp_path, mismatch=True)
    with pytest.raises(ValueError, match="mixed-date"):
        make_view(tmp_path)


def test_duplicate_identity_is_rejected(tmp_path: Path) -> None:
    write_fixture(tmp_path, duplicate=True)
    with pytest.raises(ValueError, match="duplicate"):
        make_view(tmp_path)


def test_unsafe_urls_are_not_links() -> None:
    assert safe_url("javascript:alert(1)") == ""
    assert safe_url("http://example.com") == ""
    assert safe_url("https://example.com/job") == "https://example.com/job"


def test_generation_creates_offline_dashboard_and_assets(tmp_path: Path) -> None:
    pytest.importorskip("PIL")
    write_fixture(tmp_path)
    (tmp_path / "dashboard").mkdir()
    template = Path(__file__).resolve().parents[1] / "dashboard/template.html"
    (tmp_path / "dashboard/template.html").write_text(template.read_text(encoding="utf-8"),encoding="utf-8")
    for name in ("experience.css", "experience.js"):
        source = template.parent / name
        (tmp_path / "dashboard" / name).write_text(source.read_text(encoding="utf-8"), encoding="utf-8")
    result = generate(tmp_path)
    assert result["applications"] == 1
    generated = (tmp_path / "dashboard/index.html").read_text(encoding="utf-8")
    assert "__EVIDENCE_DATA_JSON__" not in generated
    assert r"\u003cscript" in generated
    assert "<script>alert" not in generated
    assert "Counterfactual readiness" in generated
    assert "buildGraph" in generated
    assert "renderPriority" in generated
    assert "command-query" in generated
    assert '<script src="experience.js"></script>' not in generated
    assert '<link rel="stylesheet" href="experience.css">' not in generated
    assert (tmp_path / "assets/readme/evidence_pipeline.gif").stat().st_size > 0
    assert (tmp_path / "assets/readme/deadline_orbits.svg").stat().st_size > 0
    assert (tmp_path / "assets/readme/isometric_calendar.svg").stat().st_size > 0
    assert (tmp_path / "assets/readme/asset_dependencies.svg").stat().st_size > 0
    assert (tmp_path / "data/experience_lineage.jsonld").stat().st_size > 0
    doc = (tmp_path / "docs/EXPERIENCE.md").read_text(encoding="utf-8")
    assert "THIS IS AN EXECUTABLE RESEARCH WORKSPACE" in doc
    assert "kinetic_cover.svg" in doc
    assert "experience-lab.yml" in doc
    assert 'src="../assets/readme/isometric_calendar.svg"' in doc
    assert '](../dashboard/README.md)' in doc
    assert '](TODAY.md)' in doc
    assert "assets/readme/hero.svg" not in doc


def test_collision_and_source_anomaly_linkage(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    view = make_view(tmp_path)
    clone = dict(view["applications"][0], id="P2", name="Second call")
    details = operational_insights(
        view["applications"] + [clone],
        [
            {"id": "MON-1", "application_id": "P1", "status": "contradiction_closed_portal", "source_url": "https://university.example/portal"},
            {"id": "MON-2", "application_id": "UNKNOWN", "status": "review_source_changed"},
        ],
    )
    assert details["deadline_collisions"][0]["count"] == 2
    assert details["source_anomalies"][0]["is_linked"] is True
    assert details["source_anomalies"][1]["is_linked"] is False
    assert details["verification_queue"][0]["days"] == 1


def test_jsonld_lineage_and_visuals(tmp_path: Path) -> None:
    write_fixture(tmp_path)
    view = make_view(tmp_path)
    graph = lineage_jsonld(view)
    assert graph["@context"]["prov"] == "http://www.w3.org/ns/prov#"
    application = next(item for item in graph["@graph"] if item["@id"].endswith(":P1"))
    assert application["schema:citation"]["@id"] == "https://university.example/apply"
    assert len(application["documentMention"]) == 1
    for svg in (isometric_calendar_svg(view), dependency_svg(view), research_map_svg(view)):
        assert svg.startswith("<svg")
        assert svg.rstrip().endswith("</svg>")
        assert "<script>alert" not in svg
