from __future__ import annotations

import argparse
import html
import json
import re
from datetime import date, datetime
from pathlib import Path

if __package__:
    from .experience_engine import generate as generate_experience, markdown as experience_markdown
    from .readme_studio import generate as generate_readme_studio
else:
    from experience_engine import generate as generate_experience, markdown as experience_markdown
    from readme_studio import generate as generate_readme_studio
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ASSETS = ROOT / "assets" / "readme"
DOCS = ROOT / "docs"
DEEP_NAV = {
    "Read me": "Original tracker documentation, eligibility and verdict rules",
    "Action list": "Master application records, verdicts, dates, funding, blockers and links",
    "Step timeline": "Dated programme-specific preparation and submission tasks",
    "What I need to do": "Cross-route checklist and user-maintained task statuses",
    "Dropped": "Rejected or inaccessible routes with source-specific reasons",
    "Not added": "Investigated leads deliberately excluded from the main list",
    "Research queue": "Discovered leads awaiting funding, eligibility and deadline review",
    "Mail signals": "Evidence extracted from personally reviewed recruitment correspondence",
    "Evidence ledger": "Source, observation date and proof of claims",
    "Source watch": "Website change and contradictory portal monitoring",
    "Decision frontier": "Application readiness uncertainty, proof debt and reusable assets",
    "Research radar": "Related publications only, never misclassified as vacancies",
    "Execution board": "Prioritized view of scheduled submissions and preparation tasks",
    "Task ledger": "Every dated programme task and original worksheet row, not just deadlines",
    "Exclusion memory": "Historical dropped and not-added evidence; reappearing leads are flagged, never silently rejected",
    "Mail inbox": "Optional read-only Gmail metadata, if OAuth secrets are configured",
}


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def plain(text: object, limit=150):
    return re.sub(r"\s+", " ", str(text or "")).strip()[:limit]


def md(text: object, limit=160):
    return (plain(text, limit).replace("\\", "\\\\")
            .replace("|", "\\|").replace("<", "&lt;").replace(">", "&gt;")
            .replace("[", "\\[").replace("]", "\\]"))


def url(text: object):
    value=plain(text, 500)
    if not value.startswith("https://") or not urlsplit(value).hostname:
        return ""
    return value.replace("(", "%28").replace(")", "%29")


def source_link(record, caption="Source page"):
    loc=url(record.get("source"))
    return f"[{caption}]({loc})" if loc else "No verified link"


def svg(text, title, width=1200, height=420):
    return ('<svg xmlns="http://www.w3.org/2000/svg" width="{}" height="{}" '
            'viewBox="0 0 {} {}" role="img" aria-label="{}">'
            '<title>{}</title><defs>'
            '<linearGradient id="bg" x1="0" x2="1" y1="0" y2="1"><stop stop-color="#071729"/>'
            '<stop offset="1" stop-color="#17344D"/></linearGradient>'
            '</defs><rect width="{}" height="{}" fill="url(#bg)" rx="20"/>{}</svg>').format(
             width,height,width,height,html.escape(title,quote=True),
             html.escape(title),width,height,text)


def text(x,y,message,size=18,color="#EAF2FB",weight=400,anchor="start"):
    return ('<text x="{}" y="{}" font-family="Inter,Segoe UI,Arial,sans-serif" '
            'font-size="{}" fill="{}" font-weight="{}" text-anchor="{}">{}</text>').format(
                x,y,size,color,weight,anchor,html.escape(str(message)))


def rect(x,y,w,h,color="#162E44",stroke="#33516B",radius=15):
    return ('<rect x="{}" y="{}" width="{}" height="{}" rx="{}" '
            'fill="{}" stroke="{}"/>').format(x,y,w,h,radius,color,stroke)


def operations_svg(plan):
    today=plan["today"]["counts"]
    bar=[text(42,51,"TODAY  /  EVIDENCE-AWARE EXECUTION",16,"#70E1CE",700),
         text(1150,51,plan["as_of"]+"  •  Europe/Berlin",14,"#ABC4DB",500,"end"),
         text(42,107,"Applications are deadlines. Tasks are a separate clock.",28,"#F3FAFF",700),
         text(42,141,"Every figure below is traced to the original Excel rows.",16,"#A8BCD2")]
    values=[
      ("SUBMISSIONS TODAY",today["deadline_actions"],"Action list · eligible/unsubmitted","#71E3CE"),
      ("TIMELINE STEPS",today["timeline_tasks"],"Step timeline · due today","#9DC8FF"),
      ("SHARED TASKS",today["shared_tasks"],"What I need to do · due today","#FFC682"),
      ("PAST / UNCONFIRMED",plan["overdue_or_unconfirmed"]["total"],"Needs completion-status review","#F6A1AB"),
    ]
    for i,(label,value,note,color) in enumerate(values):
        x=40+i*286
        bar += [rect(x,177,268,130),text(x+18,207,label,13,"#AAC1D3",700),
                text(x+18,266,value,44,color,700),
                text(x+18,291,note,12,"#B2C4D6")]
    bar += [rect(40,330,1126,54,"#10283C","#315B6D",12),
            text(60,364,"SOURCE EXCLUSIONS",14,"#EEC88E",700),
            text(365,364,str(today["excluded_deadlines"])+
                 " deadline record(s) excluded by their Not eligible / closed status",15,"#EAF2FB")]
    return svg("".join(bar),"Actual due-today deadlines versus tasks, overdue status unknown",1206,418)


def lanes_svg(plan):
    t=plan["today"]["counts"]
    data=[("Application submissions",t["deadline_actions"],"#70E1CE"),
          ("Scheduled timeline tasks",t["timeline_tasks"],"#9DC8FF"),
          ("Cross-route tasks",t["shared_tasks"],"#FFCA8C"),
          ("Excluded / not actionable",t["excluded_deadlines"],"#EA8E9C")]
    mx=max(1,*[x[1] for x in data])
    bits=[text(30,44,"TODAY'S WORKLOAD • BY SOURCE",18,"#F4FAFF",700),
          text(30,71,"Counts reflect independent task dates; final deadlines are not double counted.",13,"#ABC4DB")]
    for i,(label,n,c) in enumerate(data):
        y=111+70*i
        width=round(580*n/mx)
        bits += [text(30,y+11,label,15,"#EAF2FB",500),
                 rect(364,y-8,580,23,"#173148","#173148",6),
                 rect(364,y-8,max(4,width),23,c,c,6) if n else "",
                 text(966,y+10,n,15,"#F4FAFF",700,"end")]
    return svg("".join(bits),"Workload composition based on real workbook",1010,430)


def task_table(items,max_rows=None,link=True):
    lines=["| When | Application / workstream | Action | Source |",
           "|:--|:--|:--|:--|"]
    for r in (items if max_rows is None else items[:max_rows]):
        due=md(r.get("due") or "Unknown",20)
        name=md(r.get("name") or r.get("source_id"),125)
        act=md(r.get("action"),210)
        if r.get("task_id") and r.get("type") in ("timeline_step","cross_route_task"):
            act += " · " + chr(96) + md(r["task_id"],24) + chr(96)
        provenance=md(r.get("sheet") or "Unknown sheet",30)+" · row "+str(r.get("row") or "?")
        route=(source_link(r) + " · " + provenance if link else provenance)
        lines.append(f"| {due} | {name} | {act} | {route} |")
    if len(lines)==2:
        lines.append("| — | None in the current snapshot | — | — |")
    return "\n".join(lines)


def share_table(items,max_rows=None):
    lines=["| Date | Cross-application task | Recorded status |",
           "|:---|:---|:---|"]
    for r in (items if max_rows is None else items[:max_rows]):
        control = (" · "+chr(96)+md(r["task_id"],24)+chr(96)) if r.get("task_id") else ""
        lines.append(f'| {md(r.get("due"),16)} | {md(r.get("action"),260)}{control} | {md(r.get("verdict"),30)} |')
    if len(lines)==2:
        lines.append("| — | None scheduled today | — |")
    return "\n".join(lines)


def dashboard_md(plan, metrics, experience_block=""):
    day=plan["as_of"]
    today=plan["today"]
    near=plan["upcoming_7_day_deadlines"]
    all_today=today["scheduled_timeline_tasks"]
    due_today=today["eligible_application_deadlines"]
    shared=today["cross_route_tasks"]
    overdue=plan["overdue_or_unconfirmed"]
    counts=today["counts"]
    conflict=metrics.get("contradictions",0)
    inventory=plan["inventory"]
    exclusion=metrics.get("exclusion_memory", {})
    source_rows=[]
    for k,v in sorted(metrics.get("providers",{}).items()):
        source_rows.append(f'| {md(k)} | {md(v.get("health","unknown"))} | {v.get("observed",0)} | {v.get("new_unique",0)} |')
    if not source_rows:
        source_rows=["| No source status | unknown | — | — |"]
    sheet_rows=[]
    for name in plan.get("source_tabs",[]):
        desc=DEEP_NAV.get(name,"Additional workbook content")
        sheet_rows.append(f"| **{md(name)}** | {md(desc,170)} |")
    rejected_today=today["excluded_application_deadlines"]
    exclusions=("\n".join(f"- **{md(r['name'],110)}** — {md(r['verdict'])}; {md(r.get('notes',''),150)}"
                         for r in rejected_today)) or "No exclusions on this date."
    source_health=metrics.get("providers",{})
    provider_ok=sum(1 for x in source_health.values() if x.get("health")=="ok")
    provider_bad=sum(1 for x in source_health.values() if x.get("health") in ("degraded","disabled"))
    last_run=load(ROOT/"data"/"latest_run.json")
    last_research=load(ROOT/"data"/"discovery_report.json")
    mail_signals=load(ROOT/"data"/"mail_signals.json")
    radar=load(ROOT/"data"/"research_radar_report.json")
    radar_count=len(load(ROOT/"data"/"research_radar.json").get("papers",[]))
    watched=last_run.get("source_watches",len(last_run.get("source_statuses",[])))
    verified_sources=sum(1 for x in last_run.get("source_statuses",[]) if x.get("status")=="anchor_present")
    deadline_count=len(near)
    urgent_count=sum(1 for x in near if x.get("days") is not None and x["days"]<=3)
    bad_names=", ".join(md(n,32) for n,v in sorted(source_health.items()) if v.get("health")!="ok") or "None reported"
    first_today=due_today[0] if due_today else None
    launch_action=(f'[Open today’s {counts["deadline_actions"]} application deadline(s)](docs/TODAY.md)' if due_today else "[Review today's scheduled tasks](docs/TODAY.md)")
    freshness=(f'Last official-page monitor: {md(last_run.get("date","unknown"))} · '
               f'last discovery: {md(last_research.get("run_date","unknown"))} · '
               f'last publication radar: {md(radar.get("as_of","unknown"))}')
    return f"""{experience_block}

<div align="center">

**EVIDENCEGRAPH · PhD APPLICATION INTELLIGENCE**

*Every deadline is dated. Every uncertainty is visible. Every decision links to evidence.*

[![Discovery & Reconciliation](https://github.com/Armanasq/phd_tracker/actions/workflows/phd-intelligence.yml/badge.svg)](../../actions/workflows/phd-intelligence.yml)
[![Regression & Data Contracts](https://github.com/Armanasq/phd_tracker/actions/workflows/intelligence-ci.yml/badge.svg)](../../actions/workflows/intelligence-ci.yml)
[![Full Workbook Audit](https://github.com/Armanasq/phd_tracker/actions/workflows/audit-workbook.yml/badge.svg)](../../actions/workflows/audit-workbook.yml)

[**APPLICATION WORKSPACE**](PhD_Action_List.xlsx) · [**DEADLINE OPERATIONS**](docs/TODAY.md) · [**BROWSER FLIGHT DECK**](dashboard/README.md) · [**SOURCE PROVENANCE**](data/experience_lineage.jsonld) · [**OWNER COMMANDS**](../../issues/1)

</div>

### Navigate the command center

[**01 · Act now**](#01--execute--{day}) · [**02 · Decide next**](#02--next-decisions-not-just-a-countdown) · [**03 · Verify sources**](#03--evidence-backed-search-and-auditability) · [**04 · Data model**](#04--all-worksheets-participate) · [**05 · Controls**](#05--github-as-a-private-operating-interface) · [**06 · Engineering**](#06--research-contributions-not-cosmetic-features)

| Priority | Immediate route | Outcome |
|:--|:--|:--|
| **Submit / verify** | {launch_action} | Prevent missing a final deadline; confirm portal status and submission receipts |
| **Plan the workload** | [Today's execution plan](docs/TODAY.md) | Separate actual application deadlines from supporting steps and shared tasks |
| **Resolve uncertainty** | [Review proof obligations](data/portfolio_frontier.json) | Identify funding restrictions, portal contradictions, and missing evidence |
| **Explore opportunities** | [Discovery inbox](data/discovered_candidates.json) | Evaluate new leads before any promotion into the application list |
| **Operate reminders** | [Private Action Center](../../issues/1) | Mark tasks done, explicitly declare asset readiness, or snooze noncritical alerts |

#### Live operational signals (committed snapshot)

| Time critical | Source assurance | Applicant decisions | Research horizon |
|:--|:--|:--|:--|
| **{urgent_count}** deadline(s) in ≤3 days; **{deadline_count}** in the next 7 days | **{provider_ok}/{len(source_health)}** active providers reporting healthy; **{provider_bad}** degraded/disabled | **{counts["timeline_tasks"]}** dated steps today; **{overdue["total"]}** older steps with *completion unknown* | **{radar_count}** indexed papers, research signals only |
| [Review every dated task](docs/TODAY.md) | [Source diagnostics](data/discovery_report.json) | [Confirm task status](../../issues/1) | [Research radar](data/research_radar.json) |

**Source consistency:** {len(last_run.get("source_statuses",[]))} observations across {watched} configured monitors; {verified_sources} matched expected anchors and {conflict} require review. **Degraded sources:** {bad_names}.

<sub>{freshness}. These are observed snapshots, not live counters or a guarantee that any position is still accepting applicants.</sub>

> [!IMPORTANT]
> **Observed snapshot: {day} (Europe/Berlin).** Application deadlines, step dates and shared tasks are different data types. A task dated in the past is **completion-unconfirmed**, not automatically unfinished. Original verdicts are research assessments, not confirmed submission receipts. Primary sources determine final eligibility and deadlines.

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

## 01 · Execute — {day}

### Submission deadlines today — {counts["deadline_actions"]} actionable · {counts["excluded_deadlines"]} explicitly excluded

{task_table(due_today)}

### Cross-route work — {counts["shared_tasks"]} scheduled today

{share_table(shared,max_rows=5)}

**Programme-specific steps due today** — {counts["timeline_tasks"]} distinct records from the *Step timeline* worksheet, not inferred from the final submission date.

{task_table(all_today,max_rows=12)}

<details>
<summary><b>Show every scheduled task today, the unconfirmed backlog, and exclusion reasons</b></summary>

The full execution queue preserves original worksheet row numbers and source IDs. No completion status is invented for the Step timeline.

[Open full, source-linked agenda](docs/TODAY.md) · [Inspect machine-readable plan](data/execution_plan.json) · [Open editable Task ledger](PhD_Action_List.xlsx)

**Not actionable today**

{exclusions}

**Earlier dates with completion unconfirmed:** {overdue["total"]} tasks. {overdue["cross_route"]} are cross-route tasks and {overdue["timeline"]} are programme timeline steps. They are **not automatically treated as outstanding** until the user confirms progress.

</details>

<a href="docs/TODAY.md"><img src="assets/readme/lanes.svg" width="100%" alt="Source-aware composition of today's task workload" /></a>

## 02 · Next decisions, not just a countdown

**Application deadlines during the next seven days ({len(near)})**

{task_table(near,max_rows=18)}

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
{chr(10).join(source_rows)}

- **Contradictory source observations:** {conflict} monitor finding(s). A published programme deadline is not proof that an application portal is accepting submissions.
- **Research records:** {radar_count} scholarly articles indexed separately, not counted as available PhD placements.
- **Discovery scope:** without configured Brave credentials, international web search is **disabled**. A healthy workflow cannot imply exhaustive worldwide coverage.

<details>
<summary><b>Research claims, exclusions and source integrity</b></summary>

The original *Dropped* and *Not added* tabs retain **{inventory["dropped_routes"]} dropped routes** and **{inventory["not_added_routes"]} researched-but-not-added routes**. They are an evidence base for explaining omissions, not proof that those programmes are permanently unsuitable.

The automated research queue contains {inventory["research_queue_rows"]} rows. Review both university vacancy records and eligibility/funding requirements before promoting a result to the main list. Historical exclusions have **{len(exclusion.get("potential_reappearances", []))} possible reappearance warning(s)**, which require manual review rather than automatic rejection.

[Source provenance](data/latest_run.json) · [Discovery report](data/discovery_report.json) · [Historical exclusion memory](data/exclusion_memory.json) · [Rejected and unadded decisions](PhD_Action_List.xlsx) · [Detailed methodology](docs/PRODUCT_RFC.md)

</details>

## 04 · All worksheets participate

The system is not limited to the deadline column. These sheets are retained in the repository workbook and have distinct operational roles.

| Worksheet | Role in the workflow |
|:--|:--|
{chr(10).join(sheet_rows)}

**Original workbook coverage:** {inventory["application_rows"]} applications · {inventory["timeline_steps"]} dated/programme-specific steps · {inventory["cross_route_tasks"]} shared tasks · {inventory["dropped_routes"]} dropped routes · {inventory["not_added_routes"]} researched but unadded.

The generated **Execution board** and **Task ledger** can be filtered or edited locally. Derived sheets are regenerated; original source sheets and status cells are protected by integrity tests.

## 05 · GitHub as a private operating interface

<details open>
<summary><b>Owner-only interactive commands</b></summary>

Comment on [PhD Intelligence — Action Center](../../issues/1):

§§§text
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
§§§

Commands are validated against the repository owner, known source IDs, allowed states and stable task IDs. Use a real `tsk-...` identifier printed beside each programme/shared task in the agenda; `/done` and `/reopen` update a private completion overlay, regenerate the workbook/README and never alter original submission states. Comments are idempotent by ID and acknowledged after successful commits. Same-day and next-day deadlines cannot be muted.

**Resource readiness is never inferred from advertised requirements.** Update it explicitly, or retain the default §unknown§.

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

Optional secrets are §BRAVE_SEARCH_API_KEY§ (broad discovery), §GMAIL_CLIENT_ID§, §GMAIL_CLIENT_SECRET§ and §GMAIL_REFRESH_TOKEN§ (read-only email metadata), and §APPRISE_URLS§ (external notifications). Without them, the corresponding capabilities are disabled rather than simulated.

</details>

<details>
<summary><b>System design, data lineage and state transitions</b></summary>

§§§mermaid
flowchart TD
    A["University vacancy sources"] --> C["Canonical identity & assertion ledger"]
    B["Optional broad research + Gmail metadata"] --> C
    X["arXiv research papers"] --> Y["Research context only"]
    C --> Q{"Primary evidence and eligibility verified?"}
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
§§§

The engine cannot submit applications, invent funding eligibility, silently change a user decision, or execute arbitrary commands from third-party search content. Data merges are re-evaluated against current §main§ to avoid binary workbook conflicts.

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

**Reusable document → explicit readiness → deadline dependency.** Review [document leverage](data/portfolio_frontier.json) and set your real state in the [Action Center](../../issues/1), for example §/asset research_statement in_progress§. Mentions of a CV, statement, or transcript in vacancy text are **not** proof that you lack the document.

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

<sub><b>Generated:</b> {day}. Charts are static SVG snapshots regenerated by GitHub Actions; GitHub READMEs cannot run React or arbitrary JavaScript. This project combines known techniques in source monitoring and orchestration; uniqueness and commercial viability require independent evaluation, not branding claims.</sub>
""".replace("§",chr(96))


def todays_md(plan,metrics):
    day=plan["as_of"]
    a=plan["today"]
    c=a["counts"]
    near=plan["upcoming_7_day_deadlines"]
    overdue=plan["overdue_or_unconfirmed"]
    doc=f"""# Execution plan — {day}

[← Repository cockpit](../README.md) · [Tracker workbook](../PhD_Action_List.xlsx) · [Import task calendar](../calendar/phd_deadlines.ics) · [Private Action Center](../../issues/1) · [Full machine-readable ledger](../data/execution_plan.json)

> **As of {day}, Europe/Berlin.** This plan is generated from original workbook rows. It distinguishes application deadlines from step dates and explicit cross-route tasks. A dated Step timeline task has no recorded completion flag; it is not automatically labelled incomplete.

## A. Application submission deadlines today ({c["deadline_actions"]})

{task_table(a["eligible_application_deadlines"])}

## B. Shared actions due today ({c["shared_tasks"]})

{share_table(a["cross_route_tasks"])}

## C. All programme steps explicitly dated today ({c["timeline_tasks"]})

To confirm a task, copy its stable `tsk-...` identifier from the table and comment `/done TASK_ID` on the [private Action Center](../../issues/1). Use `/reopen TASK_ID` to undo. These commands update a separate completion ledger, not the original source rows.

{task_table(a["scheduled_timeline_tasks"])}

## D. Application deadlines within seven days ({len(near)})

{task_table(near)}

## E. Earlier tasks, completion status unconfirmed

There are **{overdue["total"]}** pre-{day} tasks with no confirmed completion status and whose final application deadline has not definitively passed, including **{overdue["timeline"]}** programme steps and **{overdue["cross_route"]}** cross-route tasks. These represent *review work*, not automatic missed deadlines.

{task_table(overdue["highest_priority_sample"],max_rows=35,link=False)}

## F. Earlier steps linked to today's final deadlines

The following earlier preparation steps are **not** additional November 6 submission deadlines:

{task_table(a["linked_past_steps_with_final_deadline_today"])}

## G. Explicitly excluded application deadlines today

{task_table(a["excluded_application_deadlines"])}

## H. Evidence policy and next actions

- Verify the actual institutional closing time/time zone in each original posting before submitting.
- Check whether an application or preparation task was already completed; nothing in the Step timeline proves it remains undone.
- Preserve the user-maintained statuses in *What I need to do*. No third-party email or scraped vacancy changes them. Calendar events are all-day reminders unless the original source is manually confirmed; this private-repository file is a snapshot, not a continuously updating subscription.
- MEXT routes may be mutually exclusive. The main workbook records this in the original grouping rule.
- Review [source contradictions](../data/latest_run.json) and [readiness unknowns](../data/portfolio_frontier.json).
- For source reconciliation, see [full workbook audit](../data/workbook_audit.json).

*Generated automatically from the complete workbook, not synthesized from a search snippet.*
"""
    return doc


def render(root=ROOT):
    plan=load(root/"data"/"execution_plan.json")
    if not plan or "today" not in plan:
        raise ValueError("Missing full-workbook execution plan; refusing incomplete README generation")
    metrics=load(root/"assets"/"readme"/"metrics.json")
    if not metrics:
        raise ValueError("Missing README source metrics")
    metrics["exclusion_memory"]=load(root/"data"/"exclusion_memory.json")
    if (root/"data"/"portfolio_frontier.json").is_file():
        generate_experience(root)
    assets=root/"assets"/"readme"
    docs=root/"docs"
    assets.mkdir(parents=True,exist_ok=True)
    docs.mkdir(parents=True,exist_ok=True)
    (assets/"operations.svg").write_text(operations_svg(plan),encoding="utf-8")
    (assets/"lanes.svg").write_text(lanes_svg(plan),encoding="utf-8")
    view_path=root/"data"/"experience_view.json"
    experience_block=experience_markdown(load(view_path)) if view_path.is_file() else ""
    legacy=dashboard_md(plan,metrics,experience_block)
    if view_path.is_file():
        studio=generate_readme_studio(root,load(view_path),plan)
        readme=(studio+"\n\n<details>\n<summary><b>Engineering deep dive · original execution intelligence and source diagnostics</b></summary>\n\n"
                +legacy+"\n\n</details>\n")
    else:
        readme=legacy
    (root/"README.md").write_text(readme,encoding="utf-8")
    (docs/"TODAY.md").write_text(todays_md(plan,metrics),encoding="utf-8")
    output={
      "rendered_as_of":plan["as_of"],
      "task_counts":plan["today"]["counts"],
      "source_tabs":len(plan["source_tabs"]),
      "full_agenda_file":"docs/TODAY.md",
      "svg_assets":["operations.svg","lanes.svg","hero.svg","providers.svg","horizon.svg"],
    }
    (assets/"command_center_metrics.json").write_text(json.dumps(output,indent=2)+"\n",encoding="utf-8")
    return output


if __name__=="__main__":
    p=argparse.ArgumentParser()
    p.add_argument("--root",default=str(ROOT))
    args=p.parse_args()
    print(json.dumps(render(Path(args.root)),ensure_ascii=False))
