# PhD Atlas — navigation and execution contracts

Updated 2026-11-10. This is a source-backed route inventory, not a product feature wishlist. Hash-based workspace routing is centralized in `site/modules/routes.mjs`; unknown and malformed hashes resolve to `#dashboard`.

| Route | Primary source | Available without backend | Privileged or user actions |
| --- | --- | --- | --- |
| `#dashboard` | Public evidence + local drafts | Yes | Inspect records; first-run setup |
| `#applications` | Source records + device-local opportunities | Yes | Add, edit, export and stage records |
| `#discovery` | Explicit research candidate records | Yes | Review proof gaps, filter, inspect, stage verified promotions |
| `#readiness` | Deterministic evidence and document state | Yes | Inspect missing proofs and export readiness |
| `#documents` | Source-listed document requirements across tracked applications | Yes | Review shared document demand and readiness without uploading files |
| `#operations` | Private SQLite application/referee/evidence state | No | Owner-managed private updates, conflicts, reference planning |
| `#actions` | Public tasks and deadline evidence | Yes | Prioritize, navigate, export |
| `#ledger` | Public original workbook task projection | Yes | Search, filter and export |
| `#calendar` | Source dates, verified cutoffs and owner drafts | Yes | Navigate calendar and export |
| `#pipeline` | Explicit applicant application states | Yes | Stage transitions; do not infer submissions |
| `#contacts` | Faculty and contact fields | Yes | Inspect and stage follow-up information |
| `#updates` | Device-local drafts + committed source versions | Yes | Reconcile and stage public changes |
| `#compare` | Selected tracked source records | Yes | Explicit evidence comparison |
| `#review` | Source verification queue and hosted triage | Yes | Inspect proof gaps and duplicate advisories |
| `#archive` | Historical exclusions and recorded expired/blocked states | Yes | Review exclusions and route history |
| `#sources` | Public source provenance and feed diagnostics | Yes | Inspect source references and discovery history |
| `#ai` | Private model or explicitly verified browser-loopback model | Conditional | Direct browser chat or private agent inference; no automatic submissions |
| `#agents` | Private agent registry and deterministic tools | No | Configure agent responsibilities, allowlisted tools and routes |
| `#automations` | Private workflows, scheduler and model routes | No | Preview workflow routes, configure execution and opt-in schedules |
| `#activity` | Private model audit ledger | No | Inspect actual private runs and usage |
| `#evaluations` | Private aggregated run ledger, citation audit and workflow stage outcomes | No | Inspect measured provider/agent failures, token reports, latency and provenance; filter recent traces |
| `#source-observations` | Private SQLite observation history, byte-change categories and source URLs | No | Review official-source drift; manual CLI collection only; no factual promotion |
| `#source-claims` | Private retained source excerpts and exact-quote candidate claims | No | Inspect observed text, capture provenance to SQLite without promoting facts |
| `#onboarding` | Public deployment identity, model probe and runtime capability checks | Yes | Choose deployment mode, inspect requirements and export a nonsecret setup summary; no GitHub changes |
| `#deployment` | Runtime capability contract | Yes | Inspect trust boundaries and setup options |
| `#settings` | Browser-local model config or private server config | Yes, different scope | Configure/test endpoints; private mode also exposes models, routing, agents and workflows |

## Routing and state invariants

- Canonical route definitions are single-source in `site/modules/routes.mjs`, including legacy hash aliases.
- UI navigation, browser Back/Forward, deep links and mobile route selection must resolve to the same canonical view.
- `#deployment` never reports authenticated cloud hosting as ready. GitHub Actions is an independent opt-in batch workflow, not a browser chat API.
- Browser-local `#ai`, Settings and the floating Ask Atlas assistant share one ephemeral model client. An actual model response must be verified before interactive inference.
- Browser-local AI does **not** imply access to Python tools, SQLite, cloud secrets or server-side schedules. Only committed public record fields explicitly selected by the user can be included in a local-model prompt.
- Private `#automations` supports a read-only route preview. A multi-stage workflow must validate all provider routes and fresh cloud consent *before* executing its first stage.
- Document inventory aggregates only explicitly declared requirements and recorded readiness; an absent document list is unconfirmed, not evidence that documents are unnecessary.
- Discovery candidates are never automatically promoted, marked eligible, or treated as admitted. Source observation history is private and represents byte changes or unavailable fetches, never semantic deadline or admissions verification. A recorded source review may be stale, and a recorded passed date does not prove a programme is permanently closed.
- Source records remain distinct from local drafts; uploaded public data must exclude applicant notes, receipts and credentials.

## Regression gates

- `tests/routes.test.mjs`: canonical routes, alias resolution and invalid hashes.
- `tests/documents.test.mjs`: portfolio document demand, deduplication, unknowns and provenance discipline.
- `tests/discovery.test.mjs`: candidate classification, expiry and explicit review states.
- `tests/runtime_capabilities.test.mjs`: capability gating by private, browser-local and static mode.
- `tests/browser_model*.mjs`: endpoint restrictions, model probing, direct inference and ephemeral history.
- `tests/browser_lens_smoke.cjs`: real browser path from Settings to the global assistant and new routes.
- `tests/test_workflow_plan.py`: multi-agent preflight and no partial cloud execution.
- `tests/test_runtime_capabilities.py`: local capability API, correct readiness and secret exclusion.
- `tests/all_routes_audit.cjs` and `tests/mobile_layout_audit.cjs`: all 26 routes across form factors.

## Outstanding product boundaries

Authenticated cloud API, multi-user resource isolation, hosted database, durable cloud job execution and OIDC login are **not implemented**. The local Docker deployment remains Linux host-network-specific. Provider-specific browser CORS/LNA behavior must be verified on actual browser/runtime combinations. Real-world source accuracy and external application outcomes require independent proof.

These are release blockers for claiming a complete hosted PhD application SaaS.
