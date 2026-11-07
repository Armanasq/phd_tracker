from __future__ import annotations

import argparse
import json
import os
from collections import Counter
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HORIZONS = (7, 14, 30, 45)
FOCI = ("deadlines", "verification", "resources", "research")


def md(value: object, limit: int = 155) -> str:
    return str(value or "").replace("|", "/").replace("\n", " ").replace("\r", " ")[:limit]


def scenario(view: dict, horizon: int, focus: str, ready: set[str]) -> dict:
    if horizon not in HORIZONS:
        raise ValueError(f"Unsupported horizon: {horizon}")
    if focus not in FOCI:
        raise ValueError(f"Unsupported focus: {focus}")
    resources = {str(x["id"]): x for x in view.get("resources", [])}
    if ready - resources.keys():
        raise ValueError("Unknown document IDs: " + ", ".join(sorted(ready - resources.keys())))
    snapshot = date.fromisoformat(view["as_of"])
    apps = [
        a for a in view["applications"]
        if 0 <= (date.fromisoformat(a["deadline"]) - snapshot).days <= horizon
    ]
    apps.sort(key=lambda a: (a["deadline"], a["name"]))
    lanes = {}
    for kind, entries in view.get("clocks", {}).items():
        lanes[kind] = [
            row for row in entries
            if 0 <= (date.fromisoformat(row["due"]) - snapshot).days <= horizon
        ]
    collisions = [
        row for row in view.get("insights", {}).get("deadline_collisions", [])
        if 0 <= (date.fromisoformat(row["date"]) - snapshot).days <= horizon
    ]
    anomalies = list(view.get("insights", {}).get("source_anomalies", []))
    ranked = []
    for a in apps:
        unknown = [
            rid for rid in a.get("documents", [])
            if resources[rid]["state"] == "unknown" and rid not in ready
        ]
        obligations = a.get("proof_obligations", [])
        linked_anomalies = [x for x in anomalies if x.get("application_id") == a["id"]]
        ranked.append({
            "id": a["id"], "name": a["name"], "deadline": a["deadline"],
            "days": (date.fromisoformat(a["deadline"]) - snapshot).days,
            "unconfirmed_document_mentions": unknown,
            "explicit_proof_obligations": obligations,
            "source_anomalies": [x["status"] for x in linked_anomalies],
            "source": a.get("source", ""),
            "decision": a.get("decision", "unknown"),
            "scenario_all_mentioned_covered": bool(a.get("documents")) and not unknown,
        })
    ranked.sort(key=lambda a: (a["days"], -len(a["source_anomalies"]), -len(a["explicit_proof_obligations"]), -len(a["unconfirmed_document_mentions"])))
    return {
        "schema_version": 1,
        "snapshot_as_of": snapshot.isoformat(),
        "horizon_days": horizon,
        "focus": focus,
        "scenario_hypothetical_ready": sorted(ready),
        "application_count": len(apps),
        "applications": ranked,
        "deadline_collisions": collisions,
        "source_anomalies": anomalies,
        "clock_counts": {kind: len(rows) for kind, rows in lanes.items()},
        "source_providers": view.get("providers", []),
        "research_count": len(view.get("research", [])),
        "policy": "This report ranks verification workload and calendar urgency, not admission probability, eligibility, or confirmed submission status.",
    }


def report(result: dict) -> str:
    lines = [
        "# EvidenceGraph — interactive scenario run",
        "",
        f'**Source snapshot:** {md(result["snapshot_as_of"])} · **Horizon:** {result["horizon_days"]} days · **Lens:** {md(result["focus"])}',
        "",
        f'**{result["application_count"]}** application records in window · '
        f'**{len(result["deadline_collisions"])}** days with colliding deadlines · '
        f'**{len(result["source_anomalies"])}** monitored source anomalies',
        "",
        "> This is an executable, input-driven GitHub Actions analysis of the stored evidence. "
        "It is not a live institutional portal check, submission confirmation, or admissions prediction.",
        "",
    ]
    if result["scenario_hypothetical_ready"]:
        lines += [
            "**Hypothetical ready documents:** " + ", ".join(md(x) for x in result["scenario_hypothetical_ready"]),
            "",
            "These hypothetical states affect only the report; owner-confirmed readiness is unchanged.",
            "",
        ]
    if result["focus"] in {"deadlines", "verification", "resources"}:
        lines += [
            "## Next evidence-grounded decisions",
            "",
            "| Deadline | Source ID | Application | Unknown document mentions | Source flags |",
            "|:--|:--|:--|--:|:--|",
        ]
        for a in result["applications"][:35]:
            link = f'[Source]({a["source"]})' if a["source"].startswith("https://") else "No source URL"
            flags = ", ".join(a["source_anomalies"]) or "—"
            lines.append(f'| {md(a["deadline"])} | {md(a["id"])} | {md(a["name"], 95)} · {link} | '
                         f'{len(a["unconfirmed_document_mentions"])} | {md(flags)} |')
        if not result["applications"]:
            lines.append("| — | — | No applications within this horizon | — | — |")
        lines.append("")
    if result["focus"] in {"deadlines", "verification"}:
        lines += ["## Deadline collisions", ""]
        if result["deadline_collisions"]:
            for collision in result["deadline_collisions"][:12]:
                lines.append(f'- **{collision["date"]}: {collision["count"]} records** — ' +
                             ", ".join(md(a["id"]) for a in collision["applications"]))
        else:
            lines.append("No multiple-deadline days in the selected horizon.")
        lines.append("")
    if result["focus"] in {"resources", "verification"}:
        lines += [
            "## Explicit uncertainty, not fabricated readiness",
            "",
            "| ID | Remaining mentioned documents with unknown status | Explicit evidence obligations |",
            "|:--|--:|--:|",
        ]
        for a in result["applications"][:35]:
            lines.append(f'| {md(a["id"])} | {len(a["unconfirmed_document_mentions"])} | {len(a["explicit_proof_obligations"])} |')
        lines.append("")
    if result["focus"] in {"research", "verification"}:
        lines += [
            "## Research and source coverage",
            "",
            f'**{result["research_count"]}** indexed research records (papers are not job adverts).',
            "",
            "| Discovery provider | Status | Observed | New distinct |",
            "|:--|:--|--:|--:|",
        ]
        for p in result["source_providers"]:
            lines.append(f'| {md(p["name"])} | {md(p["health"])} | {p["observed"]} | {p["new_unique"]} |')
        lines.append("")
    lines += [
        "## Different execution clocks",
        "",
        *[f'- **{md(kind)}:** {number} dated events in the stored day snapshot' for kind, number in sorted(result["clock_counts"].items())],
        "",
        f'**Interpretation contract:** {result["policy"]}',
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=Path, default=ROOT / "data" / "experience_view.json")
    parser.add_argument("--output", type=Path, default=ROOT / "artifacts" / "scenario_report.json")
    parser.add_argument("--horizon", type=int, choices=HORIZONS, default=14)
    parser.add_argument("--focus", choices=FOCI, default="deadlines")
    parser.add_argument("--hypothetical-ready", default="")
    args = parser.parse_args()
    view = json.loads(args.input.read_text(encoding="utf-8"))
    ready = {v.strip() for v in args.hypothetical_ready.split(",") if v.strip()}
    result = scenario(view, args.horizon, args.focus, ready)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    content = report(result)
    if os.environ.get("GITHUB_STEP_SUMMARY"):
        with open(os.environ["GITHUB_STEP_SUMMARY"], "a", encoding="utf-8") as handle:
            handle.write(content + "\n")
    print(content)


if __name__ == "__main__":
    main()
