from __future__ import annotations

import json
import mimetypes
import os
import re
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, unquote, urlsplit

from .catalog import agent_spec, provider_spec, workflow_spec
from .domain import agenda, plan_capacity, preflight, today_in
from .operations import evidence_conflicts, milestones_for, referee_matrix, research_fit_signals, resource_schedule
from .providers import invoke
from .calendar import line_items
from .engine import catalog, owner_records, run_agent, run_workflow, scheduler_once, selected
from .store import ConflictError, Store

ROOT = Path(__file__).resolve().parents[1]
SITE = ROOT / "site"

class ApiServer(HTTPServer):
    def __init__(self, address: tuple[str, int], *, store: Store, root: Path):
        super().__init__(address, ApiHandler)
        self.store = store
        self.root = Path(root)
        self.site = self.root / "site"

class ApiHandler(BaseHTTPRequestHandler):
    server: ApiServer

    def log_message(self, format: str, *args) -> None:
        return

    def allowed(self) -> bool:
        host = self.headers.get("Host", "")
        address = host.split(":")[0].lower()
        if address not in {"127.0.0.1", "localhost", "[::1]"}:
            return False
        origin = self.headers.get("Origin", "")
        if origin:
            origin_parts = urlsplit(origin)
            if origin_parts.scheme != "http" or origin_parts.hostname not in {"127.0.0.1", "localhost"} or origin_parts.port != self.server.server_port:
                return False
        token = os.environ.get("PHDAI_API_TOKEN", "")
        if token:
            import hmac
            expected = "Bearer " + token
            if not hmac.compare_digest(self.headers.get("Authorization", ""), expected):
                return False
        return True

    def send_json(self, value: object, status: int = 200) -> None:
        raw = json.dumps(value, ensure_ascii=False, default=str).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("X-Frame-Options", "DENY")
        self.end_headers()
        self.wfile.write(raw)

    def payload(self) -> dict:
        length = int(self.headers.get("Content-Length", "0"))
        if length <= 0 or length > 60_000:
            raise ValueError("Request must contain 1–60000 bytes")
        if self.headers.get("Content-Type", "").split(";")[0] != "application/json":
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
        except (OSError, RuntimeError) as error:
            self.send_json({"error": str(error)[:220]}, 502)

    def do_GET(self) -> None:
        self.dispatch("GET")

    def do_POST(self) -> None:
        self.dispatch("POST")

    def do_OPTIONS(self) -> None:
        self.send_json({"error": "Cross-origin requests are disabled"}, 405)

    def get_route(self, path: str) -> None:
        store = self.server.store
        if path == "/api/health":
            self.send_json({"status": "ok", "mode": "loopback_private", "ai_side_effects": "none"})
        elif path == "/api/bootstrap":
            source, records = owner_records(store, self.server.root)
            today = today_in(source.get("timezone", "Europe/London"))
            self.send_json({"catalog": catalog(store), "meta": source.get("meta", {}), "as_of": source.get("as_of"),
                            "records": records, "agenda": agenda(records, today, 40),
                            "runs": store.runs(30), "activity": store.activity(30),
                            "providers_status": source.get("providers", []),
                            "security": {"local_only": True, "credentials": "environment variables", "auto_application_submission": False}})
        elif path == "/api/calendar.ics":
            source, records = owner_records(store, self.server.root)
            events = milestones_for(records, store.items("milestone"), today_in(source.get("timezone", "Europe/London")))
            body = line_items(records, events, store.items("reference")).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/calendar; charset=utf-8")
            self.send_header("Content-Disposition", 'attachment; filename="phd-atlas-private.ics"')
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif path == "/api/operations":
            source, records = owner_records(store, self.server.root)
            today = today_in(source.get("timezone", "Europe/London"))
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
            self.send_json(preflight(record, today_in(source.get("timezone", "Europe/London"))))
        else:
            self.static(path)

    def post_route(self, path: str, data: dict) -> None:
        store = self.server.store
        root = self.server.root
        if path == "/api/providers/probe":
            provider = selected(catalog(store)["providers"], data["provider_id"], "provider")
            if not provider["local"] and data.get("cloud_consent") is not True:
                raise PermissionError("Cloud provider testing requires explicit disclosure consent")
            response = invoke(provider, "Answer with one short sentence.", "Respond with the exact text: Provider connection successful.")
            self.send_json({"status": "responded", "provider_id": provider["id"],
                            "model": response.model, "response": response.content[:600],
                            "usage": response.usage})
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
                self.send_json({"saved": True, "entry": store.put_item(kind, data)})
            elif len(parts) == 3 and parts[-1] == "delete":
                self.send_json({"deleted": store.delete_item(parts[0], unquote(parts[1]))})
            else:
                self.send_json({"error": "Unknown private record route"}, 404)
        elif path == "/api/schedule":
            source, records = owner_records(store, root)
            today = today_in(source.get("timezone", "Europe/London"))
            profile = (store.items("profile") or [{}])[0]
            hours = data.get("hours_per_week") or profile.get("hours_per_week")
            if hours is None:
                raise ValueError("Configure available hours per week in your private applicant profile")
            self.send_json(resource_schedule(records, today, hours, profile))
        elif path == "/api/agents/run":
            self.send_json(run_agent(store, root,
                                     agent_id=data["agent_id"], provider_id=data["provider_id"],
                                     application_id=data.get("application_id"), input_text=data.get("input_text", ""),
                                     cloud_consent=data.get("cloud_consent") is True))
        elif path == "/api/workflows/run":
            self.send_json(run_workflow(store, root,
                                        workflow_id=data["workflow_id"], provider_id=data["provider_id"],
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
                if validated.get("provider_id") not in provider_ids:
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
            self.send_json(plan_capacity(records, today_in(source.get("timezone", "Europe/London")), hours))
        elif path == "/api/scheduler/tick":
            self.send_json({"results": scheduler_once(store, root)})
        else:
            self.send_json({"error": "Unknown API endpoint"}, 404)

    def static(self, path: str) -> None:
        relative = unquote(path).lstrip("/") or "index.html"
        if relative.startswith("api/") or "\x00" in relative:
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
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(content)

def serve(host: str = "127.0.0.1", port: int = 8765, *, root: Path = ROOT, state_path: Path | None = None) -> None:
    if host not in {"127.0.0.1", "localhost"}:
        raise ValueError("The private API binds to loopback only; use a separately secured reverse proxy for remote access")
    from threading import Event, Thread
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
        print(f"PhD Atlas private runtime listening at http://127.0.0.1:{port}/ai-studio.html", flush=True)
        print("Opt-in scheduled AI workflows are checked every five minutes while the private runtime is running.", flush=True)
        httpd.serve_forever(poll_interval=0.5)
    finally:
        stop.set()
        httpd.server_close()
        store.close()
