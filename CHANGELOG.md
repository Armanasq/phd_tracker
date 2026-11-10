# Changelog

Changes to the PhD Atlas application and its supporting tooling are recorded here. Source-data refreshes and individual PhD application status changes are tracked separately in the evidence ledger.

## Unreleased — 2026-11-10 (source provenance, 25-route UX and release verification)

- Added `#source-claims`, the 25th canonical route, with captured source inspection, exact-quote evidence capture, deterministic before/after text comparison, and owner interpretation reviews.
- Extended the private HTTPS observer with bounded visible HTML/plain-text extraction, SHA-256 fingerprinting, byte/text drift distinction, and explicit truncation; previously stored rows migrate without invented evidence.
- Added append-only claim and review ledgers. Candidate interpretations and owner decisions do not automatically verify university requirements, change applicant status, or submit applications.
- Scoped captured source quotes into local agent context as explicitly unverified `SRC-<id>` citations, with no fabricated semantic entailment or external action claims.
- Fixed evidence retention so source observations referenced by claims or reviews survive pruning of older uncited records.
- Added real-browser smoke paths for local source review, exact-quote capture, owner interpretation, persistence, and source-diff inspection; extended code-quality and Docker regression coverage.
- Replaced selective Pages asset hashing with a complete commit-bound static inventory, private-file rejection and full published-asset checksum certification; publishing fails when the deployed site contains inconsistent assets.
- Authenticated hosted cloud infrastructure, cross-platform provider certification and live institutional claim verification remain tracked as open release gates, not delivered production capabilities.

## Unreleased — 2026-11-10 (forkable inference and local deployment)

- Enabled explicit browser-to-loopback OpenAI-compatible inference from GitHub Pages, including model discovery, real inference probing, optional SSE streaming, cancellation and memory-only conversation state.
- Added a hosted Settings deployment guide separating browser-only chat, GitHub Actions batch AI and private Python agents. No cloud API key is embedded in the static frontend.
- Added a least-privilege Linux Docker Compose deployment with non-root execution, a read-only root filesystem, bounded temporary storage and project-scoped private volumes.
- Added `scripts/deployment_check.py` with fork/source, inference, private storage and hosted-mode checks. The unimplemented cloud full-stack mode fails explicitly.
- Extended CI with local-model security, integration and streaming tests; added a successful Docker runtime startup/health/bootstrap smoke workflow.
- Reconciled README, self-hosting guidance, architecture contracts and the security policy with the implemented boundaries.
- Synchronized the canonical `.github/README_TEMPLATE.md` with `README.md` after release tests detected a generated-file mismatch; future README rendering retains the documented deployment contract.
- Authenticated cloud hosting, optional OAuth login, cross-platform Docker deployment, durable cloud workers and license selection remain open in [Issue #7](https://github.com/Armanasq/phd_tracker/issues/7).

## Unreleased — 2026-11-09 (private backend integrity)

- Made applicant state updates atomically version-checked; conflicting writes now fail explicitly.
- Added exclusive opt-in scheduler claims, crash recovery, and reserved cloud-call budget.
- Added private SQLite health diagnostics, online verified backups, CLI recovery controls and Settings integration.
- Bounded inference concurrency, added request identifiers, and tightened request framing and loopback policy.
- Bound known vendor credential names to official provider hosts at request time, including legacy saved gateways.
- Added time-bounded provider verification and credential-rotation invalidation.
- Added SQLite-backed idempotency keys for manual model-request retries.
- Expanded concurrency, recovery, HTTP, cloud-policy and provider regression tests.
- Documented constraints in [backend engineering](docs/BACKEND_ENGINEERING.md).

## Unreleased — 2026-11-09 (source and release assurance)

- Added worksheet-level workbook inventory, source catalog, observed discovery errors and explicit distinction between tracked applications, research candidates, leads, exclusions and task records.
- Added filterable and exportable verification proof obligations, including unknown document readiness, exact-cutoff checks and missing receipt warnings.
- Removed silent display caps from important application, calendar, review and historical lists.
- Hardened CSV exports against spreadsheet formula evaluation and exposed more source context in application details.
- Extended deployment and CI with assurance tests, commit-bound release manifest and published asset verification.
- Corrected About metadata automation to report missing administration permission and verify live GitHub settings after an attempted update.

## 0.1.0 — 2026-11-09 (public preview)

### Public workspace
- Consolidated the tracker into one GitHub Pages interface with Applications, Actions, Contacts, Updates, Dashboard, Calendar, Pipeline, Compare, Verification, Sources, and Archive.
- Added source-aware deadline, document and submission preflight views, duplicate-route warnings, and research evidence exploration.
- Published a versioned JSON workspace projection from tracked sources; verification and unknown states are preserved rather than inferred.

### Private AI runtime
- Added a loopback-only Python backend, provider configurations for OpenAI-compatible local and cloud gateways, agent routing, explicit cloud-data disclosure consent, and opt-in scheduled workflows.
- Added SQLite-backed conversation history, application-scoped threads, deterministic relevance selection, returned evidence references, and model-run diagnostics.
- Separated public read-only Pages behavior from private applicant state and model credentials.

### Repository and delivery
- Introduced GitHub Pages deployment verification and continuous Python/JavaScript/browser checks.
- Moved detailed auto-generated research diagrams and operational evidence into a dedicated report, keeping the root README concise.
- Added canonical site metadata, a favicon, release documentation and repository-configuration guidance.

### Boundaries
- The 0.1.0 public preview did not provide browser-local inference, multi-user authentication, autonomous submissions, faculty email sending, native token streaming, or claim-level scholarly citation verification. The browser-local inference boundary was added in the 2026-11-10 unreleased changes above.
- Model-provider connectivity depends on user configuration and has not been verified against any user's private cloud deployment.
- Applications and deadline claims must be checked against original institutions before action.

The label *public preview* describes the release stage; it is not a certification of accuracy, eligibility or production security.
