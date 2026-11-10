# PhD Atlas — deployment and trust architecture

**Status:** implementation contract and gap ledger, reviewed 2026-11-10. Only components explicitly marked *implemented* are available. The public static site is not an authenticated backend.

## Deployment and capability matrix

| Mode | UI | Model inference | Agents and tools | Private durable state | Authentication |
| --- | --- | --- | --- | --- | --- |
| GitHub Pages | Static Pages | None unless local model is configured | Deterministic browser features only | Browser-local, no cross-device sync | Not required; no privileged API |
| Pages + local model | Static Pages | Browser to HTTP loopback OpenAI-compatible Chat Completions | Direct inference only; no Python tools | Session-only conversation; nonsecret model selection stored locally | Browser network permission and server CORS |
| Pages + GitHub Actions | Static Pages + asynchronous job | Opt-in HTTPS cloud model in GitHub Actions | Validated public-data verification triage | Validated public outputs committed to fork | GitHub Actions environment-scoped secrets |
| Local Python | Same UI on loopback | Server-owned local/cloud adapters | Agent catalog, deterministic tools, bounded workflows, scheduler | Private local SQLite + separate credential file | Single-owner loopback origin; optional API token for external client |
| Local Docker (Linux) | Same UI on host loopback | Server-owned local/cloud adapters | Same Python workflow runtime | Per-installation Compose named volumes | Same loopback boundary; not public internet |
| Hosted cloud full stack | Not implemented | Not implemented | Not implemented | Not implemented | Not implemented |

Model inference success does not establish source truth, admissions eligibility, completed external actions, or permission to disclose private data. Features requiring a privileged backend must be disabled or accompanied by a clear route to a supported runtime.

## Runtime topology and authority

```text
fork owner -> source-controlled public evidence -> GitHub Actions -> static Pages
                                                       |
                                                    Browser
                                                       |
                     +-------------------------+-------+-------------------+
                     |                         |                           |
                 browser-local            HTTPS Actions             private Python
                 model inference          batch results             same-origin API
                     |                                                     |
           OpenAI-compatible /v1                                 SQLite / tools / jobs
           HTTP loopback only                                    env/private credentials
```

The browser-local model path cannot execute Python tools, schedule background work, or access GitHub Actions secrets. A cloud model used by the Python API runs from the user's configured private runtime, not from static Pages. No browser code should inject cloud API keys into JavaScript, localStorage, fetch headers, or static environment variables.

## Fork isolation and public data

- Each fork starts with an empty public starter dataset until its owner supplies and reviews `data/user_opportunities.json`, selects source mode, and republishes.
- Every record published through GitHub Pages or GitHub Actions is public. Application notes, receipts, provider keys, personal credentials and SQLite files are excluded from public projections.
- A browser draft is device-local, not an authenticated private database. Clearing browser storage may delete it; export before changing devices.
- Local clone state is scoped to the repository identity and checkout. Docker requires a distinct `PHD_ATLAS_COMPOSE_PROJECT` per instance to avoid reusing private volumes.
- A fork does not inherit GitHub Actions secrets, API credentials, OAuth approvals, or private database contents from the source repository.
- Edits to private SQLite do not automatically update public workbook evidence. Publishing requires an explicit reviewed export.

## First-run owner workflow

1. Fork and select repository visibility and a reviewed source-data policy.
2. Run `python scripts/deployment_check.py --mode pages` or another supported mode. An exit code of 0 indicates absence of known structural blockers, **not** a verified live deployment.
3. Publish GitHub Pages through the fork's Actions workflow. Confirm instance metadata and the generated workspace snapshot.
4. Choose the inference boundary:
   - Direct loopback model: run Ollama, vLLM, or LM Studio and allow the actual Pages origin; then configure and test the `/v1` endpoint in hosted Settings.
   - Hosted Actions batch AI: opt in, configure a protected GitHub environment, set its secret and nonsecret endpoint variables, and run the hosted triage workflow.
   - Complete local agents: run the private Python runtime natively or use the Linux Docker configuration; configure models, test inference, and approve each cloud-data transmission.
5. Verify all requested actions using real status and output. Never interpret a provider preset or green CI as proof that the user's model is reachable.

## Cloud edition: required design before implementation

A production hosted edition cannot simply change the existing loopback server to listen on `0.0.0.0`. It must implement these separate, testable boundaries:

| Boundary | Required implementation and invariant |
| --- | --- |
| Edge | TLS termination, trusted proxy configuration, exact allowed origins, request size and rate limits |
| Identity | OIDC authorization-code/PKCE, validated issuer/audience/nonce, secure HTTP-only sessions, logout and expiration |
| Authorization | Owner and applicant identity, explicit resource membership, deny-by-default policy on every private API and worker operation |
| CSRF | Same-site cookies plus a verified CSRF mechanism on mutations; no wildcard credentialed CORS |
| Persistence | Transactional PostgreSQL data ownership, migrations, constraints and tested restore |
| Secrets | Server-only encrypted storage or managed secret store, rotation and strict provider/tenant scoping |
| Agent runtime | Durable queue, leases, idempotency keys, bounded retries, cancellation, checkpoints, concurrency and cost caps |
| Network egress | Explicit destination allowlists, redirect rejection, private-network/metadata denial and SSRF tests |
| Provenance | Immutable evidence references, source timestamps, review states and separate AI proposals |
| Observability | Request IDs, structured error codes, redacted logs, latency/tokens, health/readiness and operational alerts |
| Lifecycle | Backup and restore, schema migration, export/delete operations, cancellation and application ownership |
| Security testing | Cross-account isolation, origin/CSRF bypass attempts, token replay, prompt injection/tool-permission tests |

An OIDC login screen alone is not authentication. Authentication is complete only when API handlers and worker jobs enforce the same identity and authorization contracts. The legacy single-user SQLite runtime must not be represented as a multi-tenant hosted service.

### Proposed hosted APIs

- `GET /api/capabilities`: deployment mode, supported features, disabled reasons; never includes secrets.
- `GET /api/session`, `POST /api/session/logout`: session lifecycle and authenticated owner identity.
- `POST /api/providers`, `POST /api/providers/{id}/probe`: credential-bound provider configuration and real inference health.
- `POST /api/agent-runs`, `GET /api/agent-runs/{id}`, `POST /api/agent-runs/{id}/cancel`: idempotent asynchronous runs and verifiable states.
- `GET /api/events`: authenticated SSE event stream with reconnection and bounded retention.
- `GET /api/exports`, `POST /api/imports`: signed, versioned migrations with explicit owner approval.

These are proposed contracts, **not implemented endpoints**. Keep request/response types and failure semantics consistent with the existing deterministic domain layer before adding external services.

## Release acceptance

1. A new fork publishes an empty or independently supplied source dataset without inherited applicant records.
2. A browser-only user can test a local model and receive a text response without exposing credentials, with a clear fallback when CORS or local-network permissions prevent connectivity.
3. A Linux user can start the private Docker runtime; health, the UI, and an owner-scoped database remain functional after process restart.
4. A GitHub Actions owner can configure an environment secret and run sanitized batch inference without exposing key values or private applicant notes.
5. Hosted-cloud mode is reported unavailable until sessions, tenant isolation, secure storage, durable workers and end-to-end security tests pass.
6. Every release includes source-linked run logs and an observable artifact tied to the deployed commit.

Related documentation: [SELF_HOSTING.md](SELF_HOSTING.md), [DOCKER_LOCAL.md](DOCKER_LOCAL.md), [HOSTED_ACTIONS_AI.md](HOSTED_ACTIONS_AI.md), [UNIFIED_RUNTIME.md](UNIFIED_RUNTIME.md).

## Local workflow execution audit

Multi-stage agent workflows now resolve and verify every model route before inference, explicitly freeze the selected provider ID for each stage, and persist a versioned `workflow_summary` event. Successful runs record the ordered stage run IDs and provider route IDs without duplicating full model texts; a later-stage failure records a separate failed summary with its failed stage and completed stage IDs, then reports a recoverable audit reference. Partial stages remain unverified proposals. This is traceability for the local sequential runtime, **not** durable remote-job replay, automatic rollback, cancellation or authenticated hosted orchestration. Those capabilities remain tracked in [Issue #11](https://github.com/Armanasq/phd_tracker/issues/11).

## Versioned agent prompt contract

Private agent inference uses a deterministic `phd_evidence_analysis_v1` prompt contract: a compact shared policy and task-specific agent specialization, bounded JSON evidence and conversation history treated as untrusted data, explicit source-citation syntax and provisional-output requirements. The source/conversation JSON escapes angle brackets to prevent literal spoofing of structural delimiters. Every private agent run records the contract ID and SHA-256 of its system-policy text, but not a duplicate of the applicant request or complete evidence context in the audit record. These identifiers enable regression comparison without pretending that prompt syntax alone proves model compliance. Tests cover injection-shaped excerpts, invalid JSON and token-budget failures.

## Private model evaluation console

`#evaluations` is the 26th canonical route. It reads `GET /api/evaluations` from the local loopback runtime only. The deterministic report scans at most 500 recent `agent`, `workflow` and `workflow_summary` events and returns provider/agent attempt counts, observed failures, nearest-rank p50/p95 latency, recorded token totals, presence and counts of citation-ID audits, and separate workflow-stage outcomes. Model answers, applicant identifiers, prompts, private source quotes, provider errors and credentials are never included in the API response. Citation IDs only establish a pointer; **no semantic entailment or admissions outcome is measured**. Missing latency/tokens and missing citation audits are unknown rather than zero-quality evidence. The browser filters the recent subset without changing the global aggregates. This route does not run an LLM, schedule tests or prove external provider reliability.

### Scheduled execution uses the same adapter preflight

The scheduler preview and scheduler runner now check each stage's explicit model capability requirements before declaring a run due or reserving a schedule lease/cloud-call quota. Incompatible workflows show `model_capability_mismatch` with stage-specific blockers and are skipped without any model call, quota reservation or change to the last executed period. `workflow_plan.scheduled_policy_approved` is false when any stage cannot be executed by the selected adapter. This is a deterministic implementation guard, not live model capability certification.

## Provider-configuration fencing during local workflows

A manual multi-stage workflow fixes each stage's provider route with a deterministic SHA-256 fingerprint of its adapter, endpoint, model, credential-variable name, locality and inference parameters. Immediately before each stage's inference, the runner recomputes that fingerprint from the current private catalog and rejects a changed route. The failed workflow summary records only an error type, stage number, and prior proposal IDs rather than publishing applicant text or provider configuration. This is a local configuration-change guard; it does not freeze upstream model deployments, capture provider API keys, or make external vendor runs idempotent.
