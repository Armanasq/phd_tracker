from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any, Callable
from zoneinfo import ZoneInfo

from .catalog import AGENTS, POLICY, PROVIDERS, WORKFLOWS
from .domain import agenda, merged_records, preflight, snapshot, today_in
from .providers import invoke, invoke_stream, ProviderError
from .store import ConflictError, Store
from .toolkit import DEFAULT_TOOLS, run_tools
from .settings import read_settings
from .routing import resolve_route
from .connectivity import provider_states
from .evidence_pack import bounded_evidence
from .relevance import select_evidence
from .proof_queue import evidence_work_queue
from .claim_audit import audit_generated_claims
from .prompt_contract import agent_system, conversation_block, build_agent_prompt
from .source_claims import source_claims
from .route_contract import assess_provider_contract, provider_route_fingerprint

def paper_radar_for_instance(root: Path, source: dict[str, Any]) -> list[dict[str, Any]]:
    instance = source.get("instance", {})
    identity = instance.get("type") if isinstance(instance, dict) else None
    filename = "research_radar.json" if identity in (None, "upstream") else "user_research_radar.json"
    try:
        payload = json.loads((Path(root) / "data" / filename).read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return []
    if not isinstance(payload, dict) or not isinstance(payload.get("papers"), list):
        return []
    result = []
    for paper in payload["papers"][:500]:
        if not isinstance(paper, dict):
            continue
        item = {key: paper.get(key) for key in ("title", "paper_url", "topic", "published", "relevance_score")}
        item["title"] = str(item["title"] or "")[:180]
        item["published"] = str(item["published"] or "")[:32]
        item["relevance_score"] = item["relevance_score"] if type(item["relevance_score"]) in (int, float) else 0
        result.append(item)
    return result


def catalog(store: Store) -> dict[str, list[dict[str, Any]]]:
    return {"providers": store.catalog("provider", PROVIDERS),
            "agents": store.catalog("agent", AGENTS),
            "workflows": store.catalog("workflow", WORKFLOWS)}

def selected(candidates: list[dict[str, Any]], identity: str, kind: str) -> dict[str, Any]:
    return next((x for x in candidates if x["id"] == identity), None) or _missing(kind, identity)

def _missing(kind: str, identity: str):
    raise ValueError("Unknown " + kind + ": " + identity)

def owner_records(store: Store, root: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    source = snapshot(root)
    records = merged_records(source, store.list_applications())
    confirmed = {(m.get("application_id"), m.get("date")) for m in store.items("milestone")
                 if m.get("kind") == "final" and m.get("verification") == "primary_confirmed"
                 and m.get("source_url") and m.get("time") and m.get("timezone")}
    for record in records:
        if (record["id"], record.get("deadline")) in confirmed:
            record["deadline_time_verified"] = True
    return source, records

class WorkflowExecutionError(RuntimeError):
    def __init__(self, workflow_id: str, stage: int, audit_run_id: str):
        self.workflow_id = workflow_id
        self.stage = stage
        self.audit_run_id = audit_run_id
        super().__init__(
            f"Workflow {workflow_id} stopped at stage {stage}; "
            f"review private run {audit_run_id} before retrying"
        )


def run_agent(store: Store, root: Path, *, agent_id: str, provider_id: str | None = None,
              application_id: str | None = None, input_text: str = "",
              cloud_consent: bool = False, workflow_id: str | None = None,
              conversation_id: str | None = None, conversation_mode: bool = False,
              on_delta: Callable[[str], None] | None = None,
              expected_provider_fingerprint: str | None = None) -> dict[str, Any]:
    configuration = catalog(store)
    agent = selected(configuration["agents"], agent_id, "agent")
    route = resolve_route(store, configuration["providers"], agent_id, provider_id)
    provider = route.provider
    provider_id = provider["id"]
    if expected_provider_fingerprint is not None:
        if not isinstance(expected_provider_fingerprint, str) or len(expected_provider_fingerprint) != 64:
            raise ValueError("Expected provider route fingerprint is invalid")
        if provider_route_fingerprint(provider) != expected_provider_fingerprint:
            raise ConflictError("Provider configuration changed after workflow preflight; review routes again")
    compatibility = assess_provider_contract(
        provider, agent.get("requirements"), stream_requested=on_delta is not None,
    )
    if not compatibility["compatible"]:
        raise ValueError("Incompatible agent model route: " + ", ".join(compatibility["blockers"]))
    if not provider["local"] and not cloud_consent:
        raise PermissionError("Manual cloud inference requires fresh per-run applicant-data disclosure consent")
    if not isinstance(input_text, str) or len(input_text) > 5000:
        raise ValueError("Input must be text up to 5000 characters")
    if conversation_id and not conversation_mode:
        raise ValueError("Conversation ID requires conversation mode")
    if conversation_mode and not input_text.strip():
        raise ValueError("A conversation message is required")
    history = store.conversation_context(conversation_id, agent_id, application_id) if conversation_id else []
    source, records = owner_records(store, root)
    by_id = {record["id"]: record for record in records}
    if application_id and application_id not in by_id:
        raise ValueError("Unknown application")
    relevant = by_id[application_id] if application_id else None
    today = today_in(read_settings(store)["timezone"])
    retrieval = select_evidence(input_text, records, application_id=application_id, today=today)
    if relevant:
        keep = ("id", "name", "record_type", "deadline", "deadline_kind", "deadline_type",
                "verification", "source_url", "apply_url", "funding", "eligibility", "fit", "topic",
                "documents", "document_states", "blockers", "next_step", "contact_status",
                "status", "followup", "faculty", "duplicate_submission_advisory", "priority")
        observation = {k: relevant.get(k) for k in keep}
        evidence = {"record": observation, "preflight": preflight(relevant, today),
                    "retrieval_method": retrieval["method"]}
    else:
        evidence = {"relevant_records": retrieval["records"],
                    "retrieval_method": retrieval["method"],
                    "matched_count": retrieval["matched_count"],
                    "summary": source.get("meta", {}), "date": today.isoformat(),
                    "agenda": agenda(records, today, 12),
                    "source_health": source.get("providers", [])}
    owner_claims = store.items("evidence")
    proof_queue=evidence_work_queue(records, store.items("milestone"), store.items("reference"),
                                    owner_claims, today, limit=15)["items"]
    if application_id:
        proof_queue=[item for item in proof_queue if item["application_id"]==application_id]
    evidence["proof_queue"]=[{"application_id":item["application_id"], "kind":item["kind"],
                                "action":item["action"], "proof_needed":item["proof_needed"]}
                               for item in proof_queue[:10]]
    visible_record_ids = {application_id} if application_id else {
        ref["application_id"] for ref in retrieval["references"]
    }
    evidence["claim_registry"] = [
        {field: claim.get(field) for field in (
            "id", "application_id", "field", "assertion", "status", "source_url",
            "observed_at", "excerpt"
        )} for claim in owner_claims
        if claim.get("application_id") in visible_record_ids
    ][:10]
    evidence["source_claims"] = [
        {
            "id": "SRC-" + str(item["id"]),
            "application_id": item["application_id"],
            "field": item["claim_type"],
            "assertion": item["candidate_value"],
            "status": item["verification"],
            "source_url": item["source_url"],
            "observed_at": item["captured_at"],
            "excerpt": item["exact_quote"],
            "source_sha256": item["source_digest"],
            "evidence_scope": "exact_captured_source_quote_not_verified_interpretation",
        }
        for item in source_claims(store, limit=200)
        if item["application_id"] in visible_record_ids
    ][:6]
    tool_names = agent.get("tools") if isinstance(agent.get("tools"), list) else DEFAULT_TOOLS.get(agent_id, [])
    private = {kind: (owner_claims if kind == "evidence" else store.items(kind))
               for kind in ("profile", "referee", "reference", "milestone", "evidence")}
    papers = paper_radar_for_instance(root, source) if "paper_radar" in tool_names else []
    tool_pack = run_tools(tool_names, data=source, records=records, private=private,
                          today=today, application_id=application_id, papers=papers)
    evidence["tool_results"] = tool_pack
    system = agent_system(POLICY, agent["instructions"])
    history_block = conversation_block(history)
    evidence_budget=max(1000, min(13500, 24000-len(system)-len(input_text)-len(history_block)-1200))
    evidence_json=bounded_evidence(evidence, max_chars=evidence_budget)
    visible_evidence=json.loads(evidence_json)
    if application_id:
        observed_ids={visible_evidence.get("record", {}).get("id")} if isinstance(visible_evidence.get("record"),dict) else set()
    else:
        observed_ids={item.get("id") for item in visible_evidence.get("relevant_records",[])
                      if isinstance(item,dict)}
    evidence_refs=[item for item in retrieval["references"] if item["application_id"] in observed_ids]
    evidence_truncated=bool(visible_evidence.get("_evidence_truncated",False))
    contract = build_agent_prompt(
        system=system, today=today, evidence_json=evidence_json,
        history_block=history_block, input_text=input_text,
    )
    prompt = contract.user
    inference_started = perf_counter()
    try:
        reply = (invoke_stream(provider, system, prompt, on_delta)
                 if on_delta is not None else invoke(provider, system, prompt))
    except ProviderError as error:
        store.put_run("workflow" if workflow_id else "agent", agent_id, application_id,
                      "failed", provider_id,
                      {"model": provider["model"], "error_type": type(error).__name__,
                       "workflow_id": workflow_id, "source_as_of": source.get("as_of"),
                       "latency_ms": round((perf_counter() - inference_started) * 1000)})
        raise
    available_claims = visible_evidence.get("claim_registry", [])
    if not isinstance(available_claims, list):
        available_claims = []
    source_quotes = visible_evidence.get("source_claims", [])
    if not isinstance(source_quotes, list):
        source_quotes = []
    claim_audit = audit_generated_claims(
        reply.content, evidence_refs, available_claims + source_quotes,
    )
    run_id = store.put_run("workflow" if workflow_id else "agent", agent_id, application_id,
                           "proposed", provider_id,
                           {"text": reply.content, "model": reply.model, "usage": reply.usage, "latency_ms": reply.latency_ms,
                            "workflow_id": workflow_id, "tools": [x["name"] for x in tool_pack["tools"]], "source_as_of": source.get("as_of"),
                            "evidence_refs": evidence_refs, "retrieval_method": retrieval["method"],
                             "claim_audit": claim_audit,
                            "source_claim_refs": [claim.get("id") for claim in source_quotes],
                            "prompt_contract_id": contract.contract_id,
                            "system_sha256": contract.system_sha256,
                            "notice": "AI output is a proposal; no application or communication was changed"})
    thread_id = store.save_conversation_turn(
        conversation_id=conversation_id, agent_id=agent_id, application_id=application_id,
        question=input_text, answer=reply.content, model=reply.model,
        provider_id=provider_id, run_id=run_id,
    ) if conversation_mode else None
    return {"id": run_id, "agent_id": agent_id, "provider_id": provider_id,
            "route_source": route.source, "model": reply.model, "usage": reply.usage, "latency_ms": reply.latency_ms, "text": reply.content,
            "conversation_id": thread_id, "evidence_refs": evidence_refs, "evidence_truncated": evidence_truncated,
            "retrieval_method": retrieval["method"], "claim_audit": claim_audit,
            "source_claim_refs": [claim.get("id") for claim in source_quotes],
            "prompt_contract_id": contract.contract_id, "system_sha256": contract.system_sha256,
            "status": "proposed", "tools": [x["name"] for x in tool_pack["tools"]], "source_as_of": source.get("as_of")}

def workflow_plan(store: Store, *, workflow_id: str, provider_id: str | None = None,
                  cloud_consent: bool = False) -> dict[str, Any]:
    options = catalog(store)
    workflow = selected(options["workflows"], workflow_id, "workflow")
    agent_ids = workflow.get("steps") or [workflow["agent_id"]]
    known = {agent["id"] for agent in options["agents"]}
    agent_definitions = {agent["id"]: agent for agent in options["agents"]}
    if not agent_ids or len(agent_ids) > 3 or any(agent not in known for agent in agent_ids):
        raise ValueError("Workflow must select 1–3 known agents")
    route_override = provider_id if provider_id not in (None, "", "auto") else workflow.get("provider_id", "auto")
    stages = []
    states = provider_states(store, options["providers"])
    cloud_providers = set()
    compatibility_blockers = []
    scheduled_approval = bool(workflow.get("enabled") and workflow.get("schedule") in {"daily", "twice_daily", "weekly"})
    for index, agent in enumerate(agent_ids):
        route = resolve_route(store, options["providers"], agent, route_override)
        provider = route.provider
        contract = assess_provider_contract(provider, agent_definitions[agent].get("requirements"))
        compatibility_blockers.extend(
            "stage_" + str(index + 1) + "_" + blocker for blocker in contract["blockers"]
        )
        if not provider["local"]:
            cloud_providers.add(provider["id"])
            scheduled_approval = scheduled_approval and route.approved
        stages.append({
            "step": index + 1,
            "agent_id": agent,
            "provider_id": provider["id"],
            "provider_fingerprint": provider_route_fingerprint(provider),
            "provider_label": provider["label"],
            "model": provider["model"],
            "route_source": route.source,
            "cloud": not provider["local"],
            "scheduled_provider_approved": route.approved,
            "inference_state": states.get(provider["id"], {}).get("state", "needs_setup"),
            "inference_verified": states.get(provider["id"], {}).get("state") == "responded",
            "capability_contract": contract,
        })
    blockers = []
    if cloud_providers and not cloud_consent:
        blockers.append("cloud_disclosure_consent_required")
    blockers.extend(compatibility_blockers)
    probe_required = sorted({stage["provider_id"] for stage in stages if not stage["inference_verified"]})
    if not workflow.get("enabled"):
        scheduled_approval = False
    if cloud_providers and not workflow.get("cloud_consent"):
        scheduled_approval = False
    if compatibility_blockers:
        scheduled_approval = False
    return {
        "schema_version": 1,
        "execution_mode": "sequential_bounded",
        "workflow_id": workflow_id,
        "schedule": workflow.get("schedule", "manual"),
        "enabled": bool(workflow.get("enabled")),
        "stages": stages,
        "model_calls": len(stages),
        "cloud_provider_count": len(cloud_providers),
        "manual_ready": not blockers,
        "execution_ready": not blockers and (len(stages) == 1 or not probe_required),
        "model_probe_required": probe_required,
        "compatibility_blockers": compatibility_blockers,
        "blockers": blockers,
        "scheduled_policy_approved": scheduled_approval,
        "notice": "Multi-stage execution requires recent successful inference probes for all providers. This preview does not test external models, quotas or due times.",
    }


def run_workflow(store: Store, root: Path, *, workflow_id: str,
                 provider_id: str | None = None, application_id: str | None = None,
                 input_text: str = "", cloud_consent: bool = False) -> dict[str, Any]:
    preview = workflow_plan(store, workflow_id=workflow_id, provider_id=provider_id,
                            cloud_consent=cloud_consent)
    if preview["compatibility_blockers"]:
        raise ValueError("Workflow provider capability mismatch: " + ", ".join(preview["compatibility_blockers"]))
    if not preview["manual_ready"]:
        raise PermissionError("Workflow requires explicit per-run cloud evidence disclosure before any agent stage")
    if len(preview["stages"]) > 1 and not preview["execution_ready"]:
        raise ValueError("Verify inference for every multi-stage model route before execution: " + ", ".join(preview["model_probe_required"]))
    workflow = selected(catalog(store)["workflows"], workflow_id, "workflow")
    agent_ids = [stage["agent_id"] for stage in preview["stages"]]
    objective = workflow.get("prompt") or workflow.get("description", "")
    if input_text:
        objective += "\n\n" + input_text
    outputs = []
    for index, stage in enumerate(preview["stages"]):
        agent_id = stage["agent_id"]
        prior = "\n\nPrevious agent proposals (unverified, no actions taken):\n" + "\n".join(
            x["agent_id"] + ": " + x["text"][:900] for x in outputs
        ) if outputs else ""
        try:
            result = run_agent(
                store, root, agent_id=agent_id, provider_id=stage["provider_id"],
                application_id=application_id,
                input_text=("Workflow step " + str(index + 1) + "/" + str(len(agent_ids)) +
                            ": " + objective + prior)[:5000],
                cloud_consent=cloud_consent, workflow_id=workflow_id,
                expected_provider_fingerprint=stage["provider_fingerprint"],
            )
        except (ProviderError, ValueError, PermissionError, OSError, RuntimeError) as error:
            audit_id = store.put_run(
                "workflow_summary", workflow_id, application_id, "failed", "multi_route",
                {
                    "schema_version": 1, "workflow_id": workflow_id,
                    "failed_stage": index + 1, "stage_count": len(agent_ids),
                    "failed_agent_id": agent_id, "failed_provider_id": stage["provider_id"],
                    "error_type": type(error).__name__,
                    "completed_run_ids": [item["id"] for item in outputs],
                    "notice": "Earlier agent outputs are unverified proposals; no external action was taken",
                },
            )
            raise WorkflowExecutionError(workflow_id, index + 1, audit_id) from error
        outputs.append(result)
    summary_id = store.put_run(
        "workflow_summary", workflow_id, application_id, "proposed", "multi_route",
        {
            "schema_version": 1, "workflow_id": workflow_id,
            "stage_count": len(agent_ids),
            "completed_run_ids": [item["id"] for item in outputs],
            "provider_routes": [stage["provider_id"] for stage in preview["stages"]],
            "notice": "All stages returned proposals; no application or communication was changed",
        },
    )
    return {**outputs[-1], "workflow_id": workflow_id, "workflow_execution_id": summary_id,
            "schema_version": 1,
            "steps": [{"run_id": x["id"], "agent_id": x["agent_id"],
                       "text": x["text"], "usage": x["usage"], "tools": x["tools"]} for x in outputs],
            "status": "proposed"}

def period_for(schedule: str, now: datetime) -> str:
    if schedule == "daily":
        return now.date().isoformat()
    if schedule == "twice_daily":
        return now.date().isoformat() + ("-AM" if now.hour < 12 else "-PM")
    if schedule == "weekly":
        year, week, _ = now.isocalendar()
        return f"{year}-W{week:02d}"
    return ""

def scheduler_once(store: Store, root: Path, *, now: datetime | None = None) -> list[dict[str, Any]]:
    current = (now or datetime.now(ZoneInfo("UTC"))).astimezone(ZoneInfo(read_settings(store)["timezone"]))
    result = []
    settings = catalog(store)
    preferences = read_settings(store)
    max_runs = preferences["max_runs_per_tick"]
    cloud_cap = preferences["max_cloud_model_calls_per_day"]
    cloud_ids = [p["id"] for p in settings["providers"] if not p["local"]]
    agent_definitions = {item["id"]: item for item in settings["agents"]}
    day_start = current.replace(hour=0, minute=0, second=0, microsecond=0).astimezone(timezone.utc).isoformat(timespec="seconds")
    for workflow in settings["workflows"]:
        if len(result) >= max_runs:
            break
        if not workflow.get("enabled") or workflow.get("schedule") == "manual":
            continue
        period = period_for(workflow["schedule"], current)
        if not period or store.schedule_last(workflow["id"]) == period:
            continue
        requested = workflow.get("provider_id") or "auto"
        stages = workflow.get("steps") or [workflow["agent_id"]]
        routes = [resolve_route(store, settings["providers"], agent, requested) for agent in stages]
        capability_checks = [
            assess_provider_contract(route.provider, agent_definitions[agent].get("requirements"))
            for agent, route in zip(stages, routes)
        ]
        if any(not check["compatible"] for check in capability_checks):
            result.append({"workflow_id": workflow["id"], "status": "skipped", "reason": "model_capability_mismatch"})
            continue
        consent = bool(workflow.get("cloud_consent", False))
        if any(not route.provider["local"] for route in routes) and not consent:
            result.append({"workflow_id": workflow["id"], "status": "skipped", "reason": "cloud_consent_missing"})
            continue
        if any(not route.approved for route in routes):
            missing = [route.provider["id"] for route in routes if not route.approved]
            reason = (
                "cloud_provider_not_approved"
                if any(identity not in preferences["approved_cloud_providers"] for identity in missing)
                else "cloud_provider_reverification_required"
            )
            result.append({"workflow_id": workflow["id"], "status": "skipped", "reason": reason})
            continue
        needed = sum(not route.provider["local"] for route in routes)
        token, reason = store.schedule_claim(
            workflow["id"], period, cloud_calls=needed, cloud_cap=cloud_cap,
            cloud_ids=cloud_ids, day_start=day_start,
        )
        if token is None:
            if reason != "already_executed":
                result.append({"workflow_id": workflow["id"], "status": "skipped", "reason": reason})
            continue
        try:
            output = run_workflow(store, root, workflow_id=workflow["id"], provider_id=requested,
                                  cloud_consent=consent)
        except (ValueError, PermissionError, OSError, RuntimeError) as error:
            store.schedule_release(workflow["id"], period, token)
            result.append({"workflow_id": workflow["id"], "status": "failed", "reason": str(error)[:180]})
            continue
        try:
            store.schedule_complete(workflow["id"], period, token)
        except ValueError as error:
            result.append({"workflow_id": workflow["id"], "status": "failed", "reason": str(error)[:180]})
            continue
        result.append({"workflow_id": workflow["id"], "status": "proposed", "run_id": output["id"]})
    return result
