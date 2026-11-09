# Private backend: operational contracts and recovery

PhD Atlas separates a public, read-only GitHub Pages application from an optional single-user Python runtime. The Python runtime serves the same UI over HTTP on loopback, manages applicant state in SQLite and calls local or consented cloud models. It is not an authenticated multi-tenant service.

## Architecture and ownership

| Component | Responsibility | Guarantee |
| --- | --- | --- |
| **phd_agents/server.py** | Local HTTP request admission and routing | Exact loopback Host and Origin; bounded JSON requests; typed HTTP outcomes |
| **phd_agents/store.py** | Private SQLite, applicant changes, evidence, agent runs and conversations | Atomic version checks, recoverable scheduler execution claims and verified backups |
| **phd_agents/engine.py** | Research agents, workflows and scheduler | Source context before interpretation; manual/cloud consent; no automatic portal submission |
| **phd_agents/providers.py** | Model-provider requests | Vendor-key host binding, no redirects, bounded response sizes |
| **phd_agents/connectivity.py** | Model probes and catalog discovery | A saved probe expires after 24 hours and is invalidated on credential rotation |
| **phd_agents/routing.py** | Assignment of providers to research agents | Configured model routes independent of agent specialization |
| **phd_agents/operations.py** | Application proof and dependency analysis | Missing facts remain unknown rather than silently completed |

## Running and inspecting the private runtime

Run from the repository root with Python 3.11+ and dependencies in requirements-intelligence.txt.

| Command | Effect |
| --- | --- |
| **python -m phd_agents serve --port 8765** | Start the same-origin private application |
| **python -m phd_agents diagnostics** | Check SQLite integrity, WAL state, file permissions, active scheduler claims and backup count |
| **python -m phd_agents backup --retain 7** | Create an owner-only, integrity-checked SQLite backup |
| **python -m phd_agents verify-backup FILENAME --sha256 DIGEST** | Validate a generated backup without loading or changing the current database |
| **python -m phd_agents restore-backup FILENAME --sha256 DIGEST --confirm** | Offline verified restore after stopping the private runtime; preserve a pre-restore safety copy |
| **python -m phd_agents scheduler-once** | Evaluate opted-in scheduled workflows once |
| **python -m pytest tests -q** | Run Python backend and integration regression tests |
| **node --check site/modules/console.mjs** | Validate the private Settings frontend JavaScript |

Private state defaults to ~/.local/share/phd-atlas/state.sqlite3; PHDAI_PRIVATE_DIR overrides its directory. Keep that directory outside any public repository. The SQLite file and backup files require mode 0600; the backup directory requires mode 0700.

## API response semantics

| HTTP status | Meaning |
| --- | --- |
| **200** | Operation succeeded; a model answer remains a proposal rather than an external action |
| **400** | Input validation failure |
| **403** | Local origin, authorization or cloud-disclosure policy denied request |
| **404** | Unknown API/private resource |
| **409** | Optimistic-write conflict, duplicate running request, or conflicting idempotency key |
| **429** | Inference admission limit reached; retry later |
| **502** | External provider or local execution failure |

JSON responses include an opaque X-Request-ID header. Manual agent/workflow inference accepts an optional Idempotency-Key (16-128 characters); identical completed requests replay the response for 24 hours without another model call. In-flight duplicate keys return 409. The private UI generates UUID request keys. Crashes after remote provider processing can still result in another charge.

Expensive HTTP requests share a per-process inference admission semaphore, default two active requests (PHDAI_MAX_CONCURRENT_INFERENCE, allowed 1-8). Health, diagnostics and local configuration requests remain available during inference. These are non-streaming model requests, not simulated streamed tokens.

## SQLite and scheduler invariants

- Applicant updates carry an expected version; the last SQL write matches both identity and expected version. Conflicts never silently overwrite another write.
- A status change to Submitted requires explicit applicant confirmation. No backend route submits university applications or contacts faculty.
- Scheduled workflows are opt-in. A period is claimed atomically before model execution; concurrent ticks return already-running instead of invoking another model.
- Abandoned execution claims expire after 15 minutes. A failed run releases its claim for a retry. Recovery is at-least-once rather than exactly-once external inference.
- Scheduled cloud workflows require both cloud-context disclosure consent and a configured daily call limit. Concurrent in-flight scheduled calls reserve their allowance before execution.
- Known vendor API-key variable names are bound to the official vendor host. Other remote gateways must use a separate, dedicated API-key variable. This is enforced for legacy configurations at request time.
- A successful model catalog response does not certify inference. Successful inference probes expire for UI readiness after 24 hours; credential rotation requires reverification.
- Unknown deadlines, portal cutoffs, funding eligibility, referee responses and submitted receipts remain explicit evidence gaps.

## Recovery procedure

Use the private Settings panel or the backup CLI. The SQLite online-backup operation validates the copy, computes a SHA-256 digest, rotates retained copies and does not send the backup off-machine. It includes applicant state, run logs, settings, evidence and conversations, but excludes provider-credentials.json.

To restore on Linux or another POSIX system, stop the private runtime, select a generated backup filename, run `verify-backup` with the SHA-256 from the original backup report, then invoke `restore-backup FILENAME --sha256 DIGEST --confirm`. The offline command refuses unsafe file permissions, symlinks, corrupt or schema-incompatible backups, a running private service, and any existing SQLite journal sidecars. It stages and verifies the restored database before an atomic replacement, saves the former state as a separate pre-restore backup, and leaves the credential file untouched. Restart the service and run diagnostics. The lock is advisory for the provided Python server and restore commands; external SQLite clients must also be stopped. There is intentionally no HTTP restore endpoint. A same-host backup is not off-host disaster recovery; securely export an encrypted copy for that purpose.

## Release quality gates

- Run Python and JavaScript tests for every backend or private frontend change.
- Verify the exact main-branch GitHub Actions code-quality run before calling the change tested.
- Private Settings changes also require browser integration and accessibility smoke coverage. The public Pages workflow validates static content but cannot prove external model connectivity.
- New provider adapters require real integration verification when live credentials are available, but no production credential should enter public CI logs.
- Inspect any newly published data files and screenshots for private information.

## Explicit limitations

- Local, single-user loopback HTTP is not a secure hosted multi-user API. Authentication, authorization, TLS, user isolation, logging controls and service-level objectives are not implemented for an Internet deployment.
- Provider credentials can reside in a permission-restricted local plaintext file or process environment; no KMS/HSM-backed vault is provided.
- Custom cloud-host validation does not pin DNS resolution or enforce an egress allowlist.
- Model transports do not currently support true token streaming or interruptible provider cancellation.
- The runtime scheduler only operates while the private service or its external scheduler command is running.
- No portal submission, mail sending, live university eligibility decision or guarantee of complete opportunity discovery is available.
- A green test run does not prove correctness of individual admission facts or real-world credentials.
