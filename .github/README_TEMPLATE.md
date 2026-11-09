# PhD Atlas

**An evidence-aware workspace for PhD applications, deadlines and research fit.**

[Open workspace](https://armanasq.github.io/phd_tracker/) · [Application guide](site/README.md) · [Architecture](docs/ARCHITECTURE.md) · [Release notes](CHANGELOG.md)

[![Pages deployment](https://github.com/Armanasq/phd_tracker/actions/workflows/publish-cockpit.yml/badge.svg)](https://github.com/Armanasq/phd_tracker/actions/workflows/publish-cockpit.yml)
[![Code quality](https://github.com/Armanasq/phd_tracker/actions/workflows/intelligence-ci.yml/badge.svg)](https://github.com/Armanasq/phd_tracker/actions/workflows/intelligence-ci.yml)

PhD Atlas brings application records, supporting sources, preparation tasks, contacts and decisions into one reviewable workspace. The public site is a static projection of committed evidence. An optional local Python service enables private state, model configuration and agent execution.

## Workspace

| Area | Purpose |
| --- | --- |
| Applications & Compare | Review opportunities, recorded deadlines, funding, eligibility and research fit side by side. |
| Actions, Contacts & Updates | Track preparation dependencies, faculty follow-ups, document readiness and changes. |
| Dashboard, Calendar & Pipeline | Prioritize work and distinguish recorded dates from confirmed closing times. |
| Verification, Sources & Archive | Inspect provenance, conflicting claims, excluded routes and incomplete evidence. |
| Research & EvidenceGraph | Examine the [evidence workflow](assets/readme/evidence_flow.svg), [portfolio frontier](data/portfolio_frontier.json) and [generated research report](docs/RESEARCH_REPORT.md). |
| Atlas assistant | Use configured local or cloud-compatible inference providers through the *private* runtime; responses are proposals, not completed actions. |

The [public workspace](https://armanasq.github.io/phd_tracker/) works without an AI provider. A provider preset, search result or model-produced suggestion is not proof of current availability, admission eligibility or a submitted application.

## Run locally

Use Python 3.11+ from the repository root.

```bash
git clone https://github.com/Armanasq/phd_tracker.git
cd phd_tracker
python -m pip install -r requirements-intelligence.txt
python scripts/build_workspace.py --out site/data/workspace.json
python -m http.server 8000 --directory site
```

Open `http://127.0.0.1:8000/` for the static application. For personal AI settings, stored conversations and local model inference, start the separate private runtime instead:

```bash
python -m phd_agents serve --port 8765
```

Open `http://127.0.0.1:8765/`, then configure **Settings → Connections**, test the selected model, and explicitly activate any cloud provider. See [private runtime operations](phd_agents/README.md) and [unified workspace setup](site/README.md). The runtime binds to loopback; API keys and private SQLite conversations are not deployed to GitHub Pages.

## Evidence and state

- **Original records:** [PhD_Action_List.xlsx](PhD_Action_List.xlsx) and reviewed JSON projections under [data/](data/). The [daily agenda](docs/TODAY.md) and **Full Task ledger** are generated from these sources.
- **Evidence discipline:** A recorded deadline is not a verified cutoff time. Unknown funding, document or eligibility requirements remain unknown until confirmed against official sources.
- **Owner updates:** GitHub Issues and owner-controlled workflows retain explicit approvals; private local edits are kept in SQLite and do not silently synchronize into the public workbook.
- **Discovery:** The [discovery report](data/discovery_report.json) describes observed source health. AcademicPositions, institutional feeds and other channels are not complete coverage. Gmail intake requires separately configured consent and credentials.
- **Reproducibility:** See the [capability atlas](docs/CAPABILITY_ATLAS.md), [operator playbooks](docs/PLAYBOOKS.md), [generated evidence report](docs/RESEARCH_REPORT.md) and [source provenance](data/experience_lineage.jsonld).

Source-related changes can be proposed through the [source correction](.github/ISSUE_TEMPLATE/01-source-correction.yml), [opportunity lead](.github/ISSUE_TEMPLATE/02-opportunity-lead.yml) and [automation idea](.github/ISSUE_TEMPLATE/03-automation-idea.yml) issue templates. The [intelligence workflow](.github/workflows/phd-intelligence.yml) is an auditable automation entry point, not an autonomous submission service.

## Source coverage and verification

The [Sources](https://armanasq.github.io/phd_tracker/#sources) section exposes the source workbook inventory, research candidates, reviewed opportunity notes, task projection, historical exclusions, discovery-provider errors, and links to committed evidence layers. **Counts describe different types of records:** workbook steps, source-audit rows and excluded research leads must not be counted as new application opportunities.

The [Verification](https://armanasq.github.io/phd_tracker/#review) section now includes a prioritized, filterable proof queue. It separates recorded closing dates from structured evidence of cutoff hour/timezone; unknown document states from explicitly unstarted requirements; source verification from current portal availability; and owner-managed Submitted state from a verified receipt. Its full queue can be exported to CSV for external review.

| Evidence label | Meaning |
| --- | --- |
| Source reviewed / Owner verified | An explicit review is recorded; current availability is still not guaranteed. |
| Needs review / Unverified | The primary-source verification gate remains incomplete. |
| Unknown document | Readiness has not been established; this is not proof that a file is missing. |
| Not started | Preparation is explicitly marked incomplete for that particular document. |
| Recorded deadline | The date is known from source notes; actual closing time may remain unverified. |
| Submitted | Owner-managed status; a portal receipt remains independently verifiable. |

Missing evidence is intentionally preserved as unknown. Private applicant correspondence, API credentials and receipt links must not be copied into public Pages data. Already committed public source files require their own privacy review.

## Deployment and repository administration

The Pages workflow generates the current workspace snapshot and a commit-bound SHA-256 release manifest. Post-deployment checks fetch the hosted manifest and verify the source commit and published JavaScript asset. A passing workflow verifies the deployed build, not the factual correctness of every university claim.

The repository About description, website and topics are versioned in [metadata configuration](.github/repository-metadata.json), but **GitHub About fields require a separate administration-authorized API update**. Committing a description file alone does not populate GitHub's About sidebar. The synchronization workflow fails explicitly if authorization is missing.

[Release readiness](docs/RELEASE_READINESS.md) · [Repository settings](.github/REPOSITORY_SETTINGS.md) · [Public-site guide](site/README.md) · [Accessibility statement](ACCESSIBILITY.md) · [GitHub Actions](https://github.com/Armanasq/phd_tracker/actions)

## Engineering

The application separates read-only public evidence from local agent execution. It uses a static JavaScript frontend, source normalization and verification scripts, deterministic application checks, a Python orchestration layer and SQLite for private state.

| Directory | Responsibility |
| --- | --- |
| [site/](site/) | GitHub Pages frontend and model configuration views |
| [phd_agents/](phd_agents/) | Private HTTP runtime, inference adapters, workflows and conversation storage |
| [scripts/](scripts/) | Import, normalization, reconciliation, evaluation and publication |
| [data/](data/) | Tracked evidence snapshots and derived application records |
| [dashboard/](dashboard/) | Research and exploration views |
| [tests/](tests/) | Contract, integration and UI regression checks |
| [.github/workflows/](.github/workflows/) | Pages publishing, quality gates and controlled automation |

The latest deployment status is visible in [GitHub Actions](https://github.com/Armanasq/phd_tracker/actions). The public site is not an authenticated backend, the assistant does not send mail or submit applications, and its references describe retrieved context rather than verified claim-level citations.

For change history and the scope of the current preview, see [CHANGELOG.md](CHANGELOG.md). Vulnerability reporting guidance is in [SECURITY.md](SECURITY.md). This repository does not currently include a software license.

### Complete task ledger

The [Task ledger](https://armanasq.github.io/phd_tracker/#ledger) exposes all normalized workbook task records, including historical deadlines, preparation steps and cross-route tasks, with search, task-type filters, worksheet/row provenance, source links and a complete CSV export. This is distinct from the short-horizon **Actions** view. Historic task dates are not treated as proof of incompletion.
