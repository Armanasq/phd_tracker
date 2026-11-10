# Authenticated hosting security architecture

**Design status:** required contract, not implemented. The existing Python service accepts only loopback-origin requests and has a single-owner SQLite database. It must **not** be directly routed through a public reverse proxy or changed to listen on `0.0.0.0`.

## Security principals and trust boundaries

| Trust boundary | Required mechanism | Enforcement owner |
| --- | --- | --- |
| Browser → edge | HTTPS, HSTS, host allowlist, request-size budgets; forwarding headers accepted only from configured proxy IPs | Edge |
| Edge → application | OIDC authorization code with PKCE, exact issuer/audience/nonce/state validation, key-rotation-aware JWKS | Authentication adapter |
| Application session | Server-side opaque session ID, rotation on login, idle and absolute expiry, Secure/HttpOnly/SameSite cookies, safe logout | Session store |
| Mutation request | CSRF double-submit or synchronizer token with origin validation; deny credentialed wildcard CORS | API middleware |
| Private data access | Authenticated actor, immutable tenant ID, tenant-scoped DB queries and PostgreSQL row-level security | Repository adapter |
| Provider credentials | KMS/secret manager encryption, tenant-and-provider-scoped keys, envelope rotation, no arbitrary client-selected environment variables | Secrets adapter |
| Agent execution | Persistent principal and tenant binding on enqueue, claim, tool invocation, audit and completion | Scheduler and workers |
| External tools | Explicit allowlist, content trust labels, approval gates for mail, submissions, filesystem and network effects | Tool policy adapter |
| Model network | Origin+DNS validated egress, no private metadata routes, no automatic credential forwarding or redirects | Egress adapter |
| Backups/export | Encrypted off-host backups, tenant-scoped recovery validation, access logging, restore drills and deletion semantics | Operations |

`PHDAI_API_TOKEN` is not an OIDC identity, authorization layer, or browser-login system. Existing `ApiServer` Host/Origin checks and local request budgets reduce local attack surface but are insufficient for internet-facing use.

## Data migration and deployment invariants

1. Keep static GitHub Pages and reviewed public evidence fully separate from hosted applicant data.
2. Use PostgreSQL for authenticated multi-owner storage. Every private record, run, event, job, provider route and encrypted-secret reference must have a nonnullable tenant ID. Use database constraints, indexes and RLS; never accept a tenant ID supplied by a browser as an authorization decision.
3. Introduce a typed `ActorContext` supplied only by verified session middleware. Domain functions receive it explicitly. Worker jobs persist the originator, tenant and approved execution scope, and recheck authorization before side effects.
4. Migrate legacy SQLite data only through an explicit owner-reviewed import after login and tenant selection. Do not auto-merge records, infer users or transfer secrets from public git history.
5. Put the hosted adapter behind a reverse proxy with explicit trusted-forwarded-header CIDRs; block direct backend ingress. Every privileged operation needs a real audited denial path.
6. Add per-tenant/inference cost budgets, idempotent queue admission, rate limits, process-level hard limits, expiry and replay validation.
7. Require end-to-end tests for forged session cookies, CSRF, stale JWKS, account/tenant ID guessing, cross-tenant job claims, model DNS rebinding, leaked credentials, shared cache keys, failed backup restore and horizontal authorization.
8. Make hosted capability flags return `supported=false` until the above controls are implemented and independently deployed/tested. A login button, a reverse proxy or a successful local Docker smoke run is not a hosted release gate.

## Source and privacy governance

Application source changes remain unverified until checked against the authoritative official portal with observation timestamps; audit events never automatically modify a recorded deadline. Model citation IDs alone do not establish entailment. Public repository history must be reviewed for exposed personal data independently of any sanitized Pages projection. GitHub About settings require Administration-write permission and are not modified by source code commits.

**Release decision:** hosted cloud full stack is blocked. Local Python, Linux Docker loopback, static Pages, and opt-in Actions batch execution remain the only documented operational modes until authenticated isolation is real.
