from __future__ import annotations

import argparse
import html
import json
import math
from collections import Counter
from datetime import date
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
PALETTE = {
    "background": "#071522",
    "panel": "#102638",
    "line": "#315169",
    "text": "#EAF5FA",
    "muted": "#98B6C8",
    "mint": "#5CE0C1",
    "amber": "#FFCB8B",
    "rose": "#FA92AB",
    "blue": "#92B9FF",
}


def read_json(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(f"Required intelligence artifact missing: {path}")
    obj = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(obj, dict):
        raise ValueError(f"Expected JSON object: {path}")
    return obj


def safe_url(value: object) -> str:
    if not isinstance(value, str):
        return ""
    p = urlsplit(value.strip())
    return value.strip() if p.scheme == "https" and p.hostname else ""



def operational_insights(applications: list[dict], observations: list[dict]) -> dict:
    future = [a for a in applications if a["days"] >= 0]
    by_day: dict[str, list[dict]] = {}
    for a in future:
        by_day.setdefault(a["deadline"], []).append(a)
    collisions = [{
        "date": deadline,
        "applications": [{"id": a["id"], "name": a["name"]} for a in items],
        "count": len(items),
    } for deadline, items in sorted(by_day.items()) if len(items) >= 2]
    known = {a["id"]: a for a in applications}
    anomalies = []
    for observed in observations:
        if not isinstance(observed, dict):
            continue
        status = str(observed.get("status", "unknown"))
        if status not in {"review_source_changed", "contradiction_closed_portal"}:
            continue
        app_id = str(observed.get("application_id", observed.get("id", "")))
        app = known.get(app_id)
        anomalies.append({
            "observation_id": str(observed.get("id", "")),
            "application_id": app_id,
            "application_name": app["name"] if app else "Not linked to a recorded frontier application",
            "status": status,
            "expected_deadline": str(observed.get("expected_deadline", "")),
            "source": safe_url(observed.get("source_url")),
            "is_linked": app is not None,
        })
    verification_queue = []
    for app in future:
        reasons = []
        if app["proof_obligations"]:
            reasons.append(f'{len(app["proof_obligations"])} source/evidence obligations')
        if app["unknown_documents"]:
            reasons.append(f'{len(app["unknown_documents"])} mentioned documents with unknown readiness')
        if not reasons:
            continue
        verification_queue.append({
            "id": app["id"], "name": app["name"], "deadline": app["deadline"],
            "days": app["days"], "reasons": reasons, "source": app["source"],
        })
    verification_queue.sort(key=lambda a: (a["days"], -len(a["reasons"]), a["name"]))
    return {
        "deadline_collisions": collisions,
        "source_anomalies": anomalies,
        "verification_queue": verification_queue[:50],
        "policy": "Priorities are calendar-sorted review candidates, not admission likelihood, guaranteed eligibility or inferred incomplete tasks.",
    }


def make_view(root: Path) -> dict:
    plan = read_json(root / "data/execution_plan.json")
    frontier = read_json(root / "data/portfolio_frontier.json")
    assets = read_json(root / "data/application_assets.json")
    discovery = read_json(root / "data/discovery_report.json")
    radar = read_json(root / "data/research_radar.json")
    monitor = read_json(root / "data/latest_run.json")
    observed = date.fromisoformat(plan["as_of"])
    if date.fromisoformat(frontier["as_of"]) != observed:
        raise ValueError("Frontier and execution plan snapshots disagree; do not publish a mixed-date dashboard")
    resource_states = assets.get("resources", {})
    resources = []
    for item in frontier.get("resource_frontier", []):
        rid = str(item["resource_id"])
        configured = resource_states.get(rid, {})
        state = str(configured.get("status", item.get("current_state", "unknown")))
        if state not in {"unknown", "ready", "in_progress", "not_started", "not_applicable"}:
            raise ValueError(f"Unsupported resource state {rid}: {state}")
        resources.append({
            "id": rid, "label": str(item.get("label", rid))[:100], "state": state,
            "potential": int(item.get("potential_applications", 0)),
            "near_term": int(item.get("near_term_applications", 0)),
        })
    resource_ids = {r["id"] for r in resources}
    applications = []
    seen = set()
    for item in frontier.get("applications", []):
        source_id = str(item.get("source_id", "")).strip()
        if not source_id or source_id in seen:
            raise ValueError(f"Missing or duplicate application ID: {source_id}")
        seen.add(source_id)
        deadline = date.fromisoformat(str(item["deadline"])[:10])
        mentions = sorted(set(str(x) for x in item.get("document_mentions", []) if str(x) in resource_ids))
        proof = [str(x)[:240] for x in item.get("evidence_proof_obligations", [])]
        applications.append({
            "id": source_id,
            "name": str(item.get("opportunity", source_id))[:200],
            "deadline": deadline.isoformat(),
            "days": (deadline - observed).days,
            "decision": str(item.get("decision", "unknown"))[:100],
            "readiness": str(item.get("readiness", "unknown"))[:100],
            "documents": mentions,
            "unknown_documents": sorted(x for x in mentions if resource_states.get(x, {}).get("status", "unknown") == "unknown"),
            "proof_obligations": proof,
            "source": safe_url(item.get("source_url")),
            "next_step": str(item.get("next_step", ""))[:500],
        })
    applications.sort(key=lambda r: (r["days"], r["name"]))
    source_yield = discovery.get("source_yield", {})
    providers = []
    for name, row in sorted(source_yield.items()):
        providers.append({
            "name": str(name), "health": str(row.get("health", "unknown")),
            "observed": int(row.get("observed", 0)),
            "new_unique": int(row.get("new_unique", 0)),
        })
    statuses = monitor.get("source_statuses", [])
    source_checks = Counter(str(x.get("status", "unknown")) for x in statuses if isinstance(x, dict))
    clocks = {
        "submission_deadlines": [],
        "preparation_steps": [],
        "shared_tasks": [],
    }
    for kind, key in [
        ("submission_deadlines", "eligible_application_deadlines"),
        ("preparation_steps", "scheduled_timeline_tasks"),
        ("shared_tasks", "cross_route_tasks"),
    ]:
        for item in plan.get("today", {}).get(key, []):
            clocks[kind].append({
                "id": str(item.get("task_id", "")),
                "source_id": str(item.get("source_id", "")),
                "name": str(item.get("name", item.get("action", "")))[:220],
                "action": str(item.get("action", ""))[:450],
                "due": str(item.get("due", plan["as_of"]))[:10],
                "state": str(item.get("state", "completion_unconfirmed"))[:60],
                "source": safe_url(item.get("source")),
            })
    papers = [{
        "title": str(p.get("title", ""))[:230],
        "id": str(p.get("id", ""))[:80],
        "url": safe_url(p.get("url", "")),
        "published": str(p.get("published", ""))[:24],
    } for p in radar.get("papers", []) if isinstance(p, dict)][:40]
    return {
        "schema_version": 1,
        "as_of": observed.isoformat(),
        "timezone": str(plan.get("timezone", "Europe/Berlin")),
        "policy": "Observed snapshot, not live availability. Unknown is not false. Document mention does not imply missing. Simulations never change application state.",
        "metrics": {
            "tracked": len(applications),
            "future": sum(a["days"] >= 0 for a in applications),
            "next_seven_days": sum(0 <= a["days"] <= 7 for a in applications),
            "unknown_document_mentions": sum(len(a["unknown_documents"]) for a in applications if a["days"] >= 0),
            "source_conflicts": int(frontier.get("source_conflict_count", 0)),
            "research_papers": len(radar.get("papers", [])),
        },
        "applications": applications,
        "resources": resources,
        "providers": providers,
        "source_checks": dict(source_checks),
        "research": papers,
        "clocks": clocks,
        "insights": operational_insights(applications, statuses),
    }


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def svg_document(title: str, width: int, height: int, parts: list[str]) -> str:
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" '
            f'viewBox="0 0 {width} {height}" role="img" aria-label="{esc(title)}">'
            f'<title>{esc(title)}</title><rect width="{width}" height="{height}" '
            f'rx="24" fill="{PALETTE["background"]}"/>'
            + "".join(parts) + "</svg>\n")


def label(x: float, y: float, value: object, size: int = 17, color: str = "#EAF5FA", weight: int = 400, anchor: str = "start") -> str:
    return (f'<text x="{x:.1f}" y="{y:.1f}" font-family="Inter,Arial,sans-serif" '
            f'font-size="{size}" fill="{color}" font-weight="{weight}" '
            f'text-anchor="{anchor}">{esc(value)}</text>')


def rect(x: float, y: float, w: float, h: float, fill: str, radius: int = 12, stroke: str = "#315169") -> str:
    return (f'<rect x="{x:.1f}" y="{y:.1f}" width="{max(0,w):.1f}" height="{max(0,h):.1f}" '
            f'rx="{radius}" fill="{fill}" stroke="{stroke}"/>')


def hero_svg(view: dict) -> str:
    parts = [
        label(44, 48, "E V I D E N C E G R A P H   /   EXPERIENCE LAB", 15, PALETTE["mint"], 700),
        label(1150, 48, f'SNAPSHOT {view["as_of"]}', 14, PALETTE["muted"], 500, "end"),
        label(44, 111, "Research decisions, with inspectable evidence.", 36, PALETTE["text"], 700),
        label(44, 150, "Dual clocks  /  proof-debt simulation  /  discovery assurance  /  research context", 16, PALETTE["muted"]),
    ]
    metrics = view["metrics"]
    values = [
        ("APPLICATION RECORDS", metrics["tracked"], PALETTE["text"]),
        ("UPCOMING 7 DAYS", metrics["next_seven_days"], PALETTE["amber"]),
        ("UNKNOWN DOC MENTIONS", metrics["unknown_document_mentions"], PALETTE["blue"]),
        ("SOURCE CONFLICTS", metrics["source_conflicts"], PALETTE["rose"]),
    ]
    for i, (heading, number, color) in enumerate(values):
        x = 44 + i * 290
        parts.extend([rect(x, 184, 272, 120, PALETTE["panel"]),
                      label(x + 18, 214, heading, 12, PALETTE["muted"], 700),
                      label(x + 18, 270, number, 41, color, 700)])
    parts += [label(44, 342, "Verification is not eligibility. Deadlines are not completion receipts.", 14, PALETTE["muted"])]
    return svg_document("EvidenceGraph application command center with traceable snapshot indicators", 1200, 368, parts)


def orbit_svg(view: dict) -> str:
    apps = [a for a in view["applications"] if 0 <= a["days"] <= 30]
    parts = [label(42, 45, "DEADLINE ORBITS", 22, PALETTE["text"], 700),
             label(42, 72, "One node per application / radial distance is calendar time, not probability", 13, PALETTE["muted"])]
    cx, cy = 600, 240
    for radius, caption in [(70,"0-3d"), (130,"4-7d"), (190,"8-14d"), (250,"15-30d")]:
        parts.append(f'<circle cx="{cx}" cy="{cy}" r="{radius}" fill="none" stroke="{PALETTE["line"]}" stroke-dasharray="5 8"/>')
        parts.append(label(cx + radius + 8, cy + 4, caption, 11, PALETTE["muted"]))
    for i, a in enumerate(apps[:75]):
        days = a["days"]
        radius = 70 if days <= 3 else 130 if days <= 7 else 190 if days <= 14 else 250
        phase = 2 * math.pi * ((i * 0.61803398875) % 1)
        x = cx + radius * math.cos(phase)
        y = cy + radius * math.sin(phase)
        color = PALETTE["rose"] if days <= 3 else PALETTE["amber"] if days <= 7 else PALETTE["mint"]
        parts.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5.4" fill="{color}"><title>{esc(a["name"])} / {esc(a["deadline"])}</title></circle>')
    parts.extend([f'<circle cx="{cx}" cy="{cy}" r="32" fill="{PALETTE["mint"]}" opacity=".15"/>',
                  label(cx,cy+4,"NOW",14,PALETTE["mint"],700,"middle"),
                  label(42, 511, f'{len(apps)} dated applications within 30 days (first 75 displayed) · {view["as_of"]}', 13, PALETTE["muted"])])
    return svg_document("Calendar-based deadline orbits", 1200, 534, parts)



def isometric_calendar_svg(view: dict) -> str:
    from datetime import timedelta
    origin = date.fromisoformat(view["as_of"])
    deadline_counts = Counter(a["deadline"] for a in view["applications"] if 0 <= a["days"] < 42)
    parts = [
        label(32, 46, "SIX-WEEK DEADLINE TERRAIN", 21, PALETTE["text"], 700),
        label(32, 72, "Height = applications sharing a deadline; zero is an empty date, not a failed application", 13, PALETTE["muted"]),
    ]
    for week in range(6):
        for weekday in range(7):
            observed = origin + timedelta(days=week*7+weekday)
            n = deadline_counts.get(observed.isoformat(), 0)
            x = 175 + weekday*110 - week*24
            y = 132 + week*42 + weekday*15
            rise = min(65, n*15)
            color = PALETTE["rose"] if n >= 3 else PALETTE["amber"] if n >= 2 else PALETTE["mint"] if n else PALETTE["panel"]
            pts = f"{x},{y} {x+56},{y+11} {x+33},{y+29} {x-23},{y+18}"
            if rise:
                side = f"{x+56},{y+11-rise} {x+56},{y+11} {x+33},{y+29} {x+33},{y+29-rise}"
                front = f"{x-23},{y+18-rise} {x+33},{y+29-rise} {x+33},{y+29} {x-23},{y+18}"
                parts.append(f'<polygon points="{side}" fill="#285469" stroke="{PALETTE["line"]}"/>')
                parts.append(f'<polygon points="{front}" fill="#214657" stroke="{PALETTE["line"]}"/>')
                pts=f"{x},{y-rise} {x+56},{y+11-rise} {x+33},{y+29-rise} {x-23},{y+18-rise}"
            parts.append(f'<polygon points="{pts}" fill="{color}" stroke="{PALETTE["line"]}"><title>{observed.isoformat()}: {n} recorded application deadline(s)</title></polygon>')
            if n:
                parts.append(label(x+17,y+18-rise,n,13,PALETTE["background"],700,"middle"))
    parts.append(label(32, 464, "Each tile = one calendar day; historical status and completion remain unconfirmed unless recorded.", 12, PALETTE["muted"]))
    return svg_document("Isometric calendar of actual application-deadline density over six weeks", 1120, 487, parts)


def dependency_svg(view: dict) -> str:
    applications=[a for a in view["applications"] if 0 <= a["days"] <= 14][:13]
    resources=view["resources"][:6]
    parts=[
        label(28, 42, "REUSABLE ASSET DEPENDENCIES", 21, PALETTE["text"], 700),
        label(28, 68, "Graph edges mean a document is mentioned in an application. They do not mean it is missing.", 12, PALETTE["muted"]),
    ]
    left_x,right_x=250,840
    for i,r in enumerate(resources):
        y=124+i*56
        parts.append(rect(25,y-21,230,39,PALETTE["panel"]))
        parts.append(label(37,y+3,r["label"][:30],12,PALETTE["text"],600))
    for i,a in enumerate(applications):
        y=102+i*37
        parts.append(rect(840,y-17,335,30,PALETTE["panel"]))
        parts.append(label(850,y+3,a["name"][:46],10,PALETTE["text"]))
        for j,r in enumerate(resources):
            if r["id"] in a["documents"]:
                ry=124+j*56
                parts.append(f'<path d="M {left_x} {ry} C 475 {ry},615 {y}, {right_x} {y}" fill="none" stroke="{PALETTE["amber"] if r["state"]=="unknown" else PALETTE["mint"]}" stroke-opacity=".39" stroke-width="1.7"/>')
    parts.append(label(25,612,"Amber = unknown document readiness · Mint = explicit other readiness · No edge does not prove a document is unnecessary",11,PALETTE["muted"]))
    return svg_document("Bipartite graph of document mentions across near-term opportunities",1200,635,parts)


def research_map_svg(view: dict) -> str:
    themes=[
        ("Robot autonomy",("robot","navigation","manipulation","action","vla")),
        ("SLAM & estimation",("slam","localization","inertial","loop closure","mapping")),
        ("Vision & 3D",("vision","visual","3d","camera","segmentation","image")),
        ("Clinical imaging",("medical","pathology","clinical","diagnos","ultrasound")),
        ("Learning systems",("learning","language","neural","model","transformer")),
    ]
    papers=view["research"]
    sets=[set(p["id"] for p in papers if any(token in p["title"].lower() for token in words)) for _,words in themes]
    parts=[label(28,44,"RESEARCH TERM CONSTELLATION",20,PALETTE["text"],700),
           label(28,70,"Links represent co-occurrence of title terms in indexed papers, not verified supervisor relationships",12,PALETTE["muted"])]
    locations=[(122,200),(355,140),(593,230),(845,135),(1050,235)]
    for i in range(len(locations)):
        for j in range(i+1,len(locations)):
            overlap=len(sets[i]&sets[j])
            if overlap:
                xa,ya=locations[i];xb,yb=locations[j]
                parts.append(f'<line x1="{xa}" y1="{ya}" x2="{xb}" y2="{yb}" stroke="{PALETTE["blue"]}" stroke-width="{min(11,1+overlap)}" stroke-opacity=".25"/>')
    for i,(name,_) in enumerate(themes):
        x,y=locations[i]
        parts.append(f'<circle cx="{x}" cy="{y}" r="{min(56,23+len(sets[i])*1.5)}" fill="{PALETTE["panel"]}" stroke="{PALETTE["mint"]}" stroke-width="2"/>')
        parts.append(label(x,y+6,len(sets[i]),22,PALETTE["mint"],700,"middle"))
        parts.append(label(x,y+85,name,13,PALETTE["text"],600,"middle"))
    parts.append(label(28,345,f'{len(papers)} indexed research records in this observed snapshot; title-term grouping is heuristic.',12,PALETTE["muted"]))
    return svg_document("Research title-term co-occurrence network",1200,366,parts)


def proof_svg(view: dict) -> str:
    apps = [a for a in view["applications"] if a["days"] >= 0][:17]
    resources = view["resources"][:7]
    width = 1180
    height = max(235, 134 + len(apps) * 26)
    parts = [label(24, 38, "PROOF-DEBT MATRIX", 20, PALETTE["text"], 700),
             label(24, 64, "A marked square means the document is mentioned, not that it is missing", 13, PALETTE["muted"])]
    for j,r in enumerate(resources):
        parts.append(label(580+j*83, 99, r["id"][:10], 9, PALETTE["muted"], 600))
    for i,a in enumerate(apps):
        y = 120+i*26
        parts.append(label(24, y+11, a["name"][:69], 10, PALETTE["text"]))
        for j,r in enumerate(resources):
            fill = (PALETTE["mint"] if r["state"]=="ready" else PALETTE["amber"] if r["state"]=="unknown" else PALETTE["blue"]) if r["id"] in a["documents"] else PALETTE["panel"]
            parts.append(rect(578+j*83, y, 48, 16, fill, 4, PALETTE["line"]))
    parts.append(label(24,height-19, "Amber = mentioned / status unknown     Mint = confirmed ready     Blue = other explicit state", 11, PALETTE["muted"]))
    return svg_document("Evidence and document-readiness matrix",width,height,parts)


def providers_svg(view: dict) -> str:
    providers = view["providers"]
    parts = [label(28, 43, "DISCOVERY SIGNAL HEALTH", 19, PALETTE["text"], 700),
             label(28, 69, "Observed source yields / unknown collection coverage is never zero risk", 12, PALETTE["muted"])]
    for i,p in enumerate(providers):
        y = 92 + i*57
        parts += [rect(24,y,680,48,PALETTE["panel"]),
                  label(39,y+30,p["name"][:32],14,PALETTE["text"],600),
                  label(388,y+30,f'{p["observed"]} observed · {p["new_unique"]} new',12,PALETTE["muted"]),
                  label(686,y+30,p["health"].upper(),12,
                        PALETTE["mint"] if p["health"]=="ok" else PALETTE["rose"],700,"end")]
    if not providers:
        parts.append(label(28,125,"No observed provider health available",14,PALETTE["amber"]))
    return svg_document("Source discovery status and observed yield",730,117+max(1,len(providers))*57,parts)


def resource_svg(view: dict) -> str:
    resources = view["resources"][:8]
    parts=[label(30,43,"DOCUMENT LEVERAGE",20,PALETTE["text"],700),
           label(30,68,"Potential application associations; not confirmed unblocked submissions",12,PALETTE["muted"])]
    max_value = max(1, *(r["potential"] for r in resources))
    for i,r in enumerate(resources):
        y=92+i*57
        parts += [label(32,y+14,r["label"][:36],13,PALETTE["text"]),
                  rect(355,y,585,18,PALETTE["panel"],5),
                  rect(355,y,585*r["potential"]/max_value,18,PALETTE["mint"],5),
                  label(965,y+14,r["potential"],13,PALETTE["text"],700),
                  label(1050,y+14,r["state"],12,PALETTE["muted"])]
    return svg_document("Reusable document associations and explicit readiness",1140,122+max(1,len(resources))*57,parts)


def make_gif(view: dict, target: Path) -> None:
    from PIL import Image, ImageDraw, ImageFont
    stages = [
        ("01 / OBSERVE", "Institutional sources and discovered leads", sum(p["observed"] for p in view["providers"])),
        ("02 / RESOLVE", "Stable identities and source evidence", view["metrics"]["tracked"]),
        ("03 / VERIFY", "Source contradictions need review", view["metrics"]["source_conflicts"]),
        ("04 / ACT", "Applications with deadlines within seven days", view["metrics"]["next_seven_days"]),
    ]
    font = ImageFont.load_default()
    frames = []
    for active in range(4):
        img = Image.new("RGB", (900,170), (7,21,34))
        draw = ImageDraw.Draw(img)
        draw.text((25,18),"EVIDENCEGRAPH / OBSERVED PIPELINE",font=font,fill=(93,224,193))
        for j, (name, detail, value) in enumerate(stages):
            x=24+j*220
            fill=(40,100,103) if active==j else (17,38,56)
            draw.rounded_rectangle((x,50,x+207,143),radius=12,fill=fill,outline=(49,81,105),width=2)
            draw.text((x+12,69),name,font=font,fill=(235,246,251))
            draw.text((x+12,98),f"Observed: {value}",font=font,fill=(255,203,139) if j==active else (156,184,201))
        draw.text((24,152),stages[active][1][:105],font=font,fill=(156,184,201))
        frames.append(img)
    frames[0].save(target,format="GIF",save_all=True,append_images=frames[1:],duration=[1100]*4,loop=0,optimize=True)


def markdown(view: dict) -> str:
    return f"""## Research intelligence · observed {esc(view["as_of"])}

<div align="center">

<a href="dashboard/README.md"><img src="assets/readme/evidence_pipeline.gif" width="100%" alt="Animated four-stage research intelligence pipeline showing observed source discovery, reconciliation, verification and upcoming applications"/></a>

**RESEARCH → EVIDENCE → DECISION → EXECUTION**

[Explore private interactive dashboard](dashboard/README.md) · [Inspect evidence JSON](data/experience_view.json) · [Explore W3C-style provenance graph](data/experience_lineage.jsonld)

</div>

<table>
<tr>
<td width="60%" valign="top"><a href="docs/TODAY.md"><img src="assets/readme/isometric_calendar.svg" width="100%" alt="Six-week isometric calendar: application deadline density by date" /></a></td>
<td width="40%" valign="top"><a href="data/portfolio_frontier.json"><img src="assets/readme/deadline_orbits.svg" width="100%" alt="Deadline orbits: every near-term application shown according to days remaining"/></a></td>
</tr>
<tr>
<td><a href="data/research_radar.json"><img src="assets/readme/research_constellation.svg" width="100%" alt="Research-paper title-term co-occurrence; publications are not openings"/></a></td>
<td><a href="data/discovery_report.json"><img src="assets/readme/source_signals.svg" width="100%" alt="Observed crawler health and data coverage by source"/></a></td>
</tr>
</table>

### Investigate before acting

<table>
<tr>
<td width="33%"><b>01 · Find</b><p>Trace new leads and institutional sources.</p><a href="data/discovered_candidates.json">Discovery queue</a></td>
<td width="34%"><b>02 · Verify</b><p>Find contradictory evidence and unresolved eligibility.</p><a href="data/portfolio_frontier.json">Verification frontier</a></td>
<td width="33%"><b>03 · Execute</b><p>Review deadlines and explicitly mark task completion.</p><a href="docs/TODAY.md">Execution agenda</a></td>
</tr>
</table>

<details>
<summary><b>Explore the research and proof topology · expand visual laboratory</b></summary>

<a href="data/portfolio_frontier.json"><img src="assets/readme/asset_dependencies.svg" width="100%" alt="Source-backed network of documents mentioned by applications"/></a>

<table><tr>
<td width="50%"><img src="assets/readme/proof_matrix.svg" width="100%" alt="Proof-debt matrix showing document mentions and readiness states"/></td>
<td width="50%"><img src="assets/readme/document_leverage.svg" width="100%" alt="Recorded document associations, not guaranteed eligible applications"/></td>
</tr></table>

The [offline observatory](dashboard/README.md) supports search, filters, separate submission and preparation clocks, evidence dossiers, document counterfactuals, deadline collisions, source-linked contradictions, verification queue and research-title term groups. GitHub's README renderer cannot execute browser JavaScript.

</details>

<details>
<summary><b>Evidence policy and provenance contract</b></summary>

- **Unknown is not false.** A document mentioned in a vacancy is not proof that it is missing.
- **A deadline is not a completed application.** Past steps retain unconfirmed status until owner action.
- **Source observation is not eligibility confirmation.** Evidence conflicts require manual review.
- **A paper is not an open position.** Research signals cannot be interpreted as funded recruitment.
- **No automatic submission.** Private owner controls preserve workbook decisions.

[Machine-readable view](data/experience_view.json) · [JSON-LD source lineage](data/experience_lineage.jsonld) · [System architecture](docs/ARCHITECTURE.md)

</details>

<sub>All figures are committed snapshots observed on {esc(view["as_of"])} ({esc(view["timezone"])}), not live counts. The application dashboard is a local, private HTML tool; it is not executed inside this README. No claims of worldwide novelty or verified admission probabilities.</sub>
"""



def lineage_jsonld(view: dict) -> dict:
    from urllib.parse import quote
    base="urn:phdtracker:"
    graph=[
        {
            "@id":base+"dataset:experience-view",
            "@type":"prov:Entity",
            "schema:name":"EvidenceGraph observation snapshot",
            "schema:dateModified":{"@value":view["as_of"],"@type":"xsd:date"},
            "prov:wasDerivedFrom":[
                {"@id":base+"dataset:portfolio-frontier"},
                {"@id":base+"dataset:application-assets"},
                {"@id":base+"dataset:source-monitor"},
            ],
        },
    ]
    for resource in view["resources"]:
        graph.append({
            "@id":base+"document:"+quote(resource["id"],safe=""),
            "@type":"prov:Entity",
            "schema:name":resource["label"],
            "readinessState":resource["state"],
        })
    for record in view["applications"]:
        node={
            "@id":base+"application:"+quote(record["id"],safe=""),
            "@type":"prov:Entity",
            "schema:name":record["name"],
            "applicationDeadline":{"@value":record["deadline"],"@type":"xsd:date"},
            "applicantDecision":record["decision"],
            "documentMention":[
                {"@id":base+"document:"+quote(rid,safe="")} for rid in record["documents"]
            ],
            "prov:wasDerivedFrom":{"@id":base+"dataset:portfolio-frontier"},
        }
        if record["source"]:
            node["schema:citation"]={"@id":record["source"]}
        if record["proof_obligations"]:
            node["proofObligation"]=record["proof_obligations"]
        graph.append(node)
    for observed in view["insights"]["source_anomalies"]:
        node={
            "@id":base+"observation:"+quote(observed["observation_id"],safe=""),
            "@type":"prov:Entity",
            "sourceFindingStatus":observed["status"],
            "expectedDeadline":observed["expected_deadline"],
            "prov:wasDerivedFrom":{"@id":base+"dataset:source-monitor"},
        }
        if observed["source"]:
            node["schema:citation"]={"@id":observed["source"]}
        if observed["is_linked"]:
            node["associatedApplication"]={
                "@id":base+"application:"+quote(observed["application_id"],safe="")
            }
        graph.append(node)
    return {
        "@context":{
            "prov":"http://www.w3.org/ns/prov#",
            "schema":"https://schema.org/",
            "xsd":"http://www.w3.org/2001/XMLSchema#",
            "documentMention":{"@id":base+"vocab:documentMention","@type":"@id"},
            "associatedApplication":{"@id":base+"vocab:associatedApplication","@type":"@id"},
            "readinessState":base+"vocab:readinessState",
            "applicationDeadline":base+"vocab:applicationDeadline",
            "applicantDecision":base+"vocab:applicantDecision",
            "proofObligation":base+"vocab:proofObligation",
            "sourceFindingStatus":base+"vocab:sourceFindingStatus",
            "expectedDeadline":base+"vocab:expectedDeadline",
        },
        "@graph":graph,
    }


def generate(root: Path = ROOT) -> dict:
    view = make_view(root)
    data = root / "data"
    assets = root / "assets/readme"
    docs = root / "docs"
    data.mkdir(parents=True,exist_ok=True)
    assets.mkdir(parents=True,exist_ok=True)
    docs.mkdir(parents=True,exist_ok=True)
    (data/"experience_view.json").write_text(json.dumps(view,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    (data/"experience_lineage.jsonld").write_text(json.dumps(lineage_jsonld(view),indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    renders = {
        "experience_hero.svg":hero_svg(view),
        "isometric_calendar.svg":isometric_calendar_svg(view),
        "asset_dependencies.svg":dependency_svg(view),
        "research_constellation.svg":research_map_svg(view),
        "deadline_orbits.svg":orbit_svg(view),
        "proof_matrix.svg":proof_svg(view),
        "source_signals.svg":providers_svg(view),
        "document_leverage.svg":resource_svg(view),
    }
    for name, content in renders.items():
        (assets/name).write_text(content,encoding="utf-8")
    make_gif(view,assets/"evidence_pipeline.gif")
    template=(root/"dashboard"/"template.html").read_text(encoding="utf-8")
    placeholder="__EVIDENCE_DATA_JSON__"
    if template.count(placeholder)!=1:
        raise ValueError("Dashboard template missing data placeholder")
    embedded=json.dumps(view,ensure_ascii=False).replace("<","\\u003c").replace(">","\\u003e").replace("&","\\u0026")
    (root/"dashboard"/"index.html").write_text(template.replace(placeholder,embedded),encoding="utf-8")
    document=markdown(view)
    document=(document.replace('src="assets/','src="../assets/')
              .replace('href="assets/','href="../assets/')
              .replace('href="dashboard/','href="../dashboard/')
              .replace('href="data/','href="../data/')
              .replace('](dashboard/','](../dashboard/')
              .replace('](data/','](../data/')
              .replace('](docs/TODAY.md)','](TODAY.md)')
              .replace('href="docs/','href="'))
    (docs/"EXPERIENCE.md").write_text(document,encoding="utf-8")
    return {"as_of":view["as_of"],"applications":len(view["applications"]),"assets":list(renders)+["evidence_pipeline.gif"]}


if __name__=="__main__":
    cli=argparse.ArgumentParser()
    cli.add_argument("--root",default=str(ROOT))
    args=cli.parse_args()
    print(json.dumps(generate(Path(args.root)),ensure_ascii=False))
