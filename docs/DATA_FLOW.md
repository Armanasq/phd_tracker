# PhD Atlas: data contracts, ownership, synchronization and runtime logic

## Operating modes

- **Upstream GitHub Pages:** builds the public, sanitized evidence snapshot from committed repository sources. It has no Python backend, SQLite or access to private model credentials.
- **Independent GitHub Pages fork:** defaults to `starter`, with zero source records. The owner must review/replace source files, explicitly opt in using `PHD_ATLAS_DATA_MODE=source`, then publish.
- **Local static server:** the same HTML and JavaScript with a locally built source snapshot; browser drafts persist per host and project path.
- **Local private runtime:** the same UI from a loopback Python server, augmented by SQLite records, provider configuration, evidence-based agents, workflow execution and backup/restore. Startup generates the snapshot automatically.

All modes use the `schema_version=1` public workspace contract. Deployment identity is generated separately from evidence.

## Data ownership graph

```text
Primary programme and workbook sources
    data/experience_view.json
    data/opportunities.json
    data/portfolio_frontier.json
    data/decision_queue.json
    data/application_assets.json
    data/discovered_candidates.json
    data/execution_plan.json
    data/workspace_overrides.json
              |
              | deterministic Python projection + sanitization
              v
    scripts/build_workspace.py
              |
              v
    site/data/workspace.json
              |
              | schema and unique-ID validation
              v
    site/app.js  ---->  browser-local draft overlays (source-backed)
              |                     |
              |                     +--> export JSON/CSV
              |                     +--> stage owner-only GitHub command
              |
              +--> browser-local opportunity store (device-only)
              |       +--> Add / edit / delete / restore JSON backups
              |       +--> export sanitized experience_view.json
              |       +--> explicitly commit own reviewed sources in fork
              |             (never an automatic GitHub commit)
              |
              +--> Dashboard / Applications / Contacts / Actions
              +--> Calendar / Pipeline / Evidence / Sources

GitHub owner public action
    Issue comment /workspace {...}
              |
              v
    workspace-controls.yml -> atomic_workspace.sh
              |
              | verify issue marker, owner, field allowlist
              | check record ID, version precondition and replay ID
              v
    data/workspace_overrides.json (public-safe fields only)
              |
              v
    rebuild -> commit main -> Pages publish and post-deploy verification

Local private runtime
    python -m phd_agents serve --port 8765
              |
              +--> prepare_public_snapshot (atomic write)
              +--> same-origin HTTP frontend and /api routes
              +--> source evidence from build_workspace
              +--> SQLite Store (private owner state, runs, conversations)
              +--> provider health and explicit model routing
              +--> scheduled/manual agents with source-bound evidence
              +--> encrypted-in-transit cloud calls only with explicit consent
```

The diagram describes trust boundaries and observable processing, not guaranteed source accuracy or inferred application outcomes.

## Public snapshot invariants

- Each application must have a unique, non-empty ID and a valid record type (`tracked` or `candidate`).
- Applicant status and evidence verification are distinct state machines. A source review is not an application submission.
- Missing deadlines, document readiness, contact responses and submission receipts are represented as unknown, not silently assumed complete.
- Source URLs reject unsafe schemes, authentication in URLs, mailbox links and query/fragment tracking data during projection.
- Published application rows are sanitized and do not contain private notes, email addresses or receipt identifiers.
- Independent `starter` mode does not read inherited opportunity files and constructs an empty compatible snapshot.
- Source discovery and historical exclusions are not automatically counted as tracked applications; candidate promotion requires separate review.
- The public artifact contains an `instance` identifier and the exact source commit is carried in `instance.json` and `release-manifest.json`.

## Draft update lifecycle and conflict handling

1. A browser loads and validates `workspace.json`; local overlays are scoped to the current hostname and path.
2. An owner edits a non-sensitive status, next action, follow-up or document state. A draft retains the base `updated_at` version.
3. On GitHub Pages, the UI generates a public-safe `/workspace` command; it does **not** commit automatically or authenticate as the owner.
4. The owner posts the command in a designated Action Center issue. The workflow checks actor, marker, known ID, allowed fields and previously processed comment IDs.
5. If the supplied `expected_updated_at` differs from the current committed version, the backend rejects the stale update rather than silently overwriting it.
6. Successful writes update `data/workspace_overrides.json` and regenerate the public snapshot in a serialized retry loop.
7. The browser observes a later published snapshot and reconciles its draft by comparing the base version and operational fields. Pending local state is not proof that the remote commit succeeded.

Device-only applications are separate from the committed source registry: they have local UUIDs, do not enter owner-only Issue commands, and are never presented as GitHub-synchronized. An exported source file contains only reviewed public-field candidates; browser-only notes, receipts, workflow status, and query-token URLs are excluded. Import is validated and merges nonconflicting local UUIDs without replacing existing records.

Local SQLite mutations follow a separate optimistic-version contract and are not merged into public Git commits by default.

## Security limitations

Browser storage is scoped by application path for collision prevention; it is **not security isolation** between applications on one GitHub Pages hostname. The entire origin shares `localStorage`. Do not save sensitive correspondence, API tokens or private application files there.

The private API accepts loopback clients and same-origin requests and disables permissive cross-origin access. Remote or team-hosted deployment requires a separately engineered authentication layer, transport security and tenant isolation; GitHub Pages does not supply these capabilities.

No provider is considered available merely because it is listed in the settings catalog. Model connection, actual inference success and permission to disclose applicant data are distinct. AI output is advisory and never confirms portal submission.

## Portability and release gates

- `python -m pytest tests -q` covers data projection, version controls, private runtime and fork isolation.
- `node --test tests/domain.test.mjs tests/storage.test.mjs` covers application rules and multi-project browser storage keys.
- The Pages workflow builds, schema-checks, publishes and checks the deployed snapshot, module digests, repository identity and source SHA.
- `scripts/instance_config.py` rewrites canonical URL, repository links and sitemap for each deployment without embedding a credential.
- `python -m phd_agents serve --port 8765` builds the missing public JSON on first startup; `python -m http.server` requires a prior explicit build.

### Evidence versus claims

The snapshot and UI are an applicant work queue, not a source of admissions truth. Exact cutoff time, scholarship eligibility, faculty availability and proof of successful submission require primary institutional evidence or owner-confirmed receipts.

### Distribution and licensing

The repository did not contain an explicit software `LICENSE` file when this guide was written. Running or redistributing outside GitHub's platform terms may require permission. A repository owner must choose and publish a license before advertising broad open-source reuse.
