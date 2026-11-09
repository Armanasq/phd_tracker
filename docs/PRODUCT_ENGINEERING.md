# PhD Atlas — Product and engineering decisions

Reviewed: 2026-11-09. Target: existing GitHub Pages repository and deployed URL.

## Verified audit and remediation

| Severity | Observed deficiency | Resolution |
|---|---|---|
| P0 | Owner updates lacked an optimistic concurrency precondition | expected_updated_at, idempotent comment IDs, explicit source conflict/rebase |
| P0 | Previous owner notes and receipt URLs could be projected into public Pages data | Remove both fields from the committed public projection and issue commands |
| P1 | 109 tracked records were mixed with 21 unpromoted research candidates | Tracked-by-default scope control and verified owner promotion |
| P1 | Filters reset on navigation; views had no deep links | Hash routes, local filter recovery, and named presets |
| P1 | Pipeline relied primarily on dragging | Select controls on cards, supporting keyboard and single-pointer usage |
| P1 | Business rules intermingled with HTML rendering in a monolithic file | Pure ES module for risk, priority, readiness, filtering, date arithmetic and schema validation |
| P1 | Data validation checked only schema version and duplicate IDs | Record shape validation with a retryable source-error state |
| P2 | No saved views or persistent comparison | Device-local saved filters and comparison selection recovery |
| P2 | Missing source freshness and ongoing refresh | Stale-evidence warnings and 15-minute refresh with last-good-data fallback |
| P2 | Date-only calendar events could imply verified portal cutoff times | Explicit distinction between calendar day and official time/time-zone evidence |

## Functionality preserved

The original workbook, evidence JSON, discovery and reconciliation scripts, notification workflows, GitHub issue-control system, EvidenceGraph dashboard and repository history are retained.

The committed source is authoritative. Browser drafts are overlays. A submission is never inferred from a local status value; owner confirmation and a committed update are required. A document with state unknown is not a missing document.

## Architecture decisions

ADR-01 — Incremental ES modules, not framework migration. At this repository's current data volume, pure domain services provide deterministic unit-test coverage without adding React, Next.js, a new backend, or bundling overhead.

ADR-02 — Static authority boundary. GitHub Pages is read-only. Client code stores no privileged tokens. Owner changes use authenticated GitHub issue actions and server-side validation. This is not an authenticated backend.

ADR-03 — Optimistic concurrency. Drafts include the authoritative record version. Version changes trigger a conflict requiring explicit reconciliation. Retries recheck source state rather than overwriting a newer change.

ADR-04 — Public privacy boundary. Notes and applicant receipt links remain local; the GitHub command and public projection omit them. Highly sensitive applicant information belongs in a separately authenticated system, not in public GitHub Pages, issue comments, or localStorage.

ADR-05 — Editorial design system. Serif headings, system-sans text and data, warm neutral surfaces, restrained forest-green accents, semantic state colors, consistent icon stroke weights, clear control targets, and distinct mobile record cards. CSS design tokens are in site/style.css.

## Interaction contracts

- Eleven existing workspace views, hash-link navigation and browser history.
- Search, scope, combined filters, persistent named views, comparison, and explicit reset.
- Draft -> pending owner confirmation -> committed source; conflicts require review and rebase.
- Drag-and-drop has a labelled single-pointer and keyboard-operable select alternative.
- Modal focus containment, return focus, keyboard shortcuts, and clear validation.
- Browser notifications are optional, in-page and deduplicated; background delivery remains the repository's scheduled notification pipeline.
- Failed source refresh keeps the last valid evidence snapshot and offers recovery.

## Test and performance expectations

- Python owner-write validation tests, pure JS domain unit tests, browser journeys and existing EvidenceGraph QA.
- Browser screenshots: desktop, laptop, tablet, mobile and narrow mobile.
- Accessibility target: WCAG 2.2 AA. Automated testing is necessary but cannot certify assistive-technology behavior.
- Performance objectives: LCP <= 2.5s, INP <= 200ms, CLS <= 0.1 at the 75th percentile. A passing CI build alone is not proof of these field targets.

## Explicit remaining dependencies

Exact submission cutoff times and IANA time zones require primary official evidence; never infer them from calendar dates. Confidential data storage, authenticated outreach, and true background notifications require a secure backend. Degraded discovery providers remain an evidence coverage limitation.
