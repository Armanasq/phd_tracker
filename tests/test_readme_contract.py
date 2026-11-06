from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"


def test_readme_link_contract():
    text = README.read_text(encoding="utf-8")
    local = re.findall(r"\]\(([^)]+)\)", text)
    broken = []
    for uri in local:
        if uri.startswith(("#", "https://", "http://", "mailto:", "../../")):
            continue
        path = unquote(uri.split("#", 1)[0].split("?", 1)[0])
        if not path:
            continue
        if not (ROOT / path).exists():
            broken.append(path)
    assert not broken, "Broken local links: " + ", ".join(sorted(set(broken)))


def test_readme_is_a_discoverable_control_plane():
    text = README.read_text(encoding="utf-8")
    expected = (
        "assets/readme/evidence_flow.svg",
        "docs/CAPABILITY_ATLAS.md",
        "docs/PLAYBOOKS.md",
        "docs/TODAY.md",
        "data/portfolio_frontier.json",
        "data/discovery_report.json",
        ".github/workflows/phd-intelligence.yml",
        "01-source-correction.yml",
        "02-opportunity-lead.yml",
        "03-automation-idea.yml",
    )
    for name in expected:
        assert name in text, f"Missing operational entry point: {name}"
    assert "AcademicPositions" in text or "academicpositions" in text
    assert "Gmail" in text
    assert "source" in text.lower()
    assert "<script" not in text
