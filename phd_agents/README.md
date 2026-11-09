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

Cloud execution requires an approved provider-specific disclosure route or explicit consent for the individual request. Scheduled workflows must separately enable cloud consent and remain disabled initially. Any text passed to a cloud provider may include source/application evidence and must be assessed by the user for confidentiality first. AI runs produce proposed analyses; they do not email referees, contact faculty, submit portals, or modify verified evidence. Owner application updates go to private SQLite and do not synchronize with GitHub's public workbook.

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

Cloud credentials must be supplied only to the **private runtime**, never to public GitHub Issues, Pages or the source repository. A provider card now offers **Set API key**: it posts the secret to the loopback-only backend and stores it in `PHDAI_PRIVATE_DIR/provider-credentials.json`, defaulting to `~/.local/share/phd-atlas/provider-credentials.json`. The file is mode `0600`, stored outside the repository, and is **not encrypted at rest**. Values are not returned in API responses or included in catalog exports. Alternatively, configure the matching environment variable, such as `OPENAI_API_KEY` or `AZURE_OPENAI_API_KEY`; environment values take precedence. A saved key is only configuration, not proof of successful authentication or inference. Use an OS-backed secrets manager instead for higher-assurance deployments.

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

## Inference telemetry and cloud automation caps

The private **Run history** view now reports per-provider model calls, failed calls, actual token usage and observed request latency. The underlying `GET /api/metrics` returns bounded telemetry. Missing usage values are not inferred; monetary costs remain unknown unless verified pricing is separately supplied.

Settings include `max_cloud_model_calls_per_day`, initially **0**. This disables unattended cloud model calls even when a workflow is explicitly enabled and cloud disclosure permission is granted. Increase the cap only after reviewing the desired workflow stages, data disclosure and model pricing. A 3-stage workflow consumes up to three model-call slots. The scheduler uses the configured IANA time zone for daily periods and refuses new stages when the approved daily quota would be exceeded. Manual cloud calls still require confirmation.

A model invocation failure is recorded as a failed audit run without storing the full prompt, model text or credential.

## Private credential storage policy

The local key-entry form is an opt-in convenience for single-user development machines. It is not equivalent to a hardened multi-user secret vault. The credential file is plaintext JSON protected by local file permissions; protect workstation backups and home-directory access. The backend refuses to read a credential file whose permissions grant group or other access and replaces values atomically. Removing a key from the form removes the stored value but does not unset an environment-provided value. Never use this service as a publicly reachable credentials API without a separately authenticated reverse proxy, TLS, CSRF defenses and a professional secrets backend.

## Unified workspace and automatic inference routing

The single-page application is served at `http://127.0.0.1:8765/`. In **Settings → Connections**, register an OpenAI-compatible endpoint, including a local vLLM/LiteLLM/LM Studio HTTP `/v1` base URL or an Azure/OpenAI HTTPS endpoint, provide any required credential, run **Test inference**, and **Activate**. A successful test and activation persist the selected default route in private SQLite. Subsequent agent calls omit `provider_id` and the server resolves the saved provider automatically.

`agent_routes` optionally maps agent IDs to another registered provider. `approved_cloud_providers` records explicit model-specific applicant-data disclosure approval. Every newly approved cloud route must have a successful inference test; editing a provider resets its test and removes its automatic cloud approval. `POST /api/providers/activate` refuses untested providers and requires `allow_cloud_data=true` for cloud providers. Manual requests with an explicit provider override remain supported for backward compatibility.

Cloud approval is scoped to the selected provider. It is not permission to contact faculty, send email, submit an application, or connect unrelated remote accounts. The daily cloud scheduler call cap remains independent of approval and defaults to zero.

Public GitHub Pages continues to provide a read-only research tracking surface. The private backend serves the identical workspace with functioning Settings and agent execution. API keys and private state never become part of the public Pages artifact.


## Embedded Atlas assistant: private conversation and evidence API

Atlas Lens runs on public Pages in read-only mode and on the private loopback server with model inference and saved conversations. API keys, messages, private applicant state and model outputs are never deployed to GitHub Pages.

| Route | Purpose |
| --- | --- |
| GET /api/assistant/bootstrap | Lightweight provider states, agent-specific routing, settings and recent private conversation metadata |
| GET /api/conversations | Recent conversation metadata |
| GET /api/conversations/{id} | Messages with linked model-run metadata and evidence references |
| POST /api/conversations/{id}/delete | Remove a private conversation and its messages |
| POST /api/agents/run | Run an agent; optional conversation mode persists the request and answer |

The first conversational request contains agent_id, input_text and conversation=true, with an optional application_id. Subsequent turns add the returned conversation_id, sending only the new applicant question rather than duplicating transcript text in the prompt. The server reads up to six previous scoped messages (750 characters each) from local SQLite. Threads are bound to one agent and one application; scope mismatches are rejected.

For an unscoped request, deterministic weighted lexical ranking supplies up to seven relevant application records. If there are no lexical matches, the method is labeled deadline_fallback and the nearest open recorded deadlines are supplied instead. A selected application is pinned. The response includes evidence_refs, retrieval_method, route_source, source_as_of and model/run telemetry. Retrieved records represent context **supplied to the model**, not independently verified claim-level citations.

The widget reflects the chosen agent's configured provider and its recorded inference-verification state, not the workspace default model. Changing a provider resets its verification and automatic cloud approval. Provider probes are historical connection evidence, not guarantees of current uptime.

The backend handles simultaneous local HTTP requests using request-local SQLite connections. The browser's Stop waiting action aborts its HTTP request but may not cancel the upstream model call; finished calls are still logged. Native token streaming, shared multi-user authentication, cross-device sync and provider-wide OAuth are not implemented.

Only an opaque thread ID is retained in local browser storage. Conversation content stays in the private SQLite database. If PHDAI_API_TOKEN is set, the browser UI cannot provide that token automatically; use an authenticated client or an appropriately secured front-end integration.
