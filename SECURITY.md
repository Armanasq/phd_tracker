# Security policy

## Supported deployment model

PhD Atlas is a public static application with optional browser-to-loopback inference and a separate single-user, loopback-only Python runtime. Neither GitHub Pages nor the private runtime constitutes an authenticated multi-user SaaS product.

| Component | Security boundary |
| --- | --- |
| GitHub Pages | Public HTML, JavaScript and committed evidence projections; optional explicit browser-to-loopback inference |
| Browser-local inference | HTTP loopback only, no credentials, no remote model origins; browser CORS and Local Network Access permissions required |
| Private backend | HTTP on loopback; not suitable for direct Internet exposure |
| Linux Docker runtime | Host-network loopback-only server, non-root process, per-installation isolated state volume; not multi-user |
| Provider credentials | Environment variables or a user-owned local file; never committed |
| Local state | SQLite outside the repository; not synced automatically |
| Cloud inference | Explicit provider approval before sending application context |

Do not put API keys, tokens, personal correspondence, unredacted candidate documents, or sensitive research material in GitHub Issues, pull requests, screenshots, or committed `data/` files. Check source excerpts and publication artifacts for private information before merging.

## Report a security issue

Do not open a public issue containing a working exploit, secret, or sensitive personal data. Use the repository's private vulnerability reporting feature under **Security** if it is enabled; otherwise contact the maintainer through a non-public channel before disclosing details.

## Deployment hardening

Keep the private service bound to `127.0.0.1`. Do not expose its API with an unauthenticated reverse proxy. Publicly hosting it requires independent work on authentication, authorization, TLS, CSRF controls, user isolation, audit access and secure secret storage.

The presence of automated tests or successful deployment workflows does not establish a complete security review.

## Model-provider credential forwarding

Built-in vendor API-key environment variables are bound to their respective official provider hostnames. Custom gateways must use a dedicated, isolated `*_API_KEY` variable, and the outbound request adapters validate this binding even for legacy persisted providers. Local HTTP inference is permitted only on loopback; remote self-hosted endpoints require HTTPS and explicit cloud-data disclosure approval. Redirects are rejected. The service is intended for a trusted single user and does not provide DNS-pinned egress filtering or a secure multi-user secret manager.

## Browser-local inference and origin isolation

The hosted browser adapter accepts only `http://localhost:<port>/v1`, `http://127.0.0.1:<port>/v1`, or `http://[::1]:<port>/v1`. It sends no credentials or private SQLite state. Only explicitly entered prompts and selected public record fields are sent. The adapter retains conversation history in memory; nonsecret model settings may be stored in browser storage.

Allow only the Pages origin in a local server's CORS policy, rather than using wildcard origins. Local Network Access requirements vary by browser and version, so test the intended client. Other applications sharing the same browser origin can access same-origin browser storage regardless of application-path prefixes; browser storage keys are not access control.

## Independent forks and secrets

Forks must supply their own GitHub Actions secrets and review every public-data source before publication. Linux Docker deployments must set unique `PHD_ATLAS_COMPOSE_PROJECT` values to avoid reusing private SQLite/credential volumes. The `.env` file, local database, backups, credential files and personal applicant documents must never be committed or uploaded to Pages. The local credential file is permission-restricted but **not encrypted at rest**.

No cloud deployment mode or login screen is considered production-ready until its server-side identity, authorization, storage isolation, CSRF, rate limits and credential boundaries are independently verified. See [deployment architecture](docs/DEPLOYMENT_ARCHITECTURE.md).

## Institutional source text and provenance

The private, opt-in HTTPS source observer retains at most 24,000 characters of normalized public-source visible text per fetched observation. Extracted excerpts are kept in local SQLite, not on GitHub Pages; query strings, credentials and redirect targets are rejected by the existing observer transport. Public-page text is **untrusted** even when a reviewer copies an exact quotation. The source excerpt, its SHA-256, an owner interpretation decision and an AI citation do **not** independently prove that a deadline, admission condition or recruitment status is current. Nothing in this workflow automatically edits applicant state, writes to an external portal or sends communications.

Source observations referenced by captured claims or review events are retained beyond the uncited-history pruning window. This improves traceability but also increases private state lifetime: review backup retention, lawful data ownership and disposal practices before collecting large numbers of third-party pages. Do not collect login-dependent student records or private application portals through this public-source adapter.

## Pages artifact integrity

The Pages pipeline rejects recognized credential files, private SQLite databases and symlinks from its static bundle, creates SHA-256 checksums for all published files and verifies downloaded assets against the commit-bound manifest. These are useful release-integrity controls, **not** exhaustive secret scanning or evidence-truth certification. A fork owner must still review Git history, static inputs and any public data before publication.

### Static asset allowlist

Release generation allows only ordinary static asset formats (HTML, JavaScript, CSS, JSON, XML, Markdown, text, supported images/fonts and WebAssembly), and rejects hidden directories, recognized private/credential/backup paths, database auxiliary files, arbitrary logs, spreadsheets and other unexpected artifacts. This is a file-boundary check rather than content-level secret detection: private values can still be embedded in an otherwise valid JSON or JS file, so independent source-data review remains mandatory for each public fork.
