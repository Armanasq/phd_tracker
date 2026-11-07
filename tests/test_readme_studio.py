from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.readme_studio import (
    country_for,
    country_map,
    deadline_buckets,
    generate,
    mermaid_erd,
    mermaid_flowchart,
    mermaid_gantt,
    mermaid_quadrant,
    mermaid_sankey,
    mermaid_states,
    mermaid_xychart,
    stl_skyline,
)


def fixture() -> dict:
    return {
        "schema_version": 1,
        "as_of": "2026-11-07",
        "timezone": "Europe/Berlin",
        "metrics": {
            "tracked": 5, "future": 5, "next_seven_days": 2,
            "unknown_document_mentions": 6, "source_conflicts": 1,
            "research_papers": 7,
        },
        "providers": [
            {"name": "inria", "health": "ok", "observed": 12, "new_unique": 1},
            {"name": "brave", "health": "disabled", "observed": 0, "new_unique": 0},
        ],
        "applications": [
            {"id": "A", "name": "Karlsruhe Institute of Technology Robotics",
             "deadline": "2026-11-08", "days": 1, "source": "https://example.edu/a",
             "unknown_documents": ["cv", "statement"], "proof_obligations": []},
            {"id": "B", "name": "University of Copenhagen ML",
             "deadline": "2026-11-12", "days": 5, "source": "https://example.edu/b",
             "unknown_documents": ["cv"], "proof_obligations": []},
            {"id": "C", "name": "UCL London vision research",
             "deadline": "2026-11-20", "days": 13, "source": "https://example.edu/c",
             "unknown_documents": ["cv"], "proof_obligations": ["funding"]},
            {"id": "D", "name": "University of Amsterdam and ETH Zurich joint programme",
             "deadline": "2026-12-15", "days": 38, "source": "",
             "unknown_documents": [], "proof_obligations": []},
            {"id": "E", "name": "Unnamed institution without country information",
             "deadline": "2027-01-30", "days": 84, "source": "",
             "unknown_documents": [], "proof_obligations": []},
        ],
    }


def test_country_matching_disallows_ambiguous_assignments() -> None:
    assert country_for("University of Copenhagen ML") == "Denmark"
    assert country_for("ETH Zurich robotics") == "Switzerland"
    assert country_for("University of Amsterdam and ETH Zurich") is None
    assert country_for("A private unnamed research lab") is None


def test_native_interactive_geojson_is_derived_only_from_unambiguous_names() -> None:
    collection, matched = country_map(fixture())
    assert matched == 3
    assert collection["type"] == "FeatureCollection"
    assert len(collection["features"]) == 3
    assert sum(x["properties"]["count"] for x in collection["features"]) == 3
    assert all(x["geometry"]["type"] == "Point" for x in collection["features"])
    assert all(len(x["geometry"]["coordinates"]) == 2 for x in collection["features"])


def test_partition_funnel_and_gantt_use_actual_dates() -> None:
    view = fixture()
    assert [n for _, n in deadline_buckets(view)] == [2, 1, 0, 1, 1]
    sankey = mermaid_sankey(view)
    assert sankey.startswith("sankey-beta\n")
    assert "Recorded frontier,0-7 days,2" in sankey
    assert "Recorded frontier,61+ days,1" in sankey
    gantt = mermaid_gantt(view)
    assert "dateFormat YYYY-MM-DD" in gantt
    assert "2026-11-08" in gantt
    assert "2026-11-20" in gantt


def test_mermaid_schema_and_quadrant_diagrams() -> None:
    view = fixture()
    for content, prefix in [
        (mermaid_erd(), "erDiagram"),
        (mermaid_flowchart(view), "flowchart LR"),
        (mermaid_quadrant(view), "quadrantChart"),
        (mermaid_states(), "stateDiagram-v2"),
        (mermaid_xychart(view), "xychart-beta"),
    ]:
        assert content.startswith(prefix)
        assert "<script" not in content
    assert "R01:" in mermaid_quadrant(view)


def test_generated_readme_and_native_assets(tmp_path: Path) -> None:
    view = fixture()
    output = generate(tmp_path, view, {"as_of": "2026-11-07"})
    fence = chr(96) * 3
    assert output.count(fence+"mermaid") >= 5
    assert fence+"geojson" in output
    assert "sankey-beta" in output
    assert "quadrantChart" in output
    assert "Deadline Gantt" in output
    assert "Mermaid" in output
    assert "5</h2>" in output
    geo = json.loads((tmp_path / "data/readme_opportunities.geojson").read_text(encoding="utf-8"))
    assert geo["type"] == "FeatureCollection"
    stl = (tmp_path / "assets/readme/deadline_skyline.stl").read_text(encoding="utf-8")
    assert stl.startswith("solid deadline_horizon")
    assert stl.count("facet normal") == 60
    for filename in ("pipeline.mmd", "horizon_sankey.mmd", "deadlines.mmd", "priority_quadrant.mmd", "evidence_erd.mmd"):
        assert (tmp_path / "docs/diagrams" / filename).is_file()


def test_cross_date_snapshots_rejected(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="mismatched"):
        generate(tmp_path, fixture(), {"as_of": "2026-11-06"})


def test_stl_is_deterministic() -> None:
    assert stl_skyline(fixture()) == stl_skyline(fixture())
