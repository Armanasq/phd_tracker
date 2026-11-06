# EvidenceGraph — Product and Engineering RFC

Status: Working private reference implementation, reviewed 2026-11-06.

## Thesis

A doctoral application is not simply a job-board row. It is a time-bounded opportunity subject to proof obligations. An applicant can miss an opportunity despite discovering it because the portal is closed, funding is restricted, a referee is delayed, the final deadline differs from the priority deadline, or a lab never published a conventional vacancy.

The current system connects discovery, source assertions, applicant-owned decisions, reusable document dependencies, research context and scheduled notifications. It preserves uncertainty when sources disagree. This work does not establish a world-first invention or future company valuation.

## Implementation map

    Institutional Inria vacancies       Optional Brave search       arXiv scholarly activity
                  |                               |                          |
           Primary source parser           Candidate parser             Atom parser
                  |                               |                          |
                  +-------------------------------+                          |
                                  |                                          |
                      Deduplication and source yield               Research-only radar
                                  |                                          |
                         Proof / review queue                      Publication metadata
                                  |                                          |
                         Original Excel tracker <----------------------------+
                                  |
                         Resource readiness state
                                  |
                      Decision / evidence frontier
                                  |
                      Notification and snooze policy
                                  |
                        Private GitHub Action Center
                          and optional Apprise delivery

The main workflow runs at 04:23 and 15:41 UTC. Separate discovery workers produce immutable per-run artifacts. Workbook publication is atomic: on a concurrent branch update the workflow re-reads and recomputes changes, never binary-merges Excel. The original workbook is snapshotted and protected cells are checked before commit.

## Product primitives — implemented versus research

### 1. Temporal proof ledger

One vacancy may have conflicting source assertions: a university webpage advertises November 15 while its portal says applications closed. The system retains both observations, proposes changed deadlines for review, and flags contradictions rather than silently overwriting the user's deadline.

Implemented: source_observations, proposed_deadline, deadline_change_needs_review, and an evidence/proof-debt queue.

Next research milestone: bitemporal assertions, exact evidence spans, source provenance signatures, and typed proof contracts for deadlines, funding, eligibility and application-state claims.

### 2. Counterfactual portfolio attention

The Decision frontier records each application's time to deadline, evidence debt, and shared asset dependencies. It does not assume that a document mentioned in an advert is missing from the user's portfolio. Explicit states are unknown, ready, in_progress, not_started and not_applicable.

Implemented: document-leverage index across applications and source-status-dependent proof obligations.

Next milestone: optional user-entered effort estimates and available hours to optimize the set of applications which could be unlocked by finishing a reusable asset. Missing effort estimates remain unknown; the optimizer must never invent them.

### 3. Two-lane search

Actual PhD vacancies are acquired from institutional sources or search candidates. Unverified positions enter Research queue, never the approved action list. Research papers from arXiv are collected in a separate Research radar worksheet and are never treated as proof of open positions.

Next milestone: academic author-to-lab-to-position links only when institutional affiliation and the recruitment route can be independently verified.

### 4. Source yield and negative evidence

Providers report observed listings, new canonicalized records, reobservations, unique yield, health and failures. Missing Brave Search credentials are explicitly marked disabled rather than falsely suggesting that worldwide searches returned zero openings. Broken research sources are surfaced as coverage alerts.

Next milestone: source budget allocation using yield, freshness, duplicates and coverage gaps. Use holdout manually verified doctoral postings to estimate recall; a large raw result count is not an outcome metric.

### 5. GitHub as the human control plane

One private, assigned GitHub Issue contains the action calendar, evidence debt, research links, notifications and source health. Repository-owner commands allow per-opportunity priority, mute and snooze:

    /priority inria:2026-10570
    /unpriority inria:2026-10570
    /snooze inria:2026-10570 3d
    /unsnooze inria:2026-10570
    /mute inria:2026-10570
    /unmute inria:2026-10570

Only verified owner comments on the marked Action Center are processed. IDs must exist in the tracker. No Issue body is executed as code. A bounded state update is recorded by comment ID, committed with a race-safe transaction, and acknowledged. Alerts for deadlines at zero or one day remain active even when an item is muted or snoozed.

## Reliability and trust contracts

| Boundary | Rule |
|---|---|
| Search result | Untrusted research candidate, not application state |
| Official advertisement | Evidence for a listed role and deadline, not guaranteed funding eligibility |
| Recruiting email | Candidate signal, not proof of a successful portal submission |
| Scholarly paper | Research context, not a job opening |
| User application status | Never silently modified by automation |
| Gmail | Optional read-only OAuth metadata, separate repository secrets |
| External messaging | No Apprise delivery without explicitly configured destinations |
| Workbook mutation | Preserve existing IDs, dates, decisions and all user-protected cells |
| Concurrency | Recompute on latest head and reject conflicting modifications |
| Notification flood | Stable event IDs, per-channel ledger, milestones and owner-controlled snoozes |
| Supply chain | Immutable commit SHAs for GitHub Actions |
| Source degradation | Log missing, stale or contradictory evidence explicitly |

GitHub Actions schedules may be delayed and should not be treated as a guaranteed real-time service. Human verification of final application deadlines and portal availability remains necessary.

## Comparable open-source work and specific learnings

- [ResearchFit](https://researchfit.org/) already aggregates research positions and performs AI matching; neither aggregation nor matching alone is novel. Our differentiated hypothesis is an auditable path from an opportunity to proof debt and readiness dependencies.
- [changedetection.io](https://github.com/dgtlmoon/changedetection.io) demonstrates source diffs and monitoring; here observations from different sources can also contradict one another.
- [Apprise](https://github.com/caronc/apprise) motivates channel-neutral notification delivery, with suppression and deduplication handled upstream.
- [dlt](https://github.com/dlt-hub/dlt) demonstrates incremental ingestion and schema contracts. This system uses JSON plus Git commits, not the dlt library.
- [kitsuno-ai/agentic-job-search-eu](https://github.com/kitsuno-ai/agentic-job-search-eu) demonstrates measured source yield and honest reporting of disabled sources.
- [GPT Researcher](https://github.com/assafelovic/gpt-researcher) motivates parallel research with provenance; generated interpretations must not override primary evidence.
- [arXiv API user manual](https://github.com/arXiv/arxiv-docs/blob/develop/source/help/api/user-manual.md) documents API parameters and respectful request intervals.
- [GitHub Actions security roadmap (March 2026)](https://github.blog/news-insights/product-news/whats-coming-to-our-github-actions-2026-security-roadmap/) motivates pinned action revisions and least-privilege permissions.

These are architecture influences, not copied implementations or novelty claims about known methods.

## Company thesis and pricing constraints

Potential paying segments are applicants seeking reliable application planning, research labs seeking eligible matches, and university programmes managing recruitment. A pure low-fee alerts subscription is unlikely to support venture-scale economics alone; an institution-paid workflow requires evidence of reduced recruitment friction and demonstrably better candidate quality.

Do not invent a TAM, customer willingness to pay, or a valuation. A defensible bottom-up market model needs annual qualified applicant volume, institution procurement budgets, acceptance and retention behavior, customer acquisition costs, subscription conversion, price and gross margin.

## Core KPI contract

| Measure | Definition | State |
|---|---|---|
| Verified actionable recall | Open and actually eligible calls found / manually audited eligible benchmark universe | Benchmark not available |
| Verified on-time submission rate | Applications with confirmed submission before deadline / user-intended applications | Receipts and user labels needed |
| Time to qualified shortlist | Time from search start to a user-confirmed viable shortlist | Event instrumentation needed |
| Source unique yield | New canonical records / observed records per provider | Implemented |
| Source observation lag | Current UTC time minus last successful observation | Partially implemented |
| Notification precision | User-rated useful alerts / alerts delivered | Feedback collection needed |
| Deadline / eligibility false claims | Incorrect definitive claims / audited claims | Audit sample needed |

Quality guardrails already enforce preservation of user decisions and original records. Product success cannot be inferred from raw discovered item counts or notification volume.

## Maturity gates

M0 implemented: private tracker; twice-daily pipeline; Inria institutional discovery; optional Brave research; separate paper radar; deadline and source contradictions; portfolio frontier; owner-controlled Issue notifications; integrity tests; bounded Git publication retries.

M1: additional country and university-specific adapters with source-rights review; a manually labeled recall benchmark; localized deadlines and timezone-aware closing times; per-source service levels.

M2: evidence span verifier; research-to-supervisor maps backed by institutional affiliations; opt-in private document vault; validated marginal task scheduling.

M3: multi-tenant institution-facing console with privacy-preserving matching and measurable hiring outcomes; real billing tests and unit economics.

## Operational paths

- Main workflow: ../.github/workflows/phd-intelligence.yml
- Unit tests: ../.github/workflows/intelligence-ci.yml
- Issue controls: ../.github/workflows/issue-controls.yml
- Original Excel tracker: ../PhD_Action_List.xlsx
- Applicant resource states: ../data/application_assets.json
- Notification policy: ../data/notification_preferences.json
- Discovery yield and source health: ../data/discovery_report.json
- Research radar: ../data/research_radar.json
- Decision frontier: ../data/portfolio_frontier.json
