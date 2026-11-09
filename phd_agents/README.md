# PhD Atlas private AI runtime

This opt-in Python 3.11+ service runs beside the existing public GitHub Pages tracker. It does not replace the workbook, source monitors, GitHub Issue owner controls, or public dashboard.

## Run

From the repository root:

```bash
python -m phd_agents serve --port 8765
```

Open http://127.0.0.1:8765/ai-studio.html. The service listens on loopback only and stores applicant edits and AI run output in `~/.local/share/phd-atlas/state.sqlite3` (or `PHDAI_PRIVATE_DIR/state.sqlite3`). Do not put this file in the public repository. For recurring AI jobs, invoke `python -m phd_agents scheduler-once` with your private machine's cron/systemd timer. An enabled workflow runs at most once per period, with run state persisted. The default workflows are disabled.

## Models

The model catalog includes editable examples for Ollama, vLLM/LiteLLM, OpenAI, Azure OpenAI, Anthropic, Gemini's OpenAI-compatible gateway, and OpenRouter. Model names and APIs change; verify your deployed models and parameters. Create custom providers from AI Studio.

```bash
export OPENAI_API_KEY=...
export ANTHROPIC_API_KEY=...
export AZURE_OPENAI_API_KEY=...
export GEMINI_API_KEY=...
export OPENROUTER_API_KEY=...
python -m phd_agents catalog
```

Only set credentials for the providers you use. Keys are looked up by environment-variable name and never serialized to the catalog. Local HTTP endpoints must be loopback addresses. Remote endpoints must be HTTPS.

## Security and authority

The server is deliberately local-only and rejects cross-origin browser requests. Keep the port inaccessible from public networks; do not reverse-proxy this API without adding TLS, authenticated sessions, user isolation, request size restrictions and CSRF safeguards. If `PHDAI_API_TOKEN` is set, HTTP requests require `Authorization: Bearer <token>`; the bundled no-login UI does not supply it, so use an authenticated client in that configuration.

Cloud execution requires explicit consent per manual request. Scheduled workflows must separately enable cloud consent and remain disabled initially. Any text passed to a cloud provider may include source/application evidence and must be assessed by the user for confidentiality first. AI runs produce proposed analyses; they do not email referees, contact faculty, submit portals, or modify verified evidence. Owner application updates go to private SQLite and do not synchronize with GitHub's public workbook.

`GET /api/bootstrap` returns the local catalog, source-backed applications, agenda, runs and activity. `POST /api/catalog/{provider,agent,workflow}` registers configuration. `POST /api/agents/run`, `POST /api/workflows/run`, `GET /api/preflight/{id}`, `POST /api/capacity`, and `POST /api/applications/{id}/update` provide the core operations.

## Status

Implemented: provider-neutral model invocation, private catalog/state, 12 built-in agents, 11 workflows, deterministic preflight, task agenda, capacity screening, explicit owner updates, scheduled execution and persisted audit logs. Not implemented: automated portal submissions, verified end-to-end referee delivery, fully optimized cross-application scheduling, server-hosted multi-user authentication, live inbox OAuth, real-time push notifications, or universal research-source coverage.

## Extended private applicant operations

AI Studio includes separate views for referee requests, source-backed multi-clock milestones, contradictory evidence, lexical research alignment and capacity screening. These records are stored only in private SQLite, not in the public repository. Unknown document effort and exact cutoff times remain explicitly unknown.

The agents use a deterministic tool allowlist: `preflight`, `daily_agenda`, `deadline_clocks`, `referee_dependencies`, `evidence_disputes`, `research_alignment`, `capacity_screen`, and `discovery_health`. Custom agents select any safe subset. Custom workflows can chain 1–3 registered agent stages; each stage's unverified output feeds subsequent stages as untrusted context. Scheduled cloud workflows require explicit stored consent.

API endpoints: `GET /api/operations`, `POST /api/private/{referee,reference,milestone,evidence,profile}`, `POST /api/private/{kind}/{id}/delete`, `POST /api/schedule`. No API route sends external mail, contacts faculty, changes the public tracker, or submits a portal.

## Research evidence tool

The `paper_radar` tool supplies titles, original arXiv links, publication dates and research topics from the repository's committed research radar. Papers do not establish faculty availability or recruitment. The `proof_obligations` tool prioritizes unresolved deterministic preflight checks; neither tool invents admission probabilities or externally verified claims.

## Connection setup and diagnostics

The AI Studio **Models & providers** page now separates `needs_setup`, `ready_to_test`, `reachable`, `responded`, and `failed` status. No provider is marked connected until an explicit request succeeds. Use **Discover models** to query the provider model catalog without sending applicant data, then **Select model** and **Test inference** to validate chat compatibility. Cloud inference diagnostics may incur charges. Statuses are stored in the local SQLite database and invalidated whenever the provider configuration is edited.

Select **Settings & diagnostics** to persist the default provider, default research agent, IANA timezone, and maximum scheduler attempts per check. Cloud disclosure authorization is never disabled globally.

For local Ollama, start the Ollama service and pull an available model; choose that model identifier in AI Studio. For vLLM, LiteLLM, LM Studio, or another OpenAI-compatible endpoint, point the custom provider at an actual loopback `/v1` API. The default vLLM/LiteLLM port is an example, not a guarantee that a server is running.

Cloud credentials must be supplied to the **private runtime environment**, not pasted into GitHub Issues or the public site. Use the environment variable shown on each provider card, for example `OPENAI_API_KEY` or `AZURE_OPENAI_API_KEY`. The server does not store API-key values, and a configured key does not imply a successful provider response.

Azure has two supported routes. `azure` uses the v1 base `https://YOUR_RESOURCE.openai.azure.com/openai/v1`. `azure_deploy` uses the deployment-based base `https://YOUR_RESOURCE.openai.azure.com` and a dated API version, with the model field naming the deployment. Model-list discovery does not establish which Azure deployment is authorized for inference. The supported deployment-based route is documented by Microsoft for `/openai/deployments/{deployment}/chat/completions?api-version=...`.

OpenAI-compatible custom providers can also point at supported model gateways. Direct native AWS Bedrock authentication, direct Google Vertex authentication, credential vault integrations, full provider streaming and automatic remote service deployment are not implemented; use a locally managed compatible gateway where appropriate.

## Opt-in recurring execution on Linux

The repository now includes a systemd user-service installer for the private runtime and twice-daily scheduler. Review the generated units before installing:

```bash
python scripts/install_ai_runtime.py
python scripts/install_ai_runtime.py --install
python scripts/install_ai_runtime.py --enable --overwrite
```

The installer generates a **private empty environment file** at `~/.config/phd-atlas-ai/provider.env` with mode `0600`. Add only the provider keys you intend to use. Units reference that file but never copy its contents into Git. `--install` writes units without enabling them. `--enable` activates the private loopback server and timer for this machine. A running timer is not an enabled workflow: each automated workflow remains disabled until approved in AI Studio. On non-systemd platforms, schedule `python -m phd_agents scheduler-once` with an OS-appropriate private scheduler.

For production operations, keep the SQLite database outside the public checkout, audit outgoing model context, monitor individual workflow failures and protect the host. The default HTTP service is **not** a publicly authenticated multi-user API.
