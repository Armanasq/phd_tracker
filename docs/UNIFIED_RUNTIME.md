# PhD Atlas — unified application and private AI runtime

## Product boundary

One responsive application owns navigation for applications, operations, evidence, Copilot, agents, automations, run history and settings. The application is implemented in `site/index.html`, `site/app.js`, `site/modules/console.mjs`, `site/modules/operations.mjs`, and `site/workspace-v2.css`. The former `ai-studio.html` is a compatibility redirect, not a second application.

The public GitHub Pages deployment provides source-backed tracking and an optional browser-to-localhost inference adapter. It does not hold private API keys or expose a privileged execution backend. The private Python service serves the **same application** on loopback; that is where model configuration, personal applicant records and execution actually work.

```
Browser ── same UI and route table ─── PhD Atlas Python API (localhost)
   │                                     │
   │                                     ├── SQLite: provider, agent and workflow config
   │                                     ├── SQLite: private application state and audit
   │                                     ├── Private credential file or process env
   │                                     ├── SQL-first evidence + deterministic tools
   │                                     ├── Provider adapters: OpenAI-compatible/Azure/Anthropic
   │                                     └── LLM endpoint: local loopback or approved HTTPS
   │
   └── Public GitHub Pages (public snapshot + optional direct loopback model calls, no secrets)
```

## First-use model setup

Start the same-origin private service with `python -m phd_agents serve --port 8765` and open `http://127.0.0.1:8765/#settings`.

1. Select **Settings → Connections** and register a provider. For a locally running OpenAI-compatible server, supply its actual `/v1` base URL and exact model identifier. For Azure, select the v1 or deployment API adapter and provide the resource endpoint, deployment name and API version as applicable.
2. Supply the API key through private Settings or an environment variable. The model key is never returned in GET responses.
3. Select **Save, test & activate**. Registration alone does not make a model ready. The activation gate requires a real successful inference response.
4. For a remote/cloud provider, separately approve transmission of application evidence. This authorization is scoped to the selected provider and is reset if its configuration changes.
5. Copilot and agents automatically resolve their model from persisted routing configuration without including a provider selector in each request. The resolution order is: explicit request override, agent assignment, then workspace default. This precedence is implemented in `phd_agents/routing.py`.
6. The **Agent builder** assigns model routes and bounded deterministic tool allowlists. **Automations** compose 1–3 stages with optional recurring schedules. The scheduler still needs an independently running private timer or an explicit manual action.

There is no implicit fallback to a remote provider when a local model becomes unavailable. That would transmit applicant evidence to another service without the applicant's authorization. A failed model call produces an error and an auditable failed run.

## API contracts and state

| Route | Purpose | Side effects |
|---|---|---|
| GET `/api/bootstrap` | Configuration, status and user interface initialization | None |
| POST `/api/providers/setup` | Register a provider and optionally store a private credential | Private configuration write |
| POST `/api/providers/models` | Discover models from a selected endpoint | External catalog request, no applicant evidence |
| POST `/api/providers/probe` | Test actual inference with a synthetic diagnostic prompt | LLM request, possible cloud charge |
| POST `/api/providers/activate` | Set verified default and approve a cloud provider explicitly | Private configuration write |
| GET/POST `/api/settings` | Read or change persistent runtime and routing policy | Private configuration write on POST |
| GET `/api/routing` | Inspect resolved per-agent model routes | None |
| POST `/api/agents/run` | Execute deterministic tools and the resolved model | Model call, private audit event |
| POST `/api/workflows/run` | Run bounded sequential agents | Model calls, audit records |
| GET `/api/scheduler/preview` | Forecast workflow readiness and blocking reasons | None |
| POST `/api/scheduler/tick` | Execute eligible scheduled workflows | Model calls subject to approvals and budget |
| GET `/api/operations` | Read private referees, milestones, conflicts, work queue, research-fit signals | None |
| POST `/api/private/{kind}` | Upsert profile, referee, reference, milestone or evidence record | Private SQLite write |
| POST `/api/applications/{id}/update` | Update applicant state with optimistic concurrency | Private SQLite write |
| POST `/api/schedule` | Compute a conservative capacity scenario | None |
| GET `/api/metrics` | Measured calls, token use and latency | None |

The private store is SQLite, with schema and operations in `phd_agents/store.py`. The source snapshot remains independently generated and traceable to the workbook. Local browser drafts are legacy user-owned drafts, not implicitly synchronized with private application records. The Operations page operates on merged server records and requires explicit state changes.

## Research controls and evidence

The model receives an evidence pack generated from committed source records, owner-maintained records and allowlisted deterministic tools. Every generated reply is an unverified proposal. The application does not submit admissions applications, send faculty messages or mark referee uploads verified automatically.

The evidence work queue combines known missing cutoff clocks, unverified source status, document readiness, receipt gaps, referee dependencies and conflicting claims. Its priority is a transparent triage heuristic; it is neither a Bayesian admission predictor nor an independently validated opportunity rating. Evidence status remains owner-verified or source-verified only when the corresponding source supports it.

## Runtime and deployment constraints

The loopback server is a single-user application, not an authenticated production SaaS API. Saved provider credentials are permission-restricted local plaintext, not an HSM or encrypted secrets vault. Do not expose the built-in server directly to the internet.

An externally hosted authenticated edition would require a separate private backend with TLS termination, identity, authorization, secure secrets, per-user data isolation, CSRF/origin policy, rate limiting, background worker durability, cancellation and continuous monitoring. None of those capabilities is implied by the public Pages frontend.

Direct Bedrock/Vertex native authentication, autonomous Gmail ingestion, cloud-side recurring execution, private-backend model streaming, monetary cost estimation without verified pricing, and automatic external submissions are not implemented. Browser-local OpenAI-compatible SSE streaming is available separately, subject to model/browser support.

## Release verification

```bash
python -m pytest tests -q
python -m compileall -q scripts phd_agents
node --check site/app.js
node --check site/modules/console.mjs
node --check site/modules/operations.mjs
node tests/ai_studio_smoke.cjs
node tests/all_routes_audit.cjs
node tests/site_accessibility.cjs
```

The model integration browser test starts a synthetic local OpenAI-compatible model server and verifies registration, inference probing, activation, agent assignment, automatic routing and the private state-editing journey. The complete browser and accessibility audit remains a separate release gate; individual tests should not be reported as passed unless their CI results have been observed.

## Local state recovery

Private Settings offers database integrity diagnostics and a verified, owner-only SQLite backup. CLI equivalents: `python -m phd_agents diagnostics` and `python -m phd_agents backup --retain 7`. A backup excludes the separate provider credential file, and the application never uploads private SQLite backups to GitHub Pages. Direct restore requires stopping the local process; no remote overwrite API is provided.

## Request admission and diagnostics

The loopback API permits two concurrent inference-bearing HTTP requests by default (`PHDAI_MAX_CONCURRENT_INFERENCE=1..8`). It returns HTTP 429 when the configured capacity is exhausted; health and local-database diagnostics remain available. Every JSON response carries an opaque `X-Request-ID`. A per-process admission limit does not replace an authenticated multi-tenant service, global rate limiter or shared task queue.

## Production engineering reference

The [backend engineering and operations guide](BACKEND_ENGINEERING.md) specifies the exact request semantics, SQLite concurrency and recovery model, inference admission limits, scheduled cloud-call reservations, credential forwarding rules and remaining constraints.
