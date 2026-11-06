from __future__ import annotations
import argparse
import html
import json
from datetime import date, datetime
from pathlib import Path
from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "readme"
FG = "#EAF2FB"
MUTED = "#9CB0C6"
TEAL = "#78E2CE"
AMBER = "#FFCA85"
PINK = "#FA98A0"


def read(name: str) -> dict:
    p = ROOT / "data" / name
    return json.loads(p.read_text(encoding="utf8")) if p.exists() else {}


def snapshot(today: date) -> dict:
    wb = load_workbook(ROOT / "PhD_Action_List.xlsx", read_only=True, data_only=False)
    rows = []
    for row in wb["Action list"].iter_rows(min_row=4, max_col=21, values_only=True):
        if not row[6] or not row[20]:
            continue
        deadline = row[1]
        if isinstance(deadline, datetime):
            deadline = deadline.date()
        if not isinstance(deadline, date):
            try:
                deadline = date.fromisoformat(str(deadline)[:10])
            except ValueError:
                deadline = None
        days = (deadline - today).days if deadline else None
        rows.append({"id": str(row[20]), "name": str(row[6]), "deadline": deadline,
                     "days": days, "source": str(row[19] or ""),
                     "state": str(row[4] or "")})
    closed = {"submitted", "skipped", "rejected", "accepted", "withdrawn", "not eligible"}
    active = [r for r in rows if r["days"] is not None and r["days"] >= 0
              and r["state"].lower().strip() not in closed]
    near = sorted([r for r in active if r["days"] <= 14],
                  key=lambda r: (r["days"], r["name"]))
    discovery = read("discovery_report.json")
    candidates = read("discovered_candidates.json").get("records", [])
    run = read("latest_run.json")
    conflicts = [x for x in run.get("source_statuses", [])
                 if x["status"] in {"contradiction_closed_portal", "review_source_changed"}]
    return {"today": today.isoformat(), "total": len(rows), "active": len(active),
            "near": near, "discovered": len(candidates), "new": discovery.get("new_count", 0),
            "sources": discovery.get("source_yield", {}), "conflicts": conflicts,
            "radar": len(read("research_radar.json").get("papers", [])),
            "tabs": wb.sheetnames}


def txt(x: int, y: int, value: object, size: int = 13, color: str = FG,
        weight: int = 400, extra: str = "") -> str:
    return ('<text x="{}" y="{}" font-family="Inter,Segoe UI,Arial,sans-serif" '
            'font-size="{}" font-weight="{}" fill="{}" {}>{}</text>').format(
                x, y, size, weight, color, extra, html.escape(str(value)))


def box(x: int, y: int, w: int, h: int, fill: str = "#142039",
        stroke: str = "#294057", rx: int = 12) -> str:
    return '<rect x="{}" y="{}" width="{}" height="{}" rx="{}" fill="{}" stroke="{}"/>'.format(
        x, y, w, h, rx, fill, stroke)


def svg(w: int, h: int, elements: list[str], title: str) -> str:
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}" '
            'viewBox="0 0 {} {}" role="img" aria-label="{}">'
            '<title>{}</title><defs><linearGradient id="bg" x1="0" x2="1" y1="0" y2="1">'
            '<stop stop-color="#091425"/><stop offset="1" stop-color="#15243B"/>'
            '</linearGradient></defs><rect width="{}" height="{}" fill="url(#bg)" rx="20"/>'
            '{}'
            '</svg>').format(w, h, w, h, html.escape(title, quote=True),
                           html.escape(title), w, h, "\n".join(elements))


def hero(s: dict) -> str:
    parts = [
        box(38, 34, 9, 9, TEAL, TEAL, 5),
        txt(58, 44, "EVIDENCEGRAPH  /  PHD INTELLIGENCE", 15, TEAL, 700),
        txt(1135, 45, "SNAPSHOT  " + s["today"], 12, MUTED, 500, 'text-anchor="end"'),
        txt(40, 107, "Your applications. One evidence graph.", 32, FG, 700),
        txt(40, 144, "Discover. Verify. Prioritize. Execute.", 23, MUTED, 400),
        txt(40, 180, "An auditable research-to-action operating system, not another list of links.", 14, MUTED),
    ]
    cards = [("TRACKED", s["total"], "Original workbook records", FG),
             ("FUTURE", s["active"], "Unclosed, unexpired", TEAL),
             ("NEXT 14 DAYS", len(s["near"]), "Deadline attention", AMBER),
             ("SOURCE LEADS", s["discovered"], "Awaiting independent review", "#9BB8FF")]
    for i, (label, n, caption, color) in enumerate(cards):
        x = 40 + i * 280
        parts += [box(x, 214, 260, 133), txt(x + 18, 245, label, 12, MUTED, 700),
                  txt(x + 18, 300, n, 40, color, 700),
                  txt(x + 18, 328, caption, 12, MUTED)]
    parts += [
        box(40, 370, 1100, 44, "#10263A", "#28495C"),
        txt(59, 397, "EVIDENCE STATUS", 12, TEAL, 700),
        txt(263, 397, str(len(s["conflicts"])) + " contradictions require review", 13, AMBER, 600),
        txt(1130, 397, "SOURCE VERIFIED ≠ ELIGIBILITY VERIFIED", 12, MUTED, 500, 'text-anchor="end"'),
    ]
    return svg(1180, 440, parts, "PhD tracker live metrics, deadline counts, discovery leads and source conflicts")


def deadlines(s: dict) -> str:
    rows = s["near"][:7]
    h = 118 + max(len(rows), 1) * 55
    p = [txt(24, 37, "DEADLINE FRONTIER", 17, FG, 700),
         txt(24, 60, "Next 14 days · incomplete / unconfirmed status", 12, MUTED)]
    for idx, row in enumerate(rows):
        y = 80 + idx * 55
        p += [box(24, y, 914, 46),
              txt(37, y + 29, str(row["days"]) + "d", 15,
                  PINK if row["days"] <= 2 else AMBER if row["days"] <= 7 else TEAL, 700),
              txt(96, y + 28, row["name"][:75] + ("..." if len(row["name"]) > 75 else ""), 12, FG, 500),
              txt(917, y + 28, row["deadline"].isoformat(), 12, MUTED, 500,
                  'text-anchor="end"')]
    if not rows:
        p.append(txt(24, 119, "No deadlines found within the next 14 days.", 14, MUTED))
    return svg(962, h, p, "Application deadline timeline sorted by days remaining")


def providers(s: dict) -> str:
    rows = sorted(s["sources"].items())
    height = 120 + max(len(rows), 1) * 65
    parts = [txt(25, 38, "DISCOVERY TELEMETRY", 17, FG, 700),
             txt(25, 60, "Observed reach, not claimed global recall", 12, MUTED)]
    for i, (name, record) in enumerate(rows):
        y = 81 + 65 * i
        status = record.get("health", "unknown")
        parts += [box(24, y, 514, 54), txt(39, y + 22, name.upper(), 13, FG, 700),
                  txt(39, y + 43, str(record.get("observed", 0)) + " seen  ·  " +
                      str(record.get("new_unique", 0)) + " newly unique", 11, MUTED),
                  txt(522, y + 22, status.upper(), 12,
                      TEAL if status == "ok" else AMBER if status == "degraded" else PINK,
                      600, 'text-anchor="end"')]
    if not rows:
        parts.append(txt(25, 111, "No collector telemetry available.", 13, MUTED))
    return svg(560, height, parts, "Discovery sources and source availability")


def readme(s: dict) -> str:
    upcoming = []
    for row in s["near"][:12]:
        link = "[Source](" + row["source"] + ")" if row["source"].startswith("https://") else "Not linked"
        name = row["name"].replace("|", "/")[:104]
        upcoming.append("| **{}d** | {} | {} | {} |".format(
            row["days"], row["deadline"].isoformat(), name, link))
    if not upcoming:
        upcoming = ["| — | — | No deadline within 14 days | — |"]
    provider_rows = [
        "| {} | {} | {} | {} |".format(k, v.get("observed", 0),
                                         v.get("new_unique", 0), v.get("health", "unknown"))
        for k, v in sorted(s["sources"].items())
    ] or ["| No source data | — | — | Unavailable |"]
    doc = """
<div align="center">

<img src="assets/readme/hero.svg" alt="Live source-driven PhD application dashboard" width="100%" />

**An evidence-first PhD application command center.**

[**Application workbook**](PhD_Action_List.xlsx) · [**Action Center**](../../issues/1) · [**Discovery inbox**](data/discovered_candidates.json) · [**Run the engine**](../../actions/workflows/phd-intelligence.yml)

</div>

> **Evidence policy** · Tracked applications are not necessarily open, funded or eligible. Automated discovery never changes user submission status. Dynamic visuals are generated from committed Excel and source artifacts.

<table>
<tr>
<td width="67%"><a href="assets/readme/deadlines.svg"><img src="assets/readme/deadlines.svg" alt="Deadline frontier" width="100%" /></a></td>
<td width="33%"><a href="assets/readme/providers.svg"><img src="assets/readme/providers.svg" alt="Search source health" width="100%" /></a></td>
</tr>
</table>

<sub>Last rendered: __DATE__ · GitHub READMEs do not execute embedded JavaScript; supported interaction is provided through native expandable sections, Mermaid, Issues and Actions.</sub>

## Command center

| Open | System action |
|:--|:--|
| **[Application tracker](PhD_Action_List.xlsx)** | Edit and confirm application decisions, deadlines, requirements and progress |
| **[Private Action Center](../../issues/1)** | See alerts, use owner-only snooze/priority commands and examine conflicts |
| **[Discover opportunities](../../actions/workflows/phd-intelligence.yml)** | Execute parallel source searches and reconcile the workbook |
| **[Research queue](data/discovered_candidates.json)** | Inspect URL identities, source histories and uncertain leads |
| **[Proof-obligation frontier](data/portfolio_frontier.json)** | Review reusable resources, readiness unknowns and source conflicts |
| **[CI and audits](../../actions/workflows/intelligence-ci.yml)** | Verify source adapter and workbook invariants |

## Next deadlines

| Days | Deadline | Application | Evidence |
|---:|:---:|---|---|
__DEADLINES__

<details>
<summary><b>Explore the interactive evidence pipeline</b></summary>

§§§mermaid
flowchart LR
    A["University vacancies"] --> D["Source evidence"]
    B["Independent search"] --> D
    C["Optional Gmail metadata"] --> D
    D --> E{"Deadline, funding, eligibility confirmed?"}
    E -->|"No"| Q["Research queue / verification"]
    E -->|"Yes"| X["Candidate decision workbook"]
    Q --> P["Proof obligations"]
    X --> P
    P --> N["Reminders / Action Center"]
    N -->|"Explicit owner action"| X
§§§

Research publications enter a distinct lane and cannot be inferred to be vacancies. Search result snippets never override dated institutional evidence.

</details>

<details>
<summary><b>Provider observability — find missed applications</b></summary>

| Collector | Observed | New distinct | State |
|---|---:|---:|---|
__PROVIDERS__

Broad search is **disabled until** the optional §BRAVE_SEARCH_API_KEY§ repository secret is configured. The Inria collector is an institutional signal, not comprehensive worldwide coverage. Each source must expose failure counts and unique yield; a completed Action does not mean comprehensive discovery.

[Discovery health report](data/discovery_report.json) · [Evidence source watch](data/latest_run.json)

</details>

<details>
<summary><b>Interactive owner commands — notifications without alert fatigue</b></summary>

Post a comment on the [private Action Center Issue](../../issues/1):

§§§text
/priority inria:2026-10570
/snooze inria:2026-10570 3d
/unsnooze inria:2026-10570
/mute inria:2026-10570
/unmute inria:2026-10570
/asset academic_cv ready
/asset research_statement in_progress
§§§

Only owner-authored commands on the marked Issue are interpreted. Unknown commands cannot execute code. Deadline-day and day-before reminders bypass snoozes. Outbound multi-channel notifications require optional §APPRISE_URLS§ secrets.

</details>

<details>
<summary><b>Portfolio optimization — novel synthesis and limitations</b></summary>

**Application-as-constraint graph.** A candidate may have evidence assertions, deadlines and eligibility requirements. The applicant has reusable preparation assets whose readiness is either explicit or unknown. The system ranks *potential work reuse* across multiple applications and exposes proof debt, rather than inventing probabilities of acceptance.

The research frontier is an original engineering synthesis, **not** a proven globally first invention.

[Editable readiness](data/application_assets.json) · [Decision frontier](data/portfolio_frontier.json) · [Technical RFC](docs/PRODUCT_RFC.md)

</details>

## System architecture

§§§mermaid
flowchart TD
    subgraph Discovery
      I["Inria institutional scan"] 
      S["Optional broad web search"]
      R["arXiv publications"]
    end
    I --> C["Identity and provenance resolution"]
    S --> C
    C --> V["Source validation + contradiction detection"]
    V --> Q["Research queue"]
    Q --> W["Excel application tracker"]
    W --> F["Deadline + portfolio frontier"]
    R --> P["Research context only"]
    F --> N["Private Action Center / notifications"]
    P --> N
    N --> U["Owner decisions"]
    U --> W
§§§

<details>
<summary><b>Local development, tests and supported GitHub capabilities</b></summary>

§§§bash
python -m pip install -r requirements-intelligence.txt
python -m pytest -q tests
python scripts/refresh_tracker.py --online
python scripts/portfolio_frontier.py
python scripts/render_readme.py
§§§

UI uses generated SVG, standard Markdown tables, collapsible HTML §details§, Mermaid, and GitHub Issues. Arbitrary JavaScript, iframes, React components, server-rendered state and executable JS inside the README are not supported by GitHub's sanitizer. The SVG files are static snapshots, regenerated by Actions.

</details>

## Reliability contract

| Boundary | Guarantee |
|---|---|
| Application status | Human-owned; discovery cannot mark something submitted |
| Source identity | Stable IDs and canonical URL aliases |
| Contradictory deadlines | Never silently overwrite; retain observations and require review |
| Scheduling | Scheduled searches and transaction-safe publishing |
| Notifications | Deduplication, explicit controls and last-day override |
| Workbook | Existing sheets retained; outputs validated before publication |
| Privacy | Private repository; optional restricted Gmail metadata access |
| Evidence | Inspectable URLs and dated observation artifacts |

<sub>Engineering precedents: [changedetection.io](https://github.com/dgtlmoon/changedetection.io), [Apprise](https://github.com/caronc/apprise), [dlt](https://github.com/dlt-hub/dlt) and [Crawl4AI](https://github.com/unclecode/crawl4ai). <b>These are not claims of exclusive novelty, validated market size or billion-dollar valuation.</b></sub>
"""
    return (doc.replace("__DATE__", s["today"])
               .replace("__DEADLINES__", "\n".join(upcoming))
               .replace("__PROVIDERS__", "\n".join(provider_rows))
               .replace("§", chr(96)))


def render(today: date) -> dict:
    s = snapshot(today)
    ASSETS.mkdir(parents=True, exist_ok=True)
    for name, payload in {
        "hero.svg": hero(s),
        "deadlines.svg": deadlines(s),
        "providers.svg": providers(s),
    }.items():
        (ASSETS / name).write_text(payload, encoding="utf8")
    (ROOT / "README.md").write_text(readme(s), encoding="utf8")
    report = {"generated_at": s["today"], "applications": s["total"],
              "future": s["active"], "due_14d": len(s["near"]),
              "source_leads": s["discovered"], "contradictions": len(s["conflicts"]),
              "providers": s["sources"], "worksheets": s["tabs"]}
    (ASSETS / "metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf8")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--date", default=date.today().isoformat())
    args = parser.parse_args()
    print(json.dumps(render(date.fromisoformat(args.date))))
