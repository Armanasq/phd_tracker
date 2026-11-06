# Capability atlas

[Command center](../README.md) · [Playbooks](PLAYBOOKS.md) · [Today's agenda](TODAY.md) · [Product research](PRODUCT_RFC.md)

The states below are based on code and the committed telemetry. **Operational** means implemented and exercised; **conditional** requires credentials; **degraded** means a working pipeline cannot reliably acquire that source; **proposed** is not shipped.

## Discovery and evidence

| Capability | State | Evidence and decision boundary |
|---|---|---|
| Primary Inria vacancy crawler | Operational | [Discovery report](../data/discovery_report.json); funding still needs verification |
| AcademicTransfer source | Degraded | Zero observed results on the latest run |
| AcademicPositions source | Degraded | HTTP 403 on the latest run |
| Cross-country Brave search | Conditional | Needs BRAVE_SEARCH_API_KEY |
| Canonical URL aliasing and duplicate suppression | Operational | [Source records](../data/discovered_candidates.json) |
| Dated source observations and deadline contradictions | Operational | Prior values retained for review; no silent overwrite |
| First-seen and stale-source detection | Operational | Observation time is not current-opening proof |
| Historical exclusion memory | Operational | [Exclusion memory](../data/exclusion_memory.json); previously rejected sources may change |
| Independent arXiv research radar | Operational | [Publications](../data/research_radar.json) are not open jobs |
| Verified supervisor affiliation and lab recruiting graph | Proposed | Papers alone never imply that a lab is recruiting |
| Empirical global recall benchmark | Proposed | No measurement of all worldwide funded calls is available |

## Decision and execution

| Capability | State | Operator |
|---|---|---|
| Multi-sheet Excel application tracker | Operational | [Workbook](../PhD_Action_List.xlsx) |
| Separate application, programme-step, and shared-task clocks | Operational | [Daily execution plan](TODAY.md) |
| Evidence and eligibility proof obligations | Operational | [Decision frontier](../data/portfolio_frontier.json) |
| Explicit applicant CV/transcripts/SOP readiness | Operational, owner input needed | [Asset states](../data/application_assets.json) |
| Reusable-document priority frontier | Operational | Mentions imply possible reuse, not missing documents |
| Deadline milestone alerts | Operational | [Private Action Center](../../issues/1) |
| Owner-only priority/snooze/mute controls | Operational | [Issue commands](../scripts/issue_controls.py) |
| Separate task completion ledger | Operational | Completion requires explicit user action |
| Source conflict alerts | Operational | [Monitor report](../data/latest_run.json) |
| Calendar export | Operational snapshot | [ICS export](../calendar/phd_deadlines.ics); reimport after updates |
| External notification delivery | Conditional | Requires APPRISE_URLS |
| Automated Gmail metadata scan | Conditional | Requires read-only Gmail OAuth secrets |
| Automated portal submission | Not implemented | Must not occur without explicit authorization and validation |
| Bidirectional live Google Sheets sync | Not implemented | GitHub Excel file is the updated artifact |

## Reliability and security

| Contract | State | Proof |
|---|---|---|
| Parallel scheduled GitHub Actions | Operational | [Pipeline](../.github/workflows/phd-intelligence.yml) |
| Workbook schema and regression tests | Operational | [CI](../.github/workflows/intelligence-ci.yml) |
| Refetch and recompute on concurrent Git commits | Operational | [Atomic writer](../scripts/atomic_intelligence.sh) |
| Negative evidence for a closed submission portal | Operational | [Monitor](../data/watchlist.json) |
| Pinned GitHub Action dependencies | Operational | Workflow files |
| Per-provider yield and degraded coverage telemetry | Operational | [Discovery health](../data/discovery_report.json) |
| Robust multilingual/JS site extraction | Partial | Source-specific adapters remain limited |
| Consent-based multi-user identity and data isolation | Proposed | Not a deployed SaaS |

## The application evidence lifecycle

~~~mermaid
stateDiagram-v2
    [*] --> Discovered
    Discovered --> Verification
    Verification --> ReviewRequired: insufficient or contradictory evidence
    Verification --> Candidate: verified vacancy
    Candidate --> Preparing: owner chooses
    Preparing --> Submitted: owner-confirmed receipt
    Candidate --> Excluded: verified restriction
    ReviewRequired --> Verification: new dated evidence
    Submitted --> Interview: owner-confirmed update
    Interview --> Offer: owner-confirmed update
~~~

This is a design model. Not all lifecycle transitions have dedicated implemented controls. No search result, email subject, or scientific paper is treated as evidence that an application was submitted.

## Engineering evaluation

Primary proposed outcome metrics: (1) precision of truly open and eligible funded calls, measured against primary-source evidence; (2) verified opportunities per hour of applicant review; (3) deadline misses attributable to erroneous alerts. Driver metrics: new unique sources per successful crawl, source coverage/recall on a fixed sample, time from new posting to verified alert. Guardrails: false eligibility confirmations, spurious submission states, repeated notifications, secret exposure, and data loss on concurrent writes.

No valuation or global novelty claim is supported by these operational measurements alone.
