from __future__ import annotations

import html
import json
import math
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COORDINATES = (
    ("Germany", 13.405, 52.52, ("karlsruhe institute", "kit mrt", "tum ", "technical university of munich", "max planck", "imprs", "university of tübingen", "university of tubingen", "rwth aachen", "university of freiburg", "lmu ", "university of bremen", "university of bonn")),
    ("United Kingdom", -0.1276, 51.5072, ("ucl ", "sainsbury wellcome", "university of southampton", "northeastern university london", "university of birmingham", "university of bath", "university of edinburgh", "university of exeter", "university of oxford", "oxford dphil", "cambridge", "uea ", "university of manchester", "imperial college", "norwich research park", "university of glasgow", "university of bristol", "university of sheffield")),
    ("Netherlands", 4.9041, 52.3676, ("tu delft", "university of amsterdam", "tu/e eindhoven", "eindhoven university", "utrecht university", "university of groningen", "leiden university", "wageningen university", "radboud university", "university of twente")),
    ("Switzerland", 7.4474, 46.948, ("eth zurich", "epfl ", "university of bern", "university of zurich", "university of geneva", "swiss government excellence", "university of basel")),
    ("Norway", 10.7522, 59.9139, ("ntnu ", "university of oslo", "osloMet", "oslomet", "university of agder", "university of bergen", "uit ", "norwegian university")),
    ("Sweden", 18.0632, 59.3346, ("uppsala university", "linkoeping university", "linköping university", "kth ", "lund university", "chalmers", "university of gothenburg")),
    ("Denmark", 12.5683, 55.6761, ("university of copenhagen", "aalborg university", "aarhus university", "technical university of denmark", "dtu ")),
    ("Japan", 139.6917, 35.6895, ("institute of science tokyo", "hokkaido university", "nagoya university", "saitama university", "oist ", "university of osaka", "kyoto university", "university of tokyo", "tokyo institute of technology", "tohoku university")),
    ("France", 2.3522, 48.8566, ("inria ", "inria-", "sorbonne", "université paris", "university of paris", "paris saclay", "paris-saclay", "ecole polytechnique", "école polytechnique")),
    ("Italy", 12.4964, 41.9028, ("politecnico di torino", "politecnico di milano", "university of bologna", "sapienza ", "university of padua", "university of trento")),
    ("Cyprus", 33.3823, 35.1856, ("university of cyprus", "cyprus university")),
    ("Luxembourg", 6.1319, 49.6116, ("university of luxembourg", "luxembourg yadias")),
    ("United States", -77.0369, 38.9072, ("george washington university", "mit ", "massachusetts institute", "stanford university", "carnegie mellon", "university of california", "university of washington", "harvard university", "northeastern university boston")),
    ("Canada", -75.6972, 45.4215, ("memorial university", "york university", "mila ", "university of toronto", "university of waterloo", "university of british columbia", "mcgill university", "university of montreal", "polytechnique montréal")),
    ("Australia", 149.1300, -35.2809, ("australian national university", "university of melbourne", "university of sydney", "monash university", "university of queensland")),
    ("Austria", 16.3738, 48.2082, ("tu wien", "vienna university", "university of vienna", "graz university", "university of innsbruck")),
    ("Belgium", 4.3517, 50.8503, ("ku leuven", "university of antwerp", "ghent university", "vrije universiteit brussel")),
    ("Finland", 24.9384, 60.1699, ("aalto university", "university of helsinki", "tampere university", "university of oulu")),
)


def sanitize(value: object, limit: int = 120) -> str:
    return html.escape(re.sub(r"\s+", " ", str(value or "")).strip()[:limit], quote=True)


def diagram_text(value: object, limit: int = 64) -> str:
    s = re.sub(r"[^A-Za-z0-9 ._/-]", " ", str(value or ""))
    return re.sub(r"\s+", " ", s).strip()[:limit] or "Unspecified"


def country_for(name: str) -> str | None:
    value = str(name).casefold()
    matches = [label for label, _, _, terms in COORDINATES if any(term.casefold() in value for term in terms)]
    return matches[0] if len(matches) == 1 else None


def country_map(view: dict) -> tuple[dict, int]:
    counts: Counter[str] = Counter()
    examples: dict[str, list[str]] = defaultdict(list)
    matched = 0
    for app in view["applications"]:
        name = str(app["name"])
        country = country_for(name)
        if country is None:
            continue
        matched += 1
        counts[country] += 1
        if len(examples[country]) < 3:
            examples[country].append(str(app["id"]))
    features = []
    for label, lon, lat, _ in COORDINATES:
        n = counts[label]
        if not n:
            continue
        features.append({
            "type": "Feature",
            "properties": {
                "title": f"{label}: {n} application records",
                "description": "Country-level aggregate inferred from an unambiguous institution name; pin placed at representative capital city, not at a university",
                "count": n,
                "sample_source_ids": ", ".join(examples[label]),
                "marker-color": "#19b5b6" if n >= 8 else "#9f61e8" if n >= 3 else "#4384ff",
                "marker-size": "large" if n >= 8 else "medium",
            },
            "geometry": {"type": "Point", "coordinates": [lon, lat]},
        })
    return {"type": "FeatureCollection", "features": features}, matched


def deadline_buckets(view: dict) -> list[tuple[str, int]]:
    apps = [a for a in view["applications"] if a["days"] >= 0]
    return [
        ("0-7 days", sum(0 <= a["days"] <= 7 for a in apps)),
        ("8-14 days", sum(8 <= a["days"] <= 14 for a in apps)),
        ("15-30 days", sum(15 <= a["days"] <= 30 for a in apps)),
        ("31-60 days", sum(31 <= a["days"] <= 60 for a in apps)),
        ("61+ days", sum(a["days"] >= 61 for a in apps)),
    ]


def mermaid_flowchart(view: dict) -> str:
    n = view["metrics"]["tracked"]
    p = len(view["providers"])
    flags = view["metrics"]["source_conflicts"]
    return f"""flowchart LR
    A["Discovery sources · {p} monitored"] --> B["Ingest & deduplicate"]
    B --> C{{"Evidence verification"}}
    C -->|"Source verified"| D["Application frontier · {n}"]
    C -->|"Unresolved source"| E["Evidence review · {flags} conflicts"]
    E --> C
    D --> F["Deadline & proof planning"]
    F --> G["Owner confirmation"]
    G --> H["Execution ledger"]
    classDef source fill:#172b51,color:#e8f4ff,stroke:#49b8ff,stroke-width:2px
    classDef verified fill:#103c3b,color:#d7fff4,stroke:#51dcb4,stroke-width:2px
    classDef attention fill:#46263a,color:#fff0f3,stroke:#f58bb7,stroke-width:2px
    class A,B source
    class D,F,G,H verified
    class E attention"""


def mermaid_sankey(view: dict) -> str:
    buckets = deadline_buckets(view)
    return "sankey-beta\n" + "\n".join(f"Recorded frontier,{label},{amount}" for label, amount in buckets if amount > 0)


def mermaid_gantt(view: dict) -> str:
    upcoming = sorted(
        (a for a in view["applications"] if 0 <= a["days"] <= 60),
        key=lambda a: (a["days"], a["id"]),
    )[:11]
    lines = [
        "gantt",
        f"    title Recorded PhD deadlines - snapshot {view['as_of']}",
        "    dateFormat YYYY-MM-DD",
        "    axisFormat %b %d",
        "    section Final application deadlines",
    ]
    for i, app in enumerate(upcoming):
        title = diagram_text(f'{app["id"]} {app["name"]}', 49)
        lines.append(f'    {title} :milestone, d{i}, {app["deadline"]}, 0d')
    if not upcoming:
        lines.append(f'    No upcoming deadlines :milestone, none, {view["as_of"]}, 0d')
    return "\n".join(lines)


def mermaid_quadrant(view: dict) -> str:
    apps = sorted(
        (a for a in view["applications"] if 0 <= a["days"] <= 90),
        key=lambda a: (a["days"], a["id"]),
    )[:20]
    lines = [
        "quadrantChart",
        "    title Calendar urgency vs unresolved evidence workload",
        "    x-axis Lower urgency --> Higher urgency",
        "    y-axis Lower proof debt --> Higher proof debt",
        "    quadrant-1 Immediate evidence review",
        "    quadrant-2 Build evidence first",
        "    quadrant-3 Monitor",
        "    quadrant-4 Deadline execution",
    ]
    for i, a in enumerate(apps):
        urgency = max(.01, min(.99, 1 - a["days"] / 90))
        unknowns = len(a.get("unknown_documents", []))
        obligations = len(a.get("proof_obligations", []))
        debt = min(.99, max(.01, (unknowns + obligations) / 8))
        lines.append(f'    R{i+1:02d}: [{urgency:.3f}, {debt:.3f}]')
    return "\n".join(lines)


def mermaid_xychart(view: dict) -> str:
    buckets = deadline_buckets(view)
    maximum = max(1, *(count for _, count in buckets))
    upper = max(4, int(math.ceil(maximum / 5) * 5))
    xaxis = ", ".join('"' + label.replace(" days", "d") + '"' for label, _ in buckets)
    counts = ", ".join(str(count) for _, count in buckets)
    return f"""xychart-beta
    title "Application deadline horizon"
    x-axis [{xaxis}]
    y-axis "Application records" 0 --> {upper}
    bar [{counts}]"""


def mermaid_sequence(view: dict) -> str:
    return """sequenceDiagram
    actor Owner
    participant Action as GitHub Actions
    participant Discovery as Discovery providers
    participant Evidence as Evidence validators
    participant Store as Workbook and ledger
    Owner->>Action: Run discovery and reconciliation
    Action->>Discovery: Fetch institution listings
    Discovery-->>Action: Records plus provider failures
    Action->>Evidence: Resolve IDs and contradictions
    Evidence-->>Action: Supported claims and unknowns
    Action->>Store: Reconcile observations
    Store-->>Owner: Decision frontier and dated agenda
    Owner->>Store: Confirm applicant actions explicitly"""


def mermaid_states() -> str:
    return """stateDiagram-v2
    [*] --> Discovered
    Discovered --> EvidenceReview: Lead indexed
    EvidenceReview --> Recheck: Source conflicted
    Recheck --> EvidenceReview: New observation
    EvidenceReview --> Shortlisted: Evidence sufficient
    EvidenceReview --> Excluded: Ineligible or duplicate
    Shortlisted --> Preparation: Owner selects
    Preparation --> SubmissionReview: Documents collected
    SubmissionReview --> Submitted: Owner confirms receipt
    SubmissionReview --> Preparation: Additional requirements
    Submitted --> [*]
    Excluded --> [*]"""


def mermaid_erd() -> str:
    return """erDiagram
    APPLICATION ||--o{ DOCUMENT_MENTION : references
    APPLICATION ||--o{ SOURCE_OBSERVATION : evaluated_by
    SOURCE_OBSERVATION }o--|| PROVIDER : collected_through
    APPLICATION ||--o{ EXECUTION_STEP : scheduled_for
    RESEARCH_PAPER }o--o{ TOPIC : grouped_as
    DOCUMENT_MENTION }o--|| RESOURCE : describes
    APPLICATION {
        string source_id PK
        date final_deadline
        string decision
    }
    SOURCE_OBSERVATION {
        string status
        string url
        date observed_at
    }
    RESOURCE {
        string document_id PK
        string readiness_state
    }"""


def mermaid_mindmap() -> str:
    return """mindmap
    root((PhD Research))
      Embodied AI
        Robotics
        SLAM
        VLA
      Machine Learning
        Foundation models
        Agentic AI
        Scientific ML
      Medical AI
        Imaging
        Clinical reasoning
        Explainability
      Engineering
        Control
        Planning
        Optimization"""


def mermaid_timeline(view: dict) -> str:
    research_n = view["metrics"]["research_papers"]
    return f"""timeline
    title EvidenceGraph observation snapshot
    {view["as_of"]} : {view["metrics"]["tracked"]} dated application records
                 : {research_n} indexed research signals
                 : {view["metrics"]["source_conflicts"]} source conflict flags"""


def stl_skyline(view: dict) -> str:
    buckets = deadline_buckets(view)
    lines = ["solid deadline_horizon"]
    def facet(a: tuple[float, float, float], b: tuple[float, float, float], c: tuple[float, float, float]) -> None:
        lines.extend([
            "facet normal 0 0 0",
            "  outer loop",
            f"    vertex {a[0]:.3f} {a[1]:.3f} {a[2]:.3f}",
            f"    vertex {b[0]:.3f} {b[1]:.3f} {b[2]:.3f}",
            f"    vertex {c[0]:.3f} {c[1]:.3f} {c[2]:.3f}",
            "  endloop",
            "endfacet",
        ])
    for i, (_, amount) in enumerate(buckets):
        x0, x1 = i * 1.5, i * 1.5 + .95
        y0, y1 = 0.0, 1.0
        h = max(.08, amount * .13)
        v = [
            (x0, y0, 0), (x1, y0, 0), (x1, y1, 0), (x0, y1, 0),
            (x0, y0, h), (x1, y0, h), (x1, y1, h), (x0, y1, h),
        ]
        for quad in ((0,3,2,1),(4,5,6,7),(0,1,5,4),(1,2,6,5),(2,3,7,6),(3,0,4,7)):
            a,b,c,d = quad
            facet(v[a],v[b],v[c])
            facet(v[a],v[c],v[d])
    lines.append("endsolid deadline_horizon")
    return "\n".join(lines) + "\n"


def markdown(view: dict, plan: dict, collection: dict, mapped: int) -> str:
    m = view["metrics"]
    n = len(view["providers"])
    healthy = sum(p["health"] == "ok" for p in view["providers"])
    degraded = sum(p["health"] in ("degraded", "disabled") for p in view["providers"])
    nearest = sorted((a for a in view["applications"] if a["days"] >= 0), key=lambda a: (a["days"], a["id"]))[:7]
    mermaid = lambda s: chr(96)*3 + "mermaid\n" + s + "\n" + chr(96)*3
    geojson = chr(96)*3 + "geojson\n" + json.dumps(collection, ensure_ascii=False, separators=(",", ":")) + "\n" + chr(96)*3
    rows = [
        "| **{}d** | {} | {} | [Source]({}) |".format(
            a["days"], a["deadline"], sanitize(a["name"],90).replace("|","/"), a["source"]
        ) if a["source"].startswith("https://") else
        "| **{}d** | {} | {} | — |".format(a["days"], a["deadline"], sanitize(a["name"],90))
        for a in nearest
    ] or ["| — | — | No upcoming records in the snapshot | — |"]
    country_rows = []
    for feature in sorted(collection["features"], key=lambda x: -x["properties"]["count"]):
        p = feature["properties"]
        country_rows.append(f'| {sanitize(p["title"])} | {sanitize(p["sample_source_ids"])} |')
    country_rows = country_rows[:15]
    countries = len(collection["features"])
    apps = m["tracked"]
    due = m["next_seven_days"]
    research = m["research_papers"]
    conflicts = m["source_conflicts"]
    unknown = m["unknown_document_mentions"]
    at = sanitize(view["as_of"])
    return f"""<div align="center">

# PhD Tracker · EvidenceGraph

**AI-powered research discovery, source verification, application planning, and reproducible execution.**

<a href="../../actions/workflows/experience-lab.yml"><img src="assets/readme/kinetic_cover.svg" alt="EvidenceGraph: source-derived research intelligence orbital cover" width="100%"/></a>

[**DISCOVER**](#research--application-pipeline) · [**VERIFY**](#opportunity-funnel--actual-deadline-horizons) · [**ANALYZE**](#research-focus-quadrant) · [**PLAN**](#deadline-gantt--application-milestones) · [**SIMULATE**](#interactive-exploration--simulation-lab) · [**EXECUTE**](#github-native-workflow-console)

<sub>Observed {at} · Metrics are derived from source snapshots, not example values or inferred admissions outcomes.</sub>

</div>

<table><tr>
<td align="center" width="16%"><b>OPPORTUNITIES</b><h2>{apps}</h2><sub>dated frontier</sub></td>
<td align="center" width="16%"><b>UPCOMING</b><h2>{due}</h2><sub>next seven days</sub></td>
<td align="center" width="16%"><b>PROOF STATES</b><h2>{unknown}</h2><sub>unknown document mentions</sub></td>
<td align="center" width="16%"><b>RESEARCH</b><h2>{research}</h2><sub>indexed papers</sub></td>
<td align="center" width="16%"><b>SOURCES</b><h2>{healthy}/{n}</h2><sub>healthy providers</sub></td>
<td align="center" width="16%"><b>CONTRADICTIONS</b><h2>{conflicts}</h2><sub>source review flags</sub></td>
</tr></table>

[**Overview**](#research--application-pipeline) · [**Pipeline**](#research--application-pipeline) · [**Opportunity Map**](#global-opportunities--interactive-github-map) · [**Timeline**](#deadline-gantt--application-milestones) · [**Knowledge Graph**](#research--application-knowledge-graph) · [**Applications**](#upcoming-application-records) · [**Simulation Lab**](#interactive-exploration--simulation-lab) · [**Workflows**](#github-native-workflow-console)

---

## Research & application pipeline

The diagram below is **native Mermaid**. GitHub renders it as a diagram, not as an SVG screenshot.

{mermaid(mermaid_flowchart(view))}

## Opportunity funnel · actual deadline horizons

This Sankey partitions the {apps} dated portfolio records by their remaining calendar horizon; it does not imply historical conversion between recruitment stages.

{mermaid(mermaid_sankey(view))}

<details>
<summary><b>Show the source-provider verification mix</b></summary>

| Provider | Recorded health | Observed leads | New unique leads |
|:--|:--|--:|--:|
{chr(10).join(f'| {sanitize(p["name"])} | {sanitize(p["health"])} | {p["observed"]} | {p["new_unique"]} |' for p in view["providers"])}

Provider health is not an estimate of search completeness. {degraded} channels are degraded or disabled.

</details>

## Deadline Gantt · application milestones

{mermaid(mermaid_gantt(view))}

<details>
<summary><b>Expand the quantitative deadline horizon chart</b></summary>

{mermaid(mermaid_xychart(view))}

</details>

## Global opportunities · interactive GitHub map

{geojson}

**{mapped}/{apps}** applications have unambiguous institution-name country matches, aggregated into **{countries}** country markers. The markers are at representative capital locations, **not university campus coordinates**. The remaining {apps-mapped} records are deliberately excluded from the geographic visualization rather than assigned guessed locations.

<details>
<summary><b>Explore country counts and mapped source IDs</b></summary>

| Country aggregation | Example application IDs |
|:--|:--|
{chr(10).join(country_rows)}

[Complete GeoJSON file](data/readme_opportunities.geojson) · [Source portfolio](data/portfolio_frontier.json)

</details>

## Research & application knowledge graph

This native Mermaid ER diagram represents relationships from the actual application, source-monitor, resource, and research schemas.

{mermaid(mermaid_erd())}

<details>
<summary><b>Agent/tool orchestration · expand Mermaid sequence diagram</b></summary>

{mermaid(mermaid_sequence(view))}

</details>

<details>
<summary><b>Application state machine · expand Mermaid states</b></summary>

{mermaid(mermaid_states())}

The workflow is a **process model**, not confirmation that tracked applications have been submitted.

</details>

## Research focus quadrant

A transparent, data-based proxy: horizontal position is calendar urgency within 90 days, and vertical position is unresolved document mentions plus explicit proof obligations, divided by eight and capped at one. Neither axis is publication impact or admission probability.

{mermaid(mermaid_quadrant(view))}

[See application records and exact source IDs](data/experience_view.json) · [Open the research radar](data/research_radar.json)

<details>
<summary><b>Research mind map · expand</b></summary>

{mermaid(mermaid_mindmap())}

</details>

## Interactive exploration & simulation lab

<table><tr>
<td width="50%" valign="top">
<h3>Interact with actual application data</h3>
<p>Drag and zoom the application-to-document graph, scrub 60 days, tune proof-debt weights, query through the keyboard command palette, move scenario cards, and export CSV/JSON.</p>
<p><b><a href="dashboard/index.html">Open the self-contained browser application</a></b></p>
</td>
<td width="50%" valign="top">
<h3>Rotate the 3D deadline skyline</h3>
<p>GitHub renders the generated STL as a rotatable 3D model. Five towers encode real counts in the deadline horizon bins, not a fabricated 3D scene.</p>
<p><b><a href="assets/readme/deadline_skyline.stl">Explore the interactive STL model</a></b></p>
</td>
</tr></table>

## GitHub-native workflow console

The controls below invoke **real GitHub workflows and repository forms**, not inert mock buttons.

| Action | Real execution |
|:--|:--|
| **Run an analysis** | [Open scenario-lab workflow inputs](../../actions/workflows/experience-lab.yml) |
| **Update opportunities** | [Run discovery and reconciliation](../../actions/workflows/phd-intelligence.yml) |
| **Change owner status** | [Authenticated private issue controls](../../issues/1) |
| **Submit an opportunity** | [Structured opportunity issue form](../../issues/new?template=02-opportunity-lead.yml) |
| **Correct source evidence** | [Source-correction form](../../issues/new?template=01-source-correction.yml) |
| **Propose an automation** | [Automation-idea form](../../issues/new?template=03-automation-idea.yml) |
| **Open application tasks** | [Dated execution ledger](docs/TODAY.md) |
| **Download the tracker** | [Complete workbook](PhD_Action_List.xlsx) |

[CI checks](../../actions/workflows/intelligence-ci.yml) · [Workbook audit](../../actions/workflows/audit-workbook.yml) · [README regeneration](../../actions/workflows/readme-render.yml) · [JSON evidence](data/experience_view.json)

## Upcoming application records

| Days left | Deadline | Opportunity | Primary evidence |
|:--|:--|:--|:--|
{chr(10).join(rows)}

<details>
<summary><b>Advanced visual research laboratory: diagrams and source contracts</b></summary>

The following are generated Mermaid artifacts and can be opened independently on GitHub:

- [Pipeline graph](docs/diagrams/pipeline.mmd)
- [Deadline Sankey](docs/diagrams/horizon_sankey.mmd)
- [Application Gantt](docs/diagrams/deadlines.mmd)
- [Evidence ER model](docs/diagrams/evidence_erd.mmd)
- [Research quadrant](docs/diagrams/priority_quadrant.mmd)
- [Application states](docs/diagrams/application_states.mmd)
- [Agent orchestration](docs/diagrams/orchestration.mmd)
- [Research mind map](docs/diagrams/research_map.mmd)
- [Deadline XY chart](docs/diagrams/deadline_xy.mmd)

[Source data contracts](data/experience_view.json) · [JSON-LD lineage](data/experience_lineage.jsonld) · [Architecture](docs/ARCHITECTURE.md) · [Capability atlas](docs/CAPABILITY_ATLAS.md) · [Playbooks](docs/PLAYBOOKS.md)

</details>

<sub>EvidenceGraph · Reproducible · Generated from source data · Observation: {at}. Research papers are not vacancy notices. Unknown document readiness is not confirmed missing documentation. GitHub README renders Mermaid, GeoJSON and linked STL natively; rich JavaScript interactions run in the downloadable browser application.</sub>
"""


def generate(root: Path, view: dict, plan: dict) -> str:
    if view["as_of"] != plan["as_of"]:
        raise ValueError("README studio snapshots have mismatched observation dates")
    collection, matched = country_map(view)
    root.joinpath("data").mkdir(exist_ok=True, parents=True)
    root.joinpath("docs", "diagrams").mkdir(exist_ok=True, parents=True)
    root.joinpath("assets", "readme").mkdir(exist_ok=True, parents=True)
    (root / "data" / "readme_opportunities.geojson").write_text(
        json.dumps(collection, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    diagrams = {
        "pipeline.mmd": mermaid_flowchart(view),
        "horizon_sankey.mmd": mermaid_sankey(view),
        "deadlines.mmd": mermaid_gantt(view),
        "priority_quadrant.mmd": mermaid_quadrant(view),
        "deadline_xy.mmd": mermaid_xychart(view),
        "orchestration.mmd": mermaid_sequence(view),
        "application_states.mmd": mermaid_states(),
        "evidence_erd.mmd": mermaid_erd(),
        "research_map.mmd": mermaid_mindmap(),
    }
    for name, content in diagrams.items():
        (root / "docs" / "diagrams" / name).write_text(content + "\n", encoding="utf-8")
    (root / "assets" / "readme" / "deadline_skyline.stl").write_text(
        stl_skyline(view), encoding="utf-8"
    )
    return markdown(view, plan, collection, matched)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=ROOT)
    args = parser.parse_args()
    view = json.loads((args.root / "data" / "experience_view.json").read_text(encoding="utf-8"))
    plan = json.loads((args.root / "data" / "execution_plan.json").read_text(encoding="utf-8"))
    print(generate(args.root, view, plan))
