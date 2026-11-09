from __future__ import annotations

import json
from pathlib import Path
from xml.etree import ElementTree

from scripts.render_command_center import PUBLIC_README, report_paths
from scripts.sync_repository_metadata import load_metadata

ROOT = Path(__file__).resolve().parents[1]
PAGES = "https://armanasq.github.io/phd_tracker/"


def test_main_readme_is_consistent_and_short() -> None:
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme == PUBLIC_README
    assert len(readme) < 12000
    assert "docs/RESEARCH_REPORT.md" in readme
    assert "[Open workspace](" + PAGES + ")" in readme
    assert "local Python service" in readme
    assert "not deployed to GitHub Pages" in readme
    assert (ROOT / "docs" / "RESEARCH_REPORT.md").stat().st_size > 20000


def test_generated_research_report_paths_are_rebased() -> None:
    sample = (
        "[Data](data/portfolio_frontier.json) "
        "[Issue](../../issues/1) "
        "[Action](../../actions/workflows/phd-intelligence.yml) "
        '<a href="../../issues/1">Issues</a> '
        '<img src="assets/readme/kinetic_cover.svg">'
    )
    updated = report_paths(sample)
    assert "](../data/portfolio_frontier.json)" in updated
    assert "https://github.com/Armanasq/phd_tracker/issues/1" in updated
    assert "https://github.com/Armanasq/phd_tracker/actions/workflows/phd-intelligence.yml" in updated
    assert 'src="../assets/readme/kinetic_cover.svg"' in updated


def test_canonical_public_website_metadata_and_resources() -> None:
    site = ROOT / "site"
    html = (site / "index.html").read_text(encoding="utf-8")
    assert '<link rel="canonical" href="' + PAGES + '">' in html
    assert '<meta property="og:url" content="' + PAGES + '">' in html
    assert '<meta property="og:site_name" content="PhD Atlas">' in html
    assert 'href="./favicon.svg"' in html
    assert "API key" not in html
    assert ElementTree.parse(site / "favicon.svg").getroot().tag.endswith("svg")
    root = ElementTree.parse(site / "sitemap.xml").getroot()
    urls = [entry.text for entry in root.iter() if entry.tag.endswith("loc")]
    assert PAGES in urls
    assert PAGES + "evidencegraph/" in urls
    assert len(urls) == len(set(urls))


def test_release_manifest_and_repository_about_settings() -> None:
    version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
    assert version == "0.1.0"
    assert f"## {version} " in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    metadata = load_metadata()
    settings = json.loads((ROOT / ".github/repository-metadata.json").read_text(encoding="utf-8"))
    assert metadata["homepage"] == PAGES
    assert metadata == {k: settings[k] for k in ("description", "homepage", "topics")}
    workflow = (ROOT / ".github/workflows/release.yml").read_text(encoding="utf-8")
    assert "gh release create" in workflow
    assert "--prerelease" in workflow
    assert "contents: write" in workflow
    pages = (ROOT / ".github/workflows/publish-cockpit.yml").read_text(encoding="utf-8")
    assert "actions/deploy-pages@v4" in pages
    assert "site/favicon.svg" in pages
    assert "site/sitemap.xml" in pages
