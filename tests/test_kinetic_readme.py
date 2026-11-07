from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from pathlib import Path

from scripts.kinetic_readme import kinetic_cover, kinetic_lane, write_assets


def view() -> dict:
    return {
        "as_of": "2026-11-07",
        "metrics": {
            "tracked": 12, "future": 3, "next_seven_days": 2,
            "source_conflicts": 1, "research_papers": 8,
        },
        "providers": [
            {"name": "inria", "health": "ok"},
            {"name": "brave", "health": "disabled"},
        ],
        "applications": [
            {"id": "A", "name": "Robot SLAM", "deadline": "2026-11-08", "days": 1},
            {"id": "B", "name": "Clinical Imaging", "deadline": "2026-11-13", "days": 6},
            {"id": "C", "name": 'Title <script>alert("x")</script>', "deadline": "2026-11-30", "days": 23},
        ],
    }


def test_kinetic_assets_are_valid_self_contained_svg(tmp_path: Path) -> None:
    first, second = write_assets(view(), tmp_path)
    assert first == "kinetic_cover.svg"
    assert second == "kinetic_lane.svg"
    for name in (first, second):
        source = (tmp_path / name).read_text(encoding="utf-8")
        root = ET.fromstring(source)
        assert root.tag.endswith("svg")
        assert "animation:" in source
        assert "<script" not in source
        assert "http://" not in source
        assert "2026-11-07" in source or "source" in source.lower()


def test_visual_metrics_are_observed_not_placeholder() -> None:
    source = kinetic_cover(view())
    assert "3" in source
    assert "2 WITHIN 7 DAYS" in source
    assert "SOURCE CONFLICTS" in source
    assert "&lt;script&gt;" in source
    assert "<script>alert" not in source


def test_pulse_reports_source_health() -> None:
    source = kinetic_lane(view())
    assert "1/2 healthy" in source
    assert "12 tracked" in source
    assert "1 conflicting" in source
    assert "2 ≤7d" in source
