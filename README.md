<div align="center">

# PhD Tracker · EvidenceGraph

**AI-powered research discovery, source verification, application planning, and reproducible execution.**

<a href="../../actions/workflows/experience-lab.yml"><img src="assets/readme/kinetic_cover.svg" alt="EvidenceGraph: source-derived research intelligence orbital cover" width="100%"/></a>

[**DISCOVER**](#research--application-pipeline) · [**VERIFY**](#opportunity-funnel--actual-deadline-horizons) · [**ANALYZE**](#research-focus-quadrant) · [**PLAN**](#deadline-gantt--application-milestones) · [**SIMULATE**](#interactive-exploration--simulation-lab) · [**EXECUTE**](#github-native-workflow-console)

<sub>Observed 2026-11-07 · Metrics are derived from source snapshots, not example values or inferred admissions outcomes.</sub>

</div>

<table><tr>
<td align="center" width="16%"><b>OPPORTUNITIES</b><h2>100</h2><sub>dated frontier</sub></td>
<td align="center" width="16%"><b>UPCOMING</b><h2>6</h2><sub>next seven days</sub></td>
<td align="center" width="16%"><b>PROOF STATES</b><h2>319</h2><sub>unknown document mentions</sub></td>
<td align="center" width="16%"><b>RESEARCH</b><h2>34</h2><sub>indexed papers</sub></td>
<td align="center" width="16%"><b>SOURCES</b><h2>1/4</h2><sub>healthy providers</sub></td>
<td align="center" width="16%"><b>CONTRADICTIONS</b><h2>1</h2><sub>source review flags</sub></td>
</tr></table>

[**Overview**](#research--application-pipeline) · [**Pipeline**](#research--application-pipeline) · [**Opportunity Map**](#global-opportunities--interactive-github-map) · [**Timeline**](#deadline-gantt--application-milestones) · [**Knowledge Graph**](#research--application-knowledge-graph) · [**Applications**](#upcoming-application-records) · [**Simulation Lab**](#interactive-exploration--simulation-lab) · [**Workflows**](#github-native-workflow-console)

---

## Research & application pipeline

The diagram below is **native Mermaid**. GitHub renders it as a diagram, not as an SVG screenshot.

```mermaid
flowchart LR
    A["Discovery sources · 4 monitored"] --> B["Ingest & deduplicate"]
    B --> C{"Evidence verification"}
    C -->|"Source verified"| D["Application frontier · 100"]
    C -->|"Unresolved source"| E["Evidence review · 1 conflicts"]
    E --> C
    D --> F["Deadline & proof planning"]
    F --> G["Owner confirmation"]
    G --> H["Execution ledger"]
    classDef source fill:#172b51,color:#e8f4ff,stroke:#49b8ff,stroke-width:2px
    classDef verified fill:#103c3b,color:#d7fff4,stroke:#51dcb4,stroke-width:2px
    classDef attention fill:#46263a,color:#fff0f3,stroke:#f58bb7,stroke-width:2px
    class A,B source
    class D,F,G,H verified
    class E attention
```

## Opportunity funnel · actual deadline horizons

This Sankey partitions the 100 dated portfolio records by their remaining calendar horizon; it does not imply historical conversion between recruitment stages.

```mermaid
sankey-beta
Recorded frontier,0-7 days,6
Recorded frontier,8-14 days,20
Recorded frontier,15-30 days,26
Recorded frontier,31-60 days,25
Recorded frontier,61+ days,23
```

<details>
<summary><b>Show the source-provider verification mix</b></summary>

| Provider | Recorded health | Observed leads | New unique leads |
|:--|:--|--:|--:|
| academicpositions | degraded | 0 | 0 |
| academictransfer | degraded | 0 | 0 |
| brave | disabled | 0 | 0 |
| inria | ok | 12 | 0 |

Provider health is not an estimate of search completeness. 3 channels are degraded or disabled.

</details>

## Deadline Gantt · application milestones

```mermaid
gantt
    title Recorded PhD deadlines - snapshot 2026-11-07
    dateFormat YYYY-MM-DD
    axisFormat %b %d
    section Final application deadlines
    N263-03 Karlsruhe Institute of Technology KIT MRT :milestone, d0, 2026-11-08, 0d
    N263-04 University of Copenhagen CoAStaL PhD Cult :milestone, d1, 2026-11-08, 0d
    N263-05 UCL Gatsby Computational Neuroscience Uni :milestone, d2, 2026-11-09, 0d
    N263-06 UCL Sainsbury Wellcome Centre fully funde :milestone, d3, 2026-11-09, 0d
    C06 Swiss Government Excellence Scholarship resea :milestone, d4, 2026-11-10, 0d
    M07a Southampton MSCA BlueOcean PhD Studentship a :milestone, d5, 2026-11-13, 0d
    M15 OIST Graduate School PhD May or Sep 2027 entr :milestone, d6, 2026-11-15, 0d
    M17 Northeastern University London PhD studentshi :milestone, d7, 2026-11-15, 0d
    M18 Institute of Science Tokyo International Grad :milestone, d8, 2026-11-15, 0d
    N263-07 TUM Autonomous Vehicle Systems Johannes B :milestone, d9, 2026-11-15, 0d
    N263-08 TU Delft OPERA EU Project PhD Safe Planni :milestone, d10, 2026-11-15, 0d
```

<details>
<summary><b>Expand the quantitative deadline horizon chart</b></summary>

```mermaid
xychart-beta
    title "Application deadline horizon"
    x-axis ["0-7d", "8-14d", "15-30d", "31-60d", "61+d"]
    y-axis "Application records" 0 --> 30
    bar [6, 20, 26, 25, 23]
```

</details>

## Global opportunities · interactive GitHub map

```geojson
{"type":"FeatureCollection","features":[{"type":"Feature","properties":{"title":"Germany: 4 application records","description":"Country-level aggregate inferred from an unambiguous institution name; pin placed at representative capital city, not at a university","count":4,"sample_source_ids":"N263-03, N263-09, N263-07","marker-color":"#9f61e8","marker-size":"medium"},"geometry":{"type":"Point","coordinates":[13.405,52.52]}},{"type":"Feature","properties":{"title":"United Kingdom: 18 application records","description":"Country-level aggregate inferred from an unambiguous institution name; pin placed at representative capital city, not at a university","count":18,"sample_source_ids":"N263-05, N263-06, M17","marker-color":"#19b5b6","marker-size":"large"},"geometry":{"type":"Point","coordinates":[-0.1276,51.5072]}},{"type":"Feature","properties":{"title":"Netherlands: 8 application records","description":"Country-level aggregate inferred from an unambiguous institution name; pin placed at representative capital city, not at a university","count":8,"sample_source_ids":"N263-10, N263-08, N264-03","marker-color":"#19b5b6","marker-size":"large"},"geometry":{"type":"Point","coordinates":[4.9041,52.3676]}},{"type":"Feature","properties":{"title":"Switzerland: 9 application records","description":"Country-level aggregate inferred from an unambiguous institution name; pin placed at representative capital city, not at a university","count":9,"sample_source_ids":"C06, M23, M24","marker-color":"#19b5b6","marker-size":"large"},"geometry":{"type":"Point","coordinates":[7.4474,46.948]}},{"type":"Feature","properties":{"title":"Norway: 6 application records","description":"Country-level aggregate inferred from an unambiguous institution name; pin placed at representative capital city, not at a university","count":6,"sample_source_ids":"M19, M20, M21","marker-color":"#9f61e8","marker-size":"medium"},"geometry":{"type":"Point","coordinates":[10.7522,59.9139]}},{"type":"Feature","properties":{"title":"Sweden: 2 application records","description":"Country-level aggregate inferred from an unambiguous institution name; pin placed at representative capital city, not at a university","count":2,"sample_source_ids":"N264-07, N264-09","marker-color":"#4384ff","marker-size":"medium"},"geometry":{"type":"Point","coordinates":[18.0632,59.3346]}},{"type":"Feature","properties":{"title":"Denmark: 2 application records","description":"Country-level aggregate inferred from an unambiguous institution name; pin placed at representative capital city, not at a university","count":2,"sample_source_ids":"N263-04, N264-08","marker-color":"#4384ff","marker-size":"medium"},"geometry":{"type":"Point","coordinates":[12.5683,55.6761]}},{"type":"Feature","properties":{"title":"Japan: 6 application records","description":"Country-level aggregate inferred from an unambiguous institution name; pin placed at representative capital city, not at a university","count":6,"sample_source_ids":"M18, M15, C15-NAGOYA","marker-color":"#9f61e8","marker-size":"medium"},"geometry":{"type":"Point","coordinates":[139.6917,35.6895]}},{"type":"Feature","properties":{"title":"Italy: 2 application records","description":"Country-level aggregate inferred from an unambiguous institution name; pin placed at representative capital city, not at a university","count":2,"sample_source_ids":"N264-05, N264-04","marker-color":"#4384ff","marker-size":"medium"},"geometry":{"type":"Point","coordinates":[12.4964,41.9028]}},{"type":"Feature","properties":{"title":"Cyprus: 1 application records","description":"Country-level aggregate inferred from an unambiguous institution name; pin placed at representative capital city, not at a university","count":1,"sample_source_ids":"R26-UCY-SKEYES","marker-color":"#4384ff","marker-size":"medium"},"geometry":{"type":"Point","coordinates":[33.3823,35.1856]}},{"type":"Feature","properties":{"title":"Luxembourg: 1 application records","description":"Country-level aggregate inferred from an unambiguous institution name; pin placed at representative capital city, not at a university","count":1,"sample_source_ids":"M26","marker-color":"#4384ff","marker-size":"medium"},"geometry":{"type":"Point","coordinates":[6.1319,49.6116]}},{"type":"Feature","properties":{"title":"United States: 1 application records","description":"Country-level aggregate inferred from an unambiguous institution name; pin placed at representative capital city, not at a university","count":1,"sample_source_ids":"R26-GWU-EPIC","marker-color":"#4384ff","marker-size":"medium"},"geometry":{"type":"Point","coordinates":[-77.0369,38.9072]}},{"type":"Feature","properties":{"title":"Canada: 8 application records","description":"Country-level aggregate inferred from an unambiguous institution name; pin placed at representative capital city, not at a university","count":8,"sample_source_ids":"M33, M31, M34","marker-color":"#19b5b6","marker-size":"large"},"geometry":{"type":"Point","coordinates":[-75.6972,45.4215]}},{"type":"Feature","properties":{"title":"Australia: 1 application records","description":"Country-level aggregate inferred from an unambiguous institution name; pin placed at representative capital city, not at a university","count":1,"sample_source_ids":"M43a","marker-color":"#4384ff","marker-size":"medium"},"geometry":{"type":"Point","coordinates":[149.13,-35.2809]}}]}
```

**69/100** applications have unambiguous institution-name country matches, aggregated into **14** country markers. The markers are at representative capital locations, **not university campus coordinates**. The remaining 31 records are deliberately excluded from the geographic visualization rather than assigned guessed locations.

<details>
<summary><b>Explore country counts and mapped source IDs</b></summary>

| Country aggregation | Example application IDs |
|:--|:--|
| United Kingdom: 18 application records | N263-05, N263-06, M17 |
| Switzerland: 9 application records | C06, M23, M24 |
| Netherlands: 8 application records | N263-10, N263-08, N264-03 |
| Canada: 8 application records | M33, M31, M34 |
| Norway: 6 application records | M19, M20, M21 |
| Japan: 6 application records | M18, M15, C15-NAGOYA |
| Germany: 4 application records | N263-03, N263-09, N263-07 |
| Sweden: 2 application records | N264-07, N264-09 |
| Denmark: 2 application records | N263-04, N264-08 |
| Italy: 2 application records | N264-05, N264-04 |
| Cyprus: 1 application records | R26-UCY-SKEYES |
| Luxembourg: 1 application records | M26 |
| United States: 1 application records | R26-GWU-EPIC |
| Australia: 1 application records | M43a |

[Complete GeoJSON file](data/readme_opportunities.geojson) · [Source portfolio](data/portfolio_frontier.json)

</details>

## Research & application knowledge graph

This native Mermaid ER diagram represents relationships from the actual application, source-monitor, resource, and research schemas.

```mermaid
erDiagram
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
    }
```

<details>
<summary><b>Agent/tool orchestration · expand Mermaid sequence diagram</b></summary>

```mermaid
sequenceDiagram
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
    Owner->>Store: Confirm applicant actions explicitly
```

</details>

<details>
<summary><b>Application state machine · expand Mermaid states</b></summary>

```mermaid
stateDiagram-v2
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
    Excluded --> [*]
```

The workflow is a **process model**, not confirmation that tracked applications have been submitted.

</details>

## Research focus quadrant

A transparent, data-based proxy: horizontal position is calendar urgency within 90 days, and vertical position is unresolved document mentions plus explicit proof obligations, divided by eight and capped at one. Neither axis is publication impact or admission probability.

```mermaid
quadrantChart
    title Calendar urgency vs unresolved evidence workload
    x-axis Lower urgency --> Higher urgency
    y-axis Lower proof debt --> Higher proof debt
    quadrant-1 Immediate evidence review
    quadrant-2 Build evidence first
    quadrant-3 Monitor
    quadrant-4 Deadline execution
    R01: [0.989, 0.375]
    R02: [0.989, 0.625]
    R03: [0.978, 0.500]
    R04: [0.978, 0.250]
    R05: [0.967, 0.500]
    R06: [0.933, 0.375]
    R07: [0.911, 0.750]
    R08: [0.911, 0.250]
    R09: [0.911, 0.125]
    R10: [0.911, 0.250]
    R11: [0.911, 0.375]
    R12: [0.911, 0.625]
    R13: [0.911, 0.625]
    R14: [0.911, 0.125]
    R15: [0.911, 0.500]
    R16: [0.911, 0.500]
    R17: [0.900, 0.750]
    R18: [0.900, 0.500]
    R19: [0.900, 0.375]
    R20: [0.889, 0.750]
```

[See application records and exact source IDs](data/experience_view.json) · [Open the research radar](data/research_radar.json)

<details>
<summary><b>Research mind map · expand</b></summary>

```mermaid
mindmap
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
        Optimization
```

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
| **1d** | 2026-11-08 | Karlsruhe Institute of Technology (KIT MRT), PhD Efficient Long-Context Models for Vision  | [Source](https://jobs.pse.kit.edu/en/jobs/170920/phd-position-efficient-long-context-large-models-for-vision-and-vision-language-action-systems-fmd) |
| **1d** | 2026-11-08 | University of Copenhagen, CoAStaL PhD Cultural Reasoning with Language Models (CuRe, Danie | [Source](https://employment.ku.dk/phd/?show=167227) |
| **2d** | 2026-11-09 | UCL Gatsby Computational Neuroscience Unit, PhD in Machine Learning and Theoretical Neuros | [Source](https://www.ucl.ac.uk/life-sciences/gatsby/study-and-work/gatsby-unit-phd-programme) |
| **2d** | 2026-11-09 | UCL Sainsbury Wellcome Centre, fully funded PhD in Neural Circuits and Behaviour, 2027 int | [Source](https://www.swc.science/content/apply-our-phd-programme) |
| **3d** | 2026-11-10 | Swiss Government Excellence Scholarship (research/PhD), 2027-2028 | [Source](https://www.sbfi.admin.ch/scholarships_eng) |
| **6d** | 2026-11-13 | Southampton MSCA BlueOcean PhD Studentship, application 1 of 2: staff vacancy ref 3522426D | [Source](https://jobs.soton.ac.uk/Vacancies.aspx?cat=1065&type=10) |
| **8d** | 2026-11-15 | OIST Graduate School PhD, May or Sep 2027 entry (Admissions Workshop 2027) | [Source](https://www.oist.jp/admissions/phd-program/apply-phd) |

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

<sub>EvidenceGraph · Reproducible · Generated from source data · Observation: 2026-11-07. Research papers are not vacancy notices. Unknown document readiness is not confirmed missing documentation. GitHub README renders Mermaid, GeoJSON and linked STL natively; rich JavaScript interactions run in the downloadable browser application.</sub>


<details>
<summary><b>Engineering deep dive · original execution intelligence and source diagnostics</b></summary>

<div align="center">

<a href="../../actions/workflows/experience-lab.yml"><img src="assets/readme/kinetic_cover.svg" width="100%" alt="Animated research intelligence cover with 100 actual future application records on deadline orbits" /></a>

**THIS IS AN EXECUTABLE RESEARCH WORKSPACE, NOT A STATIC TRACKER.**

[**RUN AN INTERACTIVE SCENARIO**](../../actions/workflows/experience-lab.yml) · [**OPERATE SOURCE ALERTS**](../../issues/1) · [**DOWNLOAD ONE-FILE APP**](dashboard/index.html) · [**OPENING GUIDE**](dashboard/README.md) · [**INSPECT RAW EVIDENCE**](data/experience_view.json)

<sub>Regenerated from committed evidence. Snapshot 2026-11-07 · 100 frontier records · 1 source conflict(s). Real actions run through GitHub or the browser application.</sub>

</div>

## Choose a mode · expand and execute

<table><tr>
<td width="33%" valign="top"><details open><summary><b>01 / SIMULATE</b></summary>

Change horizon, lens and hypothetical document readiness; receive computed ranking and downloadable JSON from a GitHub Actions run.

[**Launch workflow inputs**](../../actions/workflows/experience-lab.yml)

</details></td>
<td width="34%" valign="top"><details open><summary><b>02 / INVESTIGATE</b></summary>

Drag evidence nodes, scrub time, tune proof-debt weights, run a command palette and change a local work board.

[**Download executable HTML**](dashboard/index.html) · [Opening instructions](dashboard/README.md)

</details></td>
<td width="33%" valign="top"><details open><summary><b>03 / OPERATE</b></summary>

Prioritize, snooze, acknowledge tasks or explicitly set asset readiness with validated source IDs.

[**Owner commands**](../../issues/1)

</details></td>
</tr></table>

<a href="../../actions/workflows/experience-lab.yml"><img src="assets/readme/kinetic_lane.svg" width="100%" alt="Animated, data-backed source discovery to evidence verification to decision pipeline"/></a>

## Choose your experiment

<details>
<summary><b>Scenario lab / deadlines, proof debt, documents, research</b></summary>

Open [Run workflow](../../actions/workflows/experience-lab.yml), select 7, 14, 30 or 45 days, then choose a deadline, verification, resources or research lens. Optionally enter `academic_cv,research_statement` as hypothetical-ready resources.

The workflow calculates from committed evidence and produces a readable GitHub Actions job summary and JSON artifact. It does not alter application decisions.

</details>

<details>
<summary><b>Temporal graph / drag, zoom, scrub, filter</b></summary>

The [downloadable browser cockpit](dashboard/index.html) supports a draggable and zoomable evidence graph, 0–60-day time travel, explicit review weights, reproducible URLs, CSV/JSON export, keyboard search (Ctrl/Cmd + K), and a local drag-and-drop workspace.

GitHub README rendering cannot execute JavaScript. Download the generated index.html and open it in a browser: the styles, code and snapshot are embedded in a single file.

</details>

<details>
<summary><b>Document dependencies and emerging research</b></summary>

<img src="assets/readme/asset_dependencies.svg" width="100%" alt="Application/document bipartite evidence graph"/>

<table><tr><td width="50%"><img src="assets/readme/proof_matrix.svg" width="100%" alt="Document-mention matrix with explicit states"/></td><td width="50%"><img src="assets/readme/research_constellation.svg" width="100%" alt="Research-title co-occurrence; papers are not vacancies"/></td></tr></table>

Edges encode recorded mentions, not guessed document absence or admission probability.

</details>

<details>
<summary><b>Deadline terrain and discovery source assurance</b></summary>

<table><tr><td width="60%"><img src="assets/readme/isometric_calendar.svg" width="100%" alt="Actual six-week deadline density"/></td><td width="40%"><img src="assets/readme/deadline_orbits.svg" width="100%" alt="Time-distance deadline orbits"/></td></tr></table>

<img src="assets/readme/source_signals.svg" width="100%" alt="Provider health including degraded and disabled search channels"/>

[Monitor observations](data/latest_run.json) · [Discovery diagnostics](data/discovery_report.json) · [Portfolio frontier](data/portfolio_frontier.json) · [Provenance JSON-LD](data/experience_lineage.jsonld)

</details>

## Upcoming records · observation 2026-11-07

| Horizon | Date | Application | Primary source |
|:--|:--|:--|:--|
| **1d** | 2026-11-08 | Karlsruhe Institute of Technology (KIT MRT), PhD Efficient Long-Context Models for Vision and Vision-Language- | [Evidence](https://jobs.pse.kit.edu/en/jobs/170920/phd-position-efficient-long-context-large-models-for-vision-and-vision-language-action-systems-fmd) |
| **1d** | 2026-11-08 | University of Copenhagen, CoAStaL PhD Cultural Reasoning with Language Models (CuRe, Daniel Hershcovich) | [Evidence](https://employment.ku.dk/phd/?show=167227) |
| **2d** | 2026-11-09 | UCL Gatsby Computational Neuroscience Unit, PhD in Machine Learning and Theoretical Neuroscience, 2027 | [Evidence](https://www.ucl.ac.uk/life-sciences/gatsby/study-and-work/gatsby-unit-phd-programme) |
| **2d** | 2026-11-09 | UCL Sainsbury Wellcome Centre, fully funded PhD in Neural Circuits and Behaviour, 2027 intake | [Evidence](https://www.swc.science/content/apply-our-phd-programme) |
| **3d** | 2026-11-10 | Swiss Government Excellence Scholarship (research/PhD), 2027-2028 | [Evidence](https://www.sbfi.admin.ch/scholarships_eng) |
| **6d** | 2026-11-13 | Southampton MSCA BlueOcean PhD Studentship, application 1 of 2: staff vacancy ref 3522426DA (jobs.soton.ac.uk) | [Evidence](https://jobs.soton.ac.uk/Vacancies.aspx?cat=1065&type=10) |
| **8d** | 2026-11-15 | BMW AI Robotics / RoboTac and TU/e Eindhoven, PhD World Models &amp; Visuo-Tactile Foundation Models (2 research t | [Evidence](https://www.robotac.eu/open-positions) |
| **8d** | 2026-11-15 | Institute of Science Tokyo, International Graduate Program IGP(A) Fall 2027 with MEXT recommendation | [Evidence](https://admissions.isct.ac.jp/en/013/graduate/programs/igp/igp-a) |

[Complete action agenda](docs/TODAY.md) · [Workbook](PhD_Action_List.xlsx) · [Calendar feed](calendar/phd_deadlines.ics)

<details>
<summary><b>Reproduce, verify and operate the system</b></summary>

Submission deadlines and preparation tasks are different. A source assertion is not proof of eligibility. A document mention is not evidence that it is missing. A research paper is not an open funded PhD position. Hypothetical readiness is not recorded applicant status.

[Architecture](docs/ARCHITECTURE.md) · [Capability atlas](docs/CAPABILITY_ATLAS.md) · [Playbooks](docs/PLAYBOOKS.md) · [Source correction](../../issues/new?template=01-source-correction.yml) · [New opportunity intake](../../issues/new?template=02-opportunity-lead.yml) · [Propose an experiment](../../issues/new?template=03-automation-idea.yml)

These are working combinations of existing interaction methods; no unverified claim of globally unprecedented invention is made.

</details>


<div align="center">

**EVIDENCEGRAPH · PhD APPLICATION INTELLIGENCE**

*Every deadline is dated. Every uncertainty is visible. Every decision links to evidence.*

[![Discovery & Reconciliation](https://github.com/Armanasq/phd_tracker/actions/workflows/phd-intelligence.yml/badge.svg)](../../actions/workflows/phd-intelligence.yml)
[![Regression & Data Contracts](https://github.com/Armanasq/phd_tracker/actions/workflows/intelligence-ci.yml/badge.svg)](../../actions/workflows/intelligence-ci.yml)
[![Full Workbook Audit](https://github.com/Armanasq/phd_tracker/actions/workflows/audit-workbook.yml/badge.svg)](../../actions/workflows/audit-workbook.yml)

[**APPLICATION WORKSPACE**](PhD_Action_List.xlsx) · [**DEADLINE OPERATIONS**](docs/TODAY.md) · [**BROWSER FLIGHT DECK**](dashboard/README.md) · [**SOURCE PROVENANCE**](data/experience_lineage.jsonld) · [**OWNER COMMANDS**](../../issues/1)

</div>

### Navigate the command center

[**01 · Act now**](#01--execute--2026-11-07) · [**02 · Decide next**](#02--next-decisions-not-just-a-countdown) · [**03 · Verify sources**](#03--evidence-backed-search-and-auditability) · [**04 · Data model**](#04--all-worksheets-participate) · [**05 · Controls**](#05--github-as-a-private-operating-interface) · [**06 · Engineering**](#06--research-contributions-not-cosmetic-features)

| Priority | Immediate route | Outcome |
|:--|:--|:--|
| **Submit / verify** | [Review today's scheduled tasks](docs/TODAY.md) | Prevent missing a final deadline; confirm portal status and submission receipts |
| **Plan the workload** | [Today's execution plan](docs/TODAY.md) | Separate actual application deadlines from supporting steps and shared tasks |
| **Resolve uncertainty** | [Review proof obligations](data/portfolio_frontier.json) | Identify funding restrictions, portal contradictions, and missing evidence |
| **Explore opportunities** | [Discovery inbox](data/discovered_candidates.json) | Evaluate new leads before any promotion into the application list |
| **Operate reminders** | [Private Action Center](../../issues/1) | Mark tasks done, explicitly declare asset readiness, or snooze noncritical alerts |

#### Live operational signals (committed snapshot)

| Time critical | Source assurance | Applicant decisions | Research horizon |
|:--|:--|:--|:--|
| **5** deadline(s) in ≤3 days; **6** in the next 7 days | **1/4** active providers reporting healthy; **3** degraded/disabled | **0** dated steps today; **113** older steps with *completion unknown* | **34** indexed papers, research signals only |
| [Review every dated task](docs/TODAY.md) | [Source diagnostics](data/discovery_report.json) | [Confirm task status](../../issues/1) | [Research radar](data/research_radar.json) |

**Source consistency:** 6 observations across 6 configured monitors; 4 matched expected anchors and 2 require review. **Degraded sources:** academicpositions, academictransfer, brave.

<sub>Last official-page monitor: 2026-11-07 · last discovery: 2026-11-07 · last publication radar: 2026-11-07. These are observed snapshots, not live counters or a guarantee that any position is still accepting applicants.</sub>

> [!IMPORTANT]
> **Observed snapshot: 2026-11-07 (Europe/Berlin).** Application deadlines, step dates and shared tasks are different data types. A task dated in the past is **completion-unconfirmed**, not automatically unfinished. Original verdicts are research assessments, not confirmed submission receipts. Primary sources determine final eligibility and deadlines.

<a href="docs/TODAY.md"><img src="assets/readme/operations.svg" width="100%" alt="Today: distinct application deadlines, scheduled preparation steps, shared tasks and completion-unknown backlog" /></a>

## Explore EvidenceGraph by outcome

<a href="docs/CAPABILITY_ATLAS.md"><img src="assets/readme/evidence_flow.svg" alt="Four-stage research-to-decision system: discovery, verification, portfolio prioritization, and owner-confirmed execution" width="100%" /></a>

<table>
<tr>
<td width="33%" valign="top">

### Find a doctoral position

**Discover → verify → shortlist**

[Research queue](data/discovered_candidates.json) · [Search diagnostics](data/discovery_report.json)

Identify original institutional postings, duplicate URLs, uncertain eligibility, source failures and deadline contradictions. Never confuse a research paper with an open funded position.

</td>
<td width="33%" valign="top">

### Execute an application

**Plan → prepare → submit**

[Today's action plan](docs/TODAY.md) · [Portfolio frontier](data/portfolio_frontier.json)

Separate actual final deadlines from preparation steps, identify reusable materials and explicitly confirm statuses. An unknown task or asset state is not automatically classified as incomplete.

</td>
<td width="34%" valign="top">

### Operate the intelligence system

**Monitor → alert → improve**

[Private Action Center](../../issues/1) · [Live workflow](../../actions/workflows/phd-intelligence.yml)

Review source conflicts, snooze or prioritize individual applications and inspect coverage. Gmail and external alerts require configured credentials.

</td>
</tr>
</table>

| Want to... | Open this surface |
|:--|:--|
| Understand every available capability and its maturity | [Capability atlas — operational, conditional, degraded, proposed](docs/CAPABILITY_ATLAS.md) |
| Follow a complete real-world operating procedure | [Nine scenario playbooks](docs/PLAYBOOKS.md) |
| Report a changed deadline or closed portal | [Structured source correction](../../issues/new?template=01-source-correction.yml) |
| Submit a new PhD lead for human verification | [Structured opportunity intake](../../issues/new?template=02-opportunity-lead.yml) |
| Propose an experiment with metrics and rollback | [Automation experiment form](../../issues/new?template=03-automation-idea.yml) |
| Compare engineering intent with actual implementation | [System architecture](docs/ARCHITECTURE.md) · [Product RFC](docs/PRODUCT_RFC.md) |
| Inspect tests, provider failures and data lineage | [Regression CI](../../actions/workflows/intelligence-ci.yml) · [Evidence diagnostics](data/discovery_report.json) |

> [!NOTE]
> **Capability transparency:** Inria discovery and private GitHub reminders are operating. AcademicPositions is currently blocked (HTTP 403), AcademicTransfer has zero observed records, and Brave search requires an API key. External notifications, Gmail polling and Google Sheets synchronization are not claimed to be active without their respective configuration. The operational snapshot above is dated and must not be interpreted as real-time eligibility proof.

## 01 · Execute — 2026-11-07

### Submission deadlines today — 0 actionable · 0 explicitly excluded

| When | Application / workstream | Action | Source |
|:--|:--|:--|:--|
| — | None in the current snapshot | — | — |

### Cross-route work — 0 scheduled today

| Date | Cross-application task | Recorded status |
|:---|:---|:---|
| — | None scheduled today | — |

**Programme-specific steps due today** — 0 distinct records from the *Step timeline* worksheet, not inferred from the final submission date.

| When | Application / workstream | Action | Source |
|:--|:--|:--|:--|
| — | None in the current snapshot | — | — |

<details>
<summary><b>Show every scheduled task today, the unconfirmed backlog, and exclusion reasons</b></summary>

The full execution queue preserves original worksheet row numbers and source IDs. No completion status is invented for the Step timeline.

[Open full, source-linked agenda](docs/TODAY.md) · [Inspect machine-readable plan](data/execution_plan.json) · [Open editable Task ledger](PhD_Action_List.xlsx)

**Not actionable today**

No exclusions on this date.

**Earlier dates with completion unconfirmed:** 113 tasks. 12 are cross-route tasks and 101 are programme timeline steps. They are **not automatically treated as outstanding** until the user confirms progress.

</details>

<a href="docs/TODAY.md"><img src="assets/readme/lanes.svg" width="100%" alt="Source-aware composition of today's task workload" /></a>

## 02 · Next decisions, not just a countdown

**Application deadlines during the next seven days (6)**

| When | Application / workstream | Action | Source |
|:--|:--|:--|:--|
| 2026-11-08 | Karlsruhe Institute of Technology (KIT MRT), PhD Efficient Long-Context Models for Vision and Vision-Language-Action, 1252/20 | Apply through official KIT job portal by 8 Nov. Emphasize transformer efficiency, long-context VLM inference and edge deployment. | [Source page](https://jobs.pse.kit.edu/en/jobs/170920/phd-position-efficient-long-context-large-models-for-vision-and-vision-language-action-systems-fmd) · Action list · row 33 |
| 2026-11-08 | University of Copenhagen, CoAStaL PhD Cultural Reasoning with Language Models (CuRe, Daniel Hershcovich) | Submit by 8 Nov 23:59 CET. Connect RAG evidence verification and multilingual evaluation to cultural uncertainty, not generic LLM product work. | [Source page](https://employment.ku.dk/phd/?show=167227) · Action list · row 34 |
| 2026-11-09 | UCL Gatsby Computational Neuroscience Unit, PhD in Machine Learning and Theoretical Neuroscience, 2027 | Submit Gatsby 2027 portal application before 9 Nov 17:00 GMT; academic references by 10 Nov 23:59 GMT. Joint SWC track available as preference, not a separate application. | [Source page](https://www.ucl.ac.uk/life-sciences/gatsby/study-and-work/gatsby-unit-phd-programme) · Action list · row 35 |
| 2026-11-09 | UCL Sainsbury Wellcome Centre, fully funded PhD in Neural Circuits and Behaviour, 2027 intake | Apply by 9 Nov 17:00 GMT if pursuing neural circuits; optional joint Gatsby–SWC via this OR Gatsby application, not independently. | [Source page](https://www.swc.science/content/apply-our-phd-programme) · Action list · row 36 |
| 2026-11-10 | Swiss Government Excellence Scholarship (research/PhD), 2027-2028 | By 29 Oct 2026: email sgs@sbfi.admin.ch asking Iran's scholarship type and deadline and whether an Iranian resident in Turkey applies via Tehran or Ankara route | [Source page](https://www.sbfi.admin.ch/scholarships_eng) · Action list · row 37 |
| 2026-11-13 | Southampton MSCA BlueOcean PhD Studentship, application 1 of 2: staff vacancy ref 3522426DA (jobs.soton.ac.uk) | By 13 Nov 23:59 UK time: submit BlueOcean MSCA staff vacancy ref 3522426DA via jobs.soton.ac.uk. Also confirm and complete any separate PhD/project registration (linked form timing not verified). | [Source page](https://jobs.soton.ac.uk/Vacancies.aspx?cat=1065&type=10) · Action list · row 38 |

| Operating surface | Open | Decision supported |
|:--|:--|:--|
| **Execution board** | [Workbook](PhD_Action_List.xlsx) | Due tasks separated by source, date, eligibility and status |
| **Full Task ledger** | [Workbook](PhD_Action_List.xlsx) | Every application deadline and every programme/shared task with provenance |
| **Calendar reminders** | [Download ICS](calendar/phd_deadlines.ics) | Import all-day reminders for future tasks and deadlines; reimport when the workbook changes |
| **Deadline and proof obligations** | [Decision frontier](data/portfolio_frontier.json) | Funding/eligibility contradictions and reusable-document dependencies |
| **Review queue** | [Research queue](data/discovered_candidates.json) | Search leads needing official source confirmation |
| **Live notifications** | [Private Action Center](../../issues/1) | Reminder history, conflicts and owner controls |
| **Academic trajectory** | [Research radar](data/research_radar.json) | Relevant papers for research positioning, not jobs |

## 03 · Evidence-backed search and auditability

<div align="center">
<a href="data/discovery_report.json"><img src="assets/readme/providers.svg" width="45%" alt="Collector health, new unique opportunities and disabled sources" /></a>
<a href="assets/readme/horizon.svg"><img src="assets/readme/horizon.svg" width="53%" alt="Application deadline distribution" /></a>
</div>

| Search provider | Health | Observed | New unique |
|:--|:--|--:|--:|
| academicpositions | degraded | 0 | 0 |
| academictransfer | degraded | 0 | 0 |
| brave | disabled | 0 | 0 |
| inria | ok | 12 | 0 |

- **Contradictory source observations:** 2 monitor finding(s). A published programme deadline is not proof that an application portal is accepting submissions.
- **Research records:** 34 scholarly articles indexed separately, not counted as available PhD placements.
- **Discovery scope:** without configured Brave credentials, international web search is **disabled**. A healthy workflow cannot imply exhaustive worldwide coverage.

<details>
<summary><b>Research claims, exclusions and source integrity</b></summary>

The original *Dropped* and *Not added* tabs retain **6 dropped routes** and **200 researched-but-not-added routes**. They are an evidence base for explaining omissions, not proof that those programmes are permanently unsuitable.

The automated research queue contains 27 rows. Review both university vacancy records and eligibility/funding requirements before promoting a result to the main list. Historical exclusions have **0 possible reappearance warning(s)**, which require manual review rather than automatic rejection.

[Source provenance](data/latest_run.json) · [Discovery report](data/discovery_report.json) · [Historical exclusion memory](data/exclusion_memory.json) · [Rejected and unadded decisions](PhD_Action_List.xlsx) · [Detailed methodology](docs/PRODUCT_RFC.md)

</details>

## 04 · All worksheets participate

The system is not limited to the deadline column. These sheets are retained in the repository workbook and have distinct operational roles.

| Worksheet | Role in the workflow |
|:--|:--|
| **Read me** | Original tracker documentation, eligibility and verdict rules |
| **Action list** | Master application records, verdicts, dates, funding, blockers and links |
| **Step timeline** | Dated programme-specific preparation and submission tasks |
| **What I need to do** | Cross-route checklist and user-maintained task statuses |
| **Dropped** | Rejected or inaccessible routes with source-specific reasons |
| **Not added** | Investigated leads deliberately excluded from the main list |
| **Research queue** | Discovered leads awaiting funding, eligibility and deadline review |
| **Mail signals** | Evidence extracted from personally reviewed recruitment correspondence |
| **Evidence ledger** | Source, observation date and proof of claims |
| **Source watch** | Website change and contradictory portal monitoring |
| **Decision frontier** | Application readiness uncertainty, proof debt and reusable assets |
| **Research radar** | Related publications only, never misclassified as vacancies |
| **Execution board** | Prioritized view of scheduled submissions and preparation tasks |
| **Task ledger** | Every dated programme task and original worksheet row, not just deadlines |
| **Exclusion memory** | Historical dropped and not-added evidence; reappearing leads are flagged, never silently rejected |

**Original workbook coverage:** 183 applications · 559 dated/programme-specific steps · 26 shared tasks · 6 dropped routes · 200 researched but unadded.

The generated **Execution board** and **Task ledger** can be filtered or edited locally. Derived sheets are regenerated; original source sheets and status cells are protected by integrity tests.

## 05 · GitHub as a private operating interface

<details open>
<summary><b>Owner-only interactive commands</b></summary>

Comment on [PhD Intelligence — Action Center](../../issues/1):

```text
/priority N263-02
/snooze N263-02 3d
/unsnooze N263-02
/mute N263-02
/unmute N263-02
/asset academic_cv ready
/asset research_statement in_progress
/asset transcripts unknown
/done tsk-<copy-task-id-from-daily-agenda>
/reopen tsk-<copy-task-id-from-daily-agenda>
```

Commands are validated against the repository owner, known source IDs, allowed states and stable task IDs. Use a real `tsk-...` identifier printed beside each programme/shared task in the agenda; `/done` and `/reopen` update a private completion overlay, regenerate the workbook/README and never alter original submission states. Comments are idempotent by ID and acknowledged after successful commits. Same-day and next-day deadlines cannot be muted.

**Resource readiness is never inferred from advertised requirements.** Update it explicitly, or retain the default `unknown`.

</details>

<details>
<summary><b>Advanced automation, integrations and scheduling</b></summary>

| Workflow | Trigger | Produces |
|:--|:--|:--|
| [Intelligence pipeline](.github/workflows/phd-intelligence.yml) | Twice daily and manually | Discovery, evidence reconciliation, workbook, README and notifications |
| [Workbook audit](.github/workflows/audit-workbook.yml) | Workbook-auditor changes or manually | Cross-tab inventory and date integrity |
| [Security and regression CI](.github/workflows/intelligence-ci.yml) | Code changes | Parser, deadline, snapshot and interaction tests |
| [Private issue commands](.github/workflows/issue-controls.yml) | Owner-created Issue comment | Priority, snooze, mute or explicit resource status |
| [Manual fallback](.github/workflows/refresh-tracker.yml) | On demand | Evidence-watch refresh |

Optional secrets are `BRAVE_SEARCH_API_KEY` (broad discovery), `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET` and `GMAIL_REFRESH_TOKEN` (read-only email metadata), and `APPRISE_URLS` (external notifications). Without them, the corresponding capabilities are disabled rather than simulated.

</details>

<details>
<summary><b>System design, data lineage and state transitions</b></summary>

```mermaid
flowchart TD
    A["University vacancy sources"] --> C["Canonical identity & assertion ledger"]
    B["Optional broad research + Gmail metadata"] --> C
    X["arXiv research papers"] --> Y["Research context only"]
    C --> QPrimary evidence and eligibility verified?
    Q -->|"No"| R["Research queue + proof debt"]
    Q -->|"Yes, after review"| E["Excel Action list"]
    E --> T["Step timeline · dated tasks"]
    E --> D["Deadlines · applicant status"]
    G["What I need to do"] --> O["Full task planner"]
    T --> O
    D --> O
    H["Dropped / Not added"] --> O
    O --> U["Execution board + Task ledger"]
    O --> N["Action Center + deduplicated reminders"]
    Y --> N
    N --> V["Explicit owner commands"]
    V --> O
```

The engine cannot submit applications, invent funding eligibility, silently change a user decision, or execute arbitrary commands from third-party search content. Data merges are re-evaluated against current `main` to avoid binary workbook conflicts.

</details>

## From a GitHub repository to an operating system

<details>
<summary><b>Use case A — an application closes today</b></summary>

**Deadline → application portal → explicit verification → preparation steps → receipt.** Start with [today's execution plan](docs/TODAY.md), inspect the primary source, verify the time zone, and submit directly to the university. The system records a deadline and tasks; it **does not** confirm that the application was submitted. Only a portal receipt or your explicit decision can establish that state.

</details>

<details>
<summary><b>Use case B — a recruiting lab publishes a contradictory deadline</b></summary>

**Evidence comparison → proof debt → human resolution.** The [source monitor](data/latest_run.json) checks observed institutional assertions. A closed application portal does not automatically overwrite an advertised deadline; the contradiction appears in the [decision frontier](data/portfolio_frontier.json) and the [Action Center](../../issues/1).

</details>

<details>
<summary><b>Use case C — a single document is needed for multiple applications</b></summary>

**Reusable document → explicit readiness → deadline dependency.** Review [document leverage](data/portfolio_frontier.json) and set your real state in the [Action Center](../../issues/1), for example `/asset research_statement in_progress`. Mentions of a CV, statement, or transcript in vacancy text are **not** proof that you lack the document.

</details>

<details>
<summary><b>Use case D — find a lab before an official vacancy exists</b></summary>

The [research radar](data/research_radar.json) monitors topical publications in robotics, vision, medical AI and related areas. Research papers provide context for prospective supervisors and SOP positioning; they are **not** interpreted as funded openings. The [discovery pipeline](.github/workflows/phd-intelligence.yml) independently monitors actual vacancies, with source limitations disclosed.

</details>

### Delivery truth table

| Capability | Current implementation | Trust boundary |
|:--|:--|:--|
| Scheduled search | Twice-daily matrix of institutional/marketplace connectors | A source may fail, block crawlers, or return no results |
| Deadline-driven execution | Separate final deadlines, programme steps and shared tasks | Past completion is unknown unless explicitly recorded |
| Opportunity reconciliation | Canonical URL deduplication, source history and review queue | Search snippets never prove funding or eligibility |
| Repository notifications | Owner-assigned Issue and threshold-based reminders | Notification delivery outside GitHub needs an opt-in endpoint |
| Interactive commands | Owner-scoped task, asset and alert controls | Neither a GitHub comment nor a scraped page executes arbitrary shell commands |
| Email intelligence | Existing reviewed signals; optional OAuth metadata intake | Gmail automation requires separately configured read-only credentials |
| Research radar | arXiv publications displayed apart from vacancy records | Papers do not establish a recruiting PhD position |
| Workbook integrity | Cross-sheet audit, regression CI and conflict-safe publication | The original cloud Google Sheet is not live-synced |
| Commercial roadmap | [EvidenceGraph product RFC](docs/PRODUCT_RFC.md) | Novelty, predictive quality, and revenue have **not** been established experimentally |

## 06 · Research contributions, not cosmetic features

1. **Temporal evidence and contradictions:** retain competing source assertions and review deadline changes.
2. **Multi-clock scheduling:** distinguish final application deadlines, preparation steps, shared deadlines, and overdue-completion uncertainty.
3. **Proof debt:** expose unknown eligibility/funding/document requirements without converting unknown to false.
4. **Reusable asset leverage:** reveal which confirmed document-readiness decisions may unblock multiple applications.
5. **Human-in-the-loop control:** per-application notifications with an auditable, owner-operated GitHub Issue.
6. **Coverage observability:** measure distinct discovery yield and explicit source outages rather than claiming world-scale recall.

[Product and engineering RFC](docs/PRODUCT_RFC.md) · [Technical architecture](docs/ARCHITECTURE.md) · [All tests](tests/) · [Operations checklist](docs/TODAY.md)

---

<sub><b>Generated:</b> 2026-11-07. Charts are static SVG snapshots regenerated by GitHub Actions; GitHub READMEs cannot run React or arbitrary JavaScript. This project combines known techniques in source monitoring and orchestration; uniqueness and commercial viability require independent evaluation, not branding claims.</sub>


</details>
