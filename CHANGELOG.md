# Changelog

Changes to the PhD Atlas application and its supporting tooling are recorded here. Source-data refreshes and individual PhD application status changes are tracked separately in the evidence ledger.

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
- The site does not provide public model inference, multi-user authentication, autonomous portal submissions, faculty email sending, native token streaming, or claim-level scholarly citation verification.
- Model-provider connectivity depends on user configuration and has not been verified against any user's private cloud deployment.
- Applications and deadline claims must be checked against original institutions before action.

The label *public preview* describes the release stage; it is not a certification of accuracy, eligibility or production security.
