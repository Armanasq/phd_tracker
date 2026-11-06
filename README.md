# EvidenceGraph — PhD Application Intelligence

Private evidence-first application tracker with independent academic discovery, research-context signals, controlled workbook updates, deadline reminders, contradiction monitoring, and an interactive GitHub Action Center.

**Authoritative editable artifact:** [PhD_Action_List.xlsx](PhD_Action_List.xlsx). The original [Google Sheet](https://docs.google.com/spreadsheets/d/1mbdVt1Acg_-a6wzQE4c9Vr1S2JAMzcD3zWnuaHpY5vk/edit) is not automatically overwritten.

## Live system

| Module | Implemented operation | Evidence |
|---|---|---|
| Vacancy discovery | Parallel institutional Inria doctoral-listing scan, optional broad Brave search | [Discovery state](data/discovered_candidates.json) |
| Research radar | Keyless arXiv Atom searches; publications never identified as open jobs | [Research papers](data/research_radar.json) |
| Source intelligence | Canonical URL dedupe, claim history, source yield, inaccessible source warnings | [Source health](data/discovery_report.json) |
| Application tracking | Excel application list, deadlines, original tabs and human-owned statuses | [Workbook](PhD_Action_List.xlsx) |
| Decision frontier | Shared document leverage, unconfirmed readiness and source evidence debt | [Decision frontier](data/portfolio_frontier.json) |
| Deadline service | 30/14/7/3/1/0-day milestones and persistent deduplication | [Delivery ledger](data/notification_state.json) |
| Human controls | Owner-only priority, snooze, mute and unsnooze via a private GitHub Issue | [Issue controls](.github/workflows/issue-controls.yml) |
| Delivery | Private assigned GitHub Issue and optional multi-channel Apprise | [Action Center](../../issues/1) |
| Safety | Protected-cell workbook snapshot, regression tests and atomic push retries | [CI](.github/workflows/intelligence-ci.yml) |

### Operating schedule

[Main GitHub Action](.github/workflows/phd-intelligence.yml): **04:23 and 15:41 UTC** every day, or manually from the Actions tab.

It uses separate parallel collectors, downloads their structured run artifacts, reconciles the current Git workbook, checks all original user-owned cells, updates the workbook, computes the resource and notification frontier, and publishes. Notifications are delivered only after successful reconciliation.

[Read the product RFC](docs/PRODUCT_RFC.md) and [technical architecture](docs/ARCHITECTURE.md).

## Excel worksheets

The original six tabs are preserved: Read me, Action list, Step timeline, What I need to do, Dropped and Not added. The automation adds Research queue, Mail signals, Evidence ledger, Source watch, Decision frontier and Research radar, plus Mail inbox only if Gmail intake has been configured.

New search results are **not automatically promoted** into the main Action list. The Research queue requires manual verification of the live primary source, eligibility, funding, degree requirements and deadline before promotion.

## Reminders and controls

[Open the private Action Center](../../issues/1). It is assigned to the repository owner and includes upcoming deadlines, document-preparation leverage, evidence contradictions, fresh research leads and disabled search coverage.

Comment directly on the Issue using any of the following commands, replacing the sample application ID:

    /priority inria:2026-10570
    /unpriority inria:2026-10570
    /snooze inria:2026-10570 3d
    /unsnooze inria:2026-10570
    /mute inria:2026-10570
    /unmute inria:2026-10570

The owner-command parser verifies the issue, actor, source ID and bounded duration before applying changes. Commands cannot edit a submission state or mute deadlines within one day. Successful commands are acknowledged in the Issue.

### Optional external integrations

Repository Settings → Secrets and variables → Actions:

- BRAVE_SEARCH_API_KEY — broad multi-country web search. **Not configured** means this coverage is disabled and explicitly reported.
- GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, GMAIL_REFRESH_TOKEN — a user-authorized read-only Gmail OAuth client. Only message IDs, subjects, dates and links are persisted. Gmail is not accessible to GitHub Actions simply because ChatGPT has access to a Gmail connector.
- APPRISE_URLS — optional newline-separated Apprise destination URLs (Telegram, Discord, email, etc.). Keep these private; the workflow never prints destinations. No external notifications are sent without this secret.
- GITHUB_TOKEN — automatically provisioned by GitHub Actions; do not create a separate personal access token.

No application is submitted or private email sent without the user's explicit action.

## Local verification

    python -m pip install -r requirements-intelligence.txt
    python -m pytest tests -q
    python scripts/workbook_contract.py snapshot
    python scripts/refresh_tracker.py --online
    python scripts/ingest_discovery.py
    python scripts/portfolio_frontier.py
    python scripts/workbook_contract.py verify
    python scripts/validate_tracker.py

Running mutating steps on a working branch is recommended. The scheduled workflow carries out these steps against the latest branch head and commits verified outputs.

## Design limitations and responsibility

- A published institutional deadline and a functioning application portal can disagree; both claims remain visible.
- A paper matching your research interests is **not** an advertised or funded PhD opportunity.
- A search provider with no credentials is marked disabled; search breadth must not be overstated.
- Source content is treated as untrusted data, not program instructions.
- Eligibility, nationality-based funding, degree equivalence and submission receipts always require authoritative confirmation.
- Schedule timing is best-effort; GitHub Actions is not a guaranteed real-time notification infrastructure.
- Product novelty and commercial outcomes must be demonstrated by evaluation rather than claimed without evidence.

The definitive architecture, evaluation criteria and commercialization experiments are documented in [PRODUCT_RFC.md](docs/PRODUCT_RFC.md).
