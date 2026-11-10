from __future__ import annotations

import hmac
import ipaddress
import json
import mimetypes
import os
import re
import uuid
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import BoundedSemaphore
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .catalog import agent_spec, provider_spec, workflow_spec
from .domain import agenda, plan_capacity, preflight, today_in
from .operations import evidence_conflicts, milestones_for, referee_matrix, research_fit_signals, resource_schedule
from .proof_queue import evidence_work_queue
from .providers import invoke, ProviderError
from .connectivity import model_list, provider_states, remember_check
from .settings import read_settings, save_settings
from .routing import resolve_route, routing_status
from .secrets import read_secret, write_secret
from .metrics import usage_summary
from .observability import report_observability
from .capabilities import private_runtime_capabilities
from .scheduler_preview import scheduler_preview
from .toolkit import TOOL_NAMES, DEFAULT_TOOLS
from time import perf_counter
from .calendar import line_items
from .engine import catalog, owner_records, run_agent, run_workflow, workflow_plan, scheduler_once, selected
from .store import ConflictError, Store, default_path
from .job_queue import enqueue_local_agent, list_jobs, job_status, cancel_job
from .request_budget import RequestBudget
from .recovery import runtime_lock

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"


def prepare_public_snapshot(root: Path) -> dict:
    from scripts.build_workspace import build
    root = Path(root).resolve()
    target = root / "site" / "data" / "workspace.json"
    if not (root / "site" / "index.html").is_file():
        raise ValueError("The PhD Atlas site directory is missing; run the service from a complete clone")
    data = build(root)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name("." + target.name + "." + uuid.uuid4().hex + ".tmp")
    try:
        temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temporary.replace(target)
    finally:
        temporary.unlink(missing_ok=True)
    return {
        "path": str(target),
        "records": len(data["records"]),
        "data_mode": data["instance"]["data_mode"],
        "repository": data["instance"]["repository"],
    }


class ApiServer(ThreadingHTTPServer):
    daemon_threads = True
    def __init__(self, address: tuple[str, int], *, store: Store, root: Path):
        try:
            slots = int(os.environ.get("PHDAI_MAX_CONCURRENT_INFERENCE", "2"))
        except ValueError as error:
            raise ValueError("PHDAI_MAX_CONCURRENT_INFERENCE must be an integer") from error
        if not 1 <= slots <= 8:
            raise ValueError("Inference concurrency limit must be between 1 and 8")
        self.inference_slots = BoundedSemaphore(slots)
        self.inference_limit = slots
        try:
            max_inference_minute = int(os.environ.get("PHDAI_MAX_INFERENCE_PER_MINUTE", "30"))
            max_writes_minute = int(os.environ.get("PHDAI_MAX_WRITES_PER_MINUTE", "180"))
        except ValueError as error:
            raise ValueError("Request rate budgets must be integers") from error
        self.request_budget = RequestBudget(
            inference_per_minute=max_inference_minute,
            writes_per_minute=max_writes_minute,
        )
        super().__init__(address, ApiHandler)
        self.store = store
        self.root = Path(root)
        self.site = self.root / "site"

class ApiHandler(BaseHTTPRequestHandler):
    server: ApiServer

    def setup(self) -> None:
        self.request_id = uuid.uuid4().hex
        self.request.settimeout(30)
        super().setup()

    @property
    def request_store(self) -> Store:
        if not hasattr(self, "_request_store"):
            self._request_store = Store(self.server.store.path)
        return self._request_store

    def finish(self) -> None:
        try:
            super().finish()
        finally:
            if hasattr(self, "_request_store"):
                self._request_store.close()

    def log_message(self, format: str, *args) -> None:
        return

    def allowed(self) -> bool:
        hosts = self.headers.get_all("Host", [])
        if len(hosts) != 1:
            return False
        try:
            host = urlsplit("//" + hosts[0])
            if (
                host.hostname not in {"127.0.0.1", "localhost", "::1"}
                or host.port != self.server.server_port
                or host.path or host.query or host.fragment
                or host.username or host.password
            ):
                return False
            if not ipaddress.ip_address(self.client_address[0]).is_loopback:
                return False
            origins = self.headers.get_all("Origin", [])
            if len(origins) > 1:
                return False
            if origins:
                origin = urlsplit(origins[0])
                if (
                    origin.scheme != "http"
                    or origin.hostname != host.hostname
                    or origin.port != self.server.server_port
                    or origin.path or origin.query or origin.fragment
                    or origin.username or origin.password
                ):
                    return False
        except ValueError:
            return False
        token = os.environ.get("PHDAI_API_TOKEN", "")
        return not token or hmac.compare_digest(
            self.headers.get("Authorization", ""), "Bearer " + token
        )

    def send_json(self, value: object, status: int = 200) -> None:
        raw = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Request-ID", self.request_id)
        self.end_headers()
        self.wfile.write(raw)

    def payload(self) -> dict:
        lengths = self.headers.get_all("Content-Length", [])
        if len(lengths) != 1 or self.headers.get("Transfer-Encoding"):
            raise ValueError("Request requires one Content-Length and no Transfer-Encoding")
        try:
            length = int(lengths[0])
        except ValueError as error:
            raise ValueError("Invalid Content-Length") from error
        if length <= 0 or length > 60_000:
            raise ValueError("Request must contain 1–60000 bytes")
        if self.headers.get("Content-Type", "").split(";")[0].strip().lower() != "application/json":
            raise ValueError("Expected application/json")
        data = json.loads(self.rfile.read(length))
        if not isinstance(data, dict):
            raise ValueError("Expected a JSON object")
        return data

    def dispatch(self, method: str) -> None:
        if not self.allowed():
            self.send_json({"error": "Access denied: local origin or API token mismatch"}, 403)
            return
        path = urlsplit(self.path).path
        costly = method == "POST" and path in {
            "/api/agents/run", "/api/agents/stream", "/api/workflows/run", "/api/providers/probe",
            "/api/providers/models", "/api/scheduler/tick",
        }
        if method == "POST" and not self.server.request_budget.admit("inference" if costly else "write"):
            self.send_json({"error": "Private runtime request budget exceeded; retry after the window resets"}, 429)
            return
        if costly and not self.server.inference_slots.acquire(blocking=False):
            self.send_json({"error": "Inference capacity reached; retry after an active request finishes"}, 429)
            return
        try:
            try:
                if method == "GET":
                    self.get_route(path)
                elif method == "POST":
                    self.post_route(path, self.payload())
                else:
                    self.send_json({"error": "Unsupported method"}, 405)
            except ConflictError as error:
                self.send_json({"error": str(error)}, 409)
            except PermissionError as error:
                self.send_json({"error": str(error)}, 403)
            except (ValueError, KeyError, TypeError, json.JSONDecodeError) as error:
                self.send_json({"error": str(error)[:220]}, 400)
            except (BrokenPipeError, ConnectionResetError):
                return
            except (OSError, RuntimeError) as error:
                self.send_json({"error": str(error)[:220]}, 502)
        finally:
            if costly:
                self.server.inference_slots.release()

    def do_GET(self) -> None:
        self.dispatch("GET")

    def do_POST(self) -> None:
        self.dispatch("POST")

    def do_OPTIONS(self) -> None:
        self.send_json({"error": "Cross-origin requests are disabled"}, 405)

    def get_route(self, path: str) -> None:
        store = self.request_store
        if path == "/api/health":
            self.send_json({"status": "ok", "mode": "loopback_private", "ai_side_effects": "none"})
        elif path == "/api/capabilities":
            available = catalog(store)
            preferences = read_settings(store)
            provider_id = preferences["default_provider"]
            current = next((item for item in available["providers"] if item["id"] == provider_id), None)
            verified = bool(current and provider_states(store, [current])[provider_id]["state"] == "responded")
            self.send_json(private_runtime_capabilities(
                provider_verified=verified,
                provider_name=current["label"] if current else None,
                provider_kind=current["kind"] if current else None,
            ))
        elif path == "/api/bootstrap":
            source, records = owner_records(store, self.server.root)
            today = today_in(read_settings(store)["timezone"])
            self.send_json({"catalog": catalog(store), "meta": source.get("meta", {}), "as_of": source.get("as_of"),
                            "records": records, "agenda": agenda(records, today, 40),
                            "runs": store.runs(30), "activity": store.activity(30),
                            "usage_summary": usage_summary(store),
                            "providers_status": source.get("providers", []),
                            "provider_states": provider_states(store, catalog(store)["providers"]),
                            "settings": read_settings(store),
                            "routing": routing_status(store, catalog(store)["providers"], catalog(store)["agents"]),
                            "tool_names": sorted(TOOL_NAMES), "default_tools": DEFAULT_TOOLS,
                            "security": {"local_only": True, "credentials": "environment variables", "auto_application_submission": False}})
        elif path == "/api/assistant/bootstrap":
            available = catalog(store)
            try:
                as_of = json.loads((self.server.site / "data" / "workspace.json").read_text(encoding="utf-8")).get("as_of")
            except (OSError, ValueError, TypeError):
                as_of = None
            self.send_json({
                "catalog": {"providers": available["providers"], "agents": available["agents"]},
                "settings": read_settings(store),
                "provider_states": provider_states(store, available["providers"]),
                "routing": routing_status(store, available["providers"], available["agents"]),
                "conversations": store.conversations(20),
                "as_of": as_of,
                "security": {"local_only": True, "auto_application_submission": False},
            })
        elif path == "/api/jobs":
            self.send_json({"jobs": list_jobs(store)})
        elif path.startswith("/api/jobs/"):
            self.send_json(job_status(store, unquote(path.removeprefix("/api/jobs/"))))
        elif path == "/api/conversations":
            self.send_json({"conversations": store.conversations(30)})
        elif path.startswith("/api/conversations/"):
            identity = unquote(path.removeprefix("/api/conversations/"))
            self.send_json(store.conversation(identity))
        elif path == "/api/calendar.ics":
            source, records = owner_records(store, self.server.root)
            events = milestones_for(records, store.items("milestone"), today_in(read_settings(store)["timezone"]))
            body = line_items(records, events, store.items("reference")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/calendar; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="phd-atlas-private.ics"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/source-observations":
            from .source_observer import recent_observations
            self.send_json({"observations": recent_observations(store)})
        elif path == "/api/observability":
            self.send_json(report_observability(store))
        elif path == "/api/metrics":
            self.send_json(usage_summary(store))
        elif path == "/api/diagnostics":
            self.send_json(store.diagnostics())
        elif path == "/api/scheduler/preview":
            self.send_json(scheduler_preview(store))
        elif path == "/api/settings":
            self.send_json({"settings": read_settings(store),
                            "provider_states": provider_states(store, catalog(store)["providers"]),
                            "routing": routing_status(store, catalog(store)["providers"], catalog(store)["agents"])})
        elif path == "/api/routing":
            self.send_json(routing_status(store, catalog(store)["providers"], catalog(store)["agents"]))
        elif path == "/api/operations":
            source, records = owner_records(store, self.server.root)
            today = today_in(read_settings(store)["timezone"])
            profile = (store.items("profile") or [{}])[0]
            referees = store.items("referee")
            references = store.items("reference")
            milestones = store.items("milestone")
            claims = store.items("evidence")
            self.send_json({"referees": referees, "references": references, "milestones": milestones,
                            "claims": claims, "profile": profile,
                            "referee_matrix": referee_matrix(referees, references, today),
                            "deadline_events": milestones_for(records, milestones, today),
                            "evidence_conflicts": evidence_conflicts(claims),
                            "research_fit_signals": research_fit_signals(profile, records),
                            "proof_queue": evidence_work_queue(records, milestones, references, claims, today),
                            "as_of": today.isoformat()})
        elif path == "/api/runs":
            self.send_json(store.runs())
        elif path == "/api/activity":
            self.send_json(store.activity())
        elif path == "/api/snapshot":
            source, records = owner_records(store, self.server.root)
            source["records"] = records
            self.send_json(source)
        elif path == "/data/workspace.json":
            source, records = owner_records(store, self.server.root)
            source["records"] = records
            self.send_json(source)
        elif path.startswith("/api/preflight/"):
            identity = unquote(path.removeprefix("/api/preflight/"))
            source, records = owner_records(store, self.server.root)
            record = next((r for r in records if r["id"] == identity), None)
            if not record:
                raise ValueError("Unknown application")
            self.send_json(preflight(record, today_in(read_settings(store)["timezone"])))
        else:
            self.static(path)

    def inference_reply(self, path: str, data: dict, operation) -> None:
        key = self.headers.get("Idempotency-Key")
        if key is None:
            self.send_json(operation())
            return
        state, cached = self.request_store.begin_idempotent(key, path, data)
        if state == "replayed":
            self.send_json(cached)
            return
        if state == "running":
            self.send_json({"error": "Request with this idempotency key is still processing"}, 409)
            return
        try:
            result = operation()
            self.request_store.complete_idempotent(key, result)
        except Exception:
            self.request_store.abort_idempotent(key)
            raise
        self.send_json(result)

    def stream_agent(self, data: dict) -> None:
        if self.headers.get("Idempotency-Key"):
            raise ValueError("Streaming requests do not support replay keys; use /api/agents/run")
        agent_id = data.get("agent_id")
        if not isinstance(agent_id, str):
            raise ValueError("Agent ID is required")
        input_text = data.get("input_text", "")
        if not isinstance(input_text, str) or len(input_text) > 5000:
            raise ValueError("Agent input must contain at most 5000 characters")
        config = catalog(self.request_store)
        selected(config["agents"], agent_id, "agent")
        route = resolve_route(self.request_store, config["providers"], agent_id, data.get("provider_id"))
        if route.provider["kind"] not in {"openai_compatible", "azure_openai", "azure_deployment"}:
            raise ValueError("Selected provider does not support native SSE streaming")
        if not route.provider["local"] and data.get("cloud_consent") is not True:
            raise PermissionError("Cloud streaming requires fresh per-run applicant-data disclosure consent")

        self.send_response(200)
        self.send_header("Content-Type", "text/event-stream; charset=utf-8")
        self.send_header("Cache-Control", "no-cache, no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Accel-Buffering", "no")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("X-Request-ID", self.request_id)
        self.send_header("Connection", "close")
        self.end_headers()
        self.close_connection = True

        def emit(event: str, payload: dict) -> None:
            body = "event: " + event + "\n" + "data: " + json.dumps(
                payload, ensure_ascii=False, separators=(",", ":")) + "\n\n"
            self.wfile.write(body.encode("utf-8"))
            self.wfile.flush()

        try:
            emit("status", {"status": "running", "request_id": self.request_id})
            response = run_agent(
                self.request_store, self.server.root,
                agent_id=agent_id, provider_id=data.get("provider_id"),
                application_id=data.get("application_id"),
                input_text=input_text,
                cloud_consent=data.get("cloud_consent") is True,
                conversation_mode=data.get("conversation") is True,
                conversation_id=data.get("conversation_id"),
                on_delta=lambda fragment: emit("delta", {"text": fragment}),
            )
            emit("result", response)
            emit("done", {"status": "complete"})
        except (BrokenPipeError, ConnectionResetError):
            return
        except (ProviderError, RuntimeError, OSError, ValueError, KeyError, PermissionError) as error:
            message = ("Cloud consent required" if isinstance(error, PermissionError) else
                       "Invalid streaming request" if isinstance(error, (ValueError, KeyError)) else
                       "Streaming run failed; inspect the private run history")
            try:
                emit("error", {"code": type(error).__name__, "error": message})
            except (BrokenPipeError, ConnectionResetError):
                return

    def post_route(self, path: str, data: dict) -> None:
        store = self.request_store
        root = self.server.root
        if path == "/api/settings":
            self.send_json({"settings": save_settings(store, data)})
        elif path == "/api/source-observations/review":
            from .source_reviews import record_source_review
            if "expected_digest" not in data:
                raise ValueError("Source review requires an explicit observed digest")
            review = record_source_review(
                store,
                observation_id=data.get("observation_id"),
                decision=data.get("decision"),
                note=data.get("note"),
                expected_digest=data["expected_digest"],
            )
            self.send_json({"review": review})
        elif path == "/api/maintenance/backup":
            self.send_json({"backup": store.create_backup(retain=data.get("retain", 7))})
        elif path == "/api/providers/setup":
            spec = provider_spec(data["provider"])
            store.put_custom("provider", spec)
            if "credential" in data:
                if not spec["api_key_env"]:
                    if data["credential"]:
                        raise ValueError("This provider has no credential variable")
                else:
                    write_secret(spec["api_key_env"], data["credential"])
            self.send_json({"saved": True, "provider": spec,
                            "state": provider_states(store, [spec])[spec["id"]]})
        elif path == "/api/providers/activate":
            provider = selected(catalog(store)["providers"], data["provider_id"], "provider")
            status = provider_states(store, [provider])[provider["id"]]
            if status["state"] != "responded":
                raise ValueError("Test a successful inference response before activating this provider")
            approve = data.get("allow_cloud_data") is True
            if not provider["local"] and not approve:
                raise PermissionError("Automatic cloud routing requires explicit applicant-data disclosure approval")
            settings = read_settings(store)
            approved = set(settings["approved_cloud_providers"])
            if not provider["local"]:
                approved.add(provider["id"])
            updated = save_settings(store, {"default_provider": provider["id"],
                                            "approved_cloud_providers": sorted(approved)})
            self.send_json({"activated": True, "settings": updated,
                            "routing": routing_status(store, catalog(store)["providers"], catalog(store)["agents"])})
        elif path == "/api/providers/credential":
            provider = selected(catalog(store)["providers"], data["provider_id"], "provider")
            variable = provider.get("api_key_env") or ""
            if not variable:
                raise ValueError("Provider has no credential variable")
            write_secret(variable, data["credential"])
            store.put_custom("provider", provider)
            self.send_json({"saved": True, "provider_id": provider["id"],
                            "credential_configured": bool(read_secret(variable)),
                            "requires_reverification": True})
        elif path in {"/api/providers/probe", "/api/providers/models"}:
            provider = selected(catalog(store)["providers"], data["provider_id"], "provider")
            if not provider["local"] and data.get("cloud_consent") is not True:
                raise PermissionError("Cloud provider connection checks require explicit consent")
            started = perf_counter()
            try:
                if path == "/api/providers/models":
                    result = model_list(provider)
                    remember_check(store, provider["id"], status="reachable",
                                   latency_ms=result["latency_ms"], model_count=result["model_count"])
                else:
                    response = invoke(provider, "Answer with one short sentence.",
                                      "Respond with the exact text: Provider connection successful.", timeout=18)
                    result = {"status": "responded", "provider_id": provider["id"],
                              "model": response.model, "response": response.content[:600],
                              "usage": response.usage}
                    remember_check(store, provider["id"], status="responded", model=response.model,
                                   latency_ms=round((perf_counter() - started) * 1000))
            except (OSError, RuntimeError, ValueError) as error:
                remember_check(store, provider["id"], status="failed",
                               latency_ms=round((perf_counter() - started) * 1000),
                               error=str(error))
                raise
            self.send_json(result)
        elif path.startswith("/api/private/"):
            parts = path.removeprefix("/api/private/").split("/")
            if len(parts) == 1:
                kind = parts[0]
                if kind in {"reference", "milestone", "evidence"}:
                    _, known = owner_records(store, root)
                    if data.get("application_id") not in {r["id"] for r in known}:
                        raise ValueError("Unknown application ID")
                if kind == "reference" and data.get("referee_id") not in {r["id"] for r in store.items("referee")}:
                    raise ValueError("Unknown referee ID")
                expected = data.pop("expected_version", None)
                if type(expected) is not int or expected < 0:
                    raise ValueError("Private record updates require a non-negative expected_version")
                self.send_json({"saved": True, "entry": store.put_item(kind, data, expected_version=expected)})
            elif len(parts) == 3 and parts[-1] == "delete":
                expected = data.get("expected_version")
                if type(expected) is not int or expected < 1:
                    raise ValueError("Private record deletion requires a positive expected_version")
                self.send_json({"deleted": store.delete_item(parts[0], unquote(parts[1]), expected_version=expected)})
            else:
                self.send_json({"error": "Unknown private record route"}, 404)
        elif path == "/api/schedule":
            source, records = owner_records(store, root)
            today = today_in(read_settings(store)["timezone"])
            profile = (store.items("profile") or [{}])[0]
            hours = data.get("hours_per_week") or profile.get("hours_per_week")
            if hours is None:
                raise ValueError("Configure available hours per week in your private applicant profile")
            self.send_json(resource_schedule(records, today, hours, profile))
        elif path == "/api/jobs/enqueue":
            self.send_json({"job": enqueue_local_agent(
                store, agent_id=data["agent_id"], input_text=data.get("input_text", ""),
                provider_id=data.get("provider_id"), application_id=data.get("application_id"),
                max_attempts=data.get("max_attempts", 2),
            )}, 202)
        elif path.startswith("/api/jobs/") and path.endswith("/cancel"):
            identity = unquote(path[len("/api/jobs/"):-len("/cancel")].strip("/"))
            self.send_json({"job": cancel_job(store, identity)})
        elif path == "/api/agents/stream":
            self.stream_agent(data)
        elif path == "/api/agents/run":
            self.inference_reply(path, data, lambda: run_agent(store, root,
                                     agent_id=data["agent_id"], provider_id=data.get("provider_id"),
                                     application_id=data.get("application_id"), input_text=data.get("input_text", ""),
                                     cloud_consent=data.get("cloud_consent") is True,
                                     conversation_mode=data.get("conversation") is True,
                                     conversation_id=data.get("conversation_id")))
        elif path.startswith("/api/conversations/") and path.endswith("/delete"):
            identity = unquote(path[len("/api/conversations/"):-len("/delete")].strip("/"))
            self.send_json({"deleted": store.delete_conversation(identity)})
        elif path == "/api/workflows/preview":
            self.send_json(workflow_plan(
                store, workflow_id=data["workflow_id"],
                provider_id=data.get("provider_id"),
                cloud_consent=data.get("cloud_consent") is True,
            ))
        elif path == "/api/workflows/run":
            self.inference_reply(path, data, lambda: run_workflow(store, root,
                                        workflow_id=data["workflow_id"], provider_id=data.get("provider_id"),
                                        application_id=data.get("application_id"), input_text=data.get("input_text", ""),
                                        cloud_consent=data.get("cloud_consent") is True))
        elif path in {"/api/catalog/provider", "/api/catalog/agent", "/api/catalog/workflow"}:
            kind = path.rsplit("/", 1)[-1]
            validated = {"provider": provider_spec, "agent": agent_spec, "workflow": workflow_spec}[kind](data)
            if kind == "workflow":
                ids = {a["id"] for a in catalog(store)["agents"]}
                if validated["agent_id"] not in ids:
                    raise ValueError("Workflow references an unknown agent")
                if any(step not in ids for step in validated.get("steps", [])):
                    raise ValueError("Workflow contains an unknown agent step")
                provider_ids = {p["id"] for p in catalog(store)["providers"]}
                if validated.get("provider_id") not in provider_ids | {"auto"}:
                    raise ValueError("Workflow references an unknown model provider")
            store.put_custom(kind, validated)
            self.send_json({"saved": True, "kind": kind, "entry": validated})
        elif path.startswith("/api/applications/") and path.endswith("/update"):
            identity = unquote(path[len("/api/applications/"):-len("/update")].strip("/"))
            _, records = owner_records(store, root)
            if identity not in {r["id"] for r in records}:
                raise ValueError("Unknown application")
            expected = data.get("expected_version")
            if not isinstance(expected, int) or isinstance(expected, bool) or expected < 0:
                raise ValueError("expected_version must be a non-negative integer")
            self.send_json(store.update_application(identity, data["patch"], expected))
        elif path == "/api/capacity":
            source, records = owner_records(store, root)
            hours = data.get("hours_per_week")
            self.send_json(plan_capacity(records, today_in(read_settings(store)["timezone"]), hours))
        elif path == "/api/scheduler/tick":
            self.send_json({"results": scheduler_once(store, root)})
        else:
            self.send_json({"error": "Unknown API endpoint"}, 404)

    def static(self, path: str) -> None:
        relative = unquote(path).lstrip("/") or "index.html"
        if relative.startswith("api/"):
            self.send_json({"error": "Unknown API endpoint"}, 404)
            return
        if "\x00" in relative:
            raise ValueError("Invalid static path")
        site_root = self.server.site.resolve()
        target = (site_root / relative).resolve()
        if not target.is_relative_to(site_root) or not target.is_file():
            self.send_json({"error": "Not found"}, 404)
            return
        if target.suffix.lower() not in {".html", ".css", ".js", ".mjs", ".json", ".svg", ".png", ".ico"}:
            self.send_json({"error": "File type not served"}, 404)
            return
        content = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mimetypes.guess_type(str(target))[0] or "application/octet-stream")
        self.send_header("Content-Length", str(len(content)))
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "SAMEORIGIN")
        self.send_header("Content-Security-Policy", "frame-ancestors 'self'")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

def serve(host: str = "127.0.0.1", port: int = 8765, *, root: Path = ROOT, state_path: Path | None = None) -> None:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("The private API binds to loopback only; use a separately secured reverse proxy for remote access")
    with runtime_lock(Path(state_path) if state_path is not None else default_path()):
        _serve_locked(host, port, root=root, state_path=state_path)


def _serve_locked(host: str, port: int, *, root: Path, state_path: Path | None) -> None:
    from threading import Event, Thread
    prepared = prepare_public_snapshot(root)
    store = Store(state_path)
    httpd = ApiServer((host, port), store=store, root=root)
    stop = Event()
    def schedule_loop() -> None:
        while not stop.is_set():
            worker = Store(state_path)
            try:
                scheduler_once(worker, root)
            except (OSError, ValueError, RuntimeError) as error:
                print("Private scheduler diagnostic: " + type(error).__name__, flush=True)
            finally:
                worker.close()
            if stop.wait(300):
                break
    thread = Thread(target=schedule_loop, name="phd-atlas-scheduler", daemon=True)
    thread.start()
    try:
        print(f"PhD Atlas private runtime listening at http://127.0.0.1:{port}/", flush=True)
        print("Public source projection initialized: " + str(prepared["records"]) + " records (" + prepared["data_mode"] + ").", flush=True)
        print("Opt-in scheduled AI workflows are checked every five minutes while the private runtime is running.", flush=True)
        httpd.serve_forever(poll_interval=0.5)
    finally:
        stop.set()
        httpd.server_close()
        store.close()
