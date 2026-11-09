# Running PhD Atlas on a local machine or another GitHub repository

## Deployment and data ownership

| Deployment | User interface | Public evidence | Private state | Model execution |
| --- | --- | --- | --- | --- |
| GitHub Pages (upstream or fork) | Static HTML/JS | Published `data/workspace.json` | Device-local applications and drafts | No |
| Local static server | Same HTML/JS | Locally built snapshot | Browser-local drafts | No |
| Python runtime on loopback | Same HTML/JS | Locally built snapshot | Private SQLite | Yes, when configured and consented |

GitHub Pages is a static host. Python, SQLite, API keys, provider authentication, and recurring private agent runs do **not** run on GitHub Pages. The public application deliberately does not call a local service from a hosted origin. For authenticated AI execution, open the **same UI served by the local runtime**.

### Run locally

Requirements: Python 3.11+, git, and a browser. From your own clone:

```bash
git clone https://github.com/Armanasq/phd_tracker.git
cd phd_tracker
python -m pip install -r requirements-intelligence.txt
python scripts/build_workspace.py --out site/data/workspace.json
python -m http.server 8000 --directory site
```

Open `http://127.0.0.1:8000/`. File URLs (`file://`) are not supported because module imports and data fetches require HTTP. The static server does not expose the private Python agent API.

To use local/cloud model providers, private application updates, scheduled workflows and SQLite (the private server automatically regenerates `site/data/workspace.json` if it is missing):

```bash
python -m phd_agents serve --port 8765
```

Open `http://127.0.0.1:8765/#settings`. Configure a real OpenAI-compatible/other supported endpoint in Settings; local models must already be running. The private server listens only on loopback and is not suitable for internet exposure without an independently designed authentication and reverse-proxy deployment.

### Publish your own GitHub Pages site

1. Fork or copy the repository to `YOUR_ACCOUNT/YOUR_REPOSITORY`. A fork contains the original maintainer's public files and Git history. By default, its Pages build publishes an empty starter workspace rather than inherited opportunities. Replace those source files and review provenance before sharing any new data. Never publish private emails, receipts or credentials.
2. Keep `main` as the default branch. In **Settings → Actions**, enable GitHub Actions for the fork as required. In **Settings → Pages → Build and deployment**, select **GitHub Actions**.
3. Run **Actions -> PhD Atlas | Publish GitHub Pages Workspace -> Run workflow**. The initial deployment is an empty starter. Use the browser's **Applications -> Add opportunity** and **Export workspace -> GitHub source JSON (public fields)** features, review and commit the generated JSON at `data/user_opportunities.json`, then set Actions variable `PHD_ATLAS_DATA_MODE=source` and rerun publication. The site derives its repository and URL from `GITHUB_REPOSITORY`.
4. Inspect the deployed `instance.json`, `release-manifest.json`, `data/workspace.json`, sitemap, and source links. The manifest binds published files to the source commit. A green deploy does not establish university claim accuracy.
5. To use owner-controlled public status updates, enable Issues, create an **Owner Action Center** issue from the included issue template, and set repository Actions variable `PHD_ATLAS_ACTION_ISSUE` to its number. Without the variable, the application links to the issue-creation template rather than guessing `issues/1`.

For a custom domain, configure the actual Pages domain in GitHub first, and set the Actions repository variable `PHD_ATLAS_SITE_URL` to the HTTPS site root. This controls the generated canonical link, Open Graph URL and sitemap; a variable alone cannot register DNS or a Pages custom domain.

The publisher never writes credentials to the static artifact. Forks must independently configure GitHub Actions permissions and optional discovery sources; upstream GitHub secrets and local SQLite files are not inherited.

### Browser-local opportunities on any deployment

The Applications view provides **Add opportunity**, **Local backup**, and **Import backup**. Opportunity details can be edited and deleted without a backend. These records remain only in the current browser storage and are explicitly marked device-only; clearing browser data deletes them unless a backup has been exported. Import merges distinct local IDs and never overwrites an existing record automatically.

Use **Export → GitHub source JSON (public fields)** to create `user_opportunities.json` from device-local opportunities. The export deliberately omits local notes, receipt links, next-step text, local submission state, URL query parameters and fragments. Query-dependent official links must be reviewed and replaced with a stable public URL before publication. Review the generated records and commit the file as `data/user_opportunities.json` in your own repository. Independent source-mode builds read only that dedicated file and optionally `data/user_workspace_overrides.json`, never the upstream applications, workbook or overrides; inherited source files can still remain visible in the fork's Git history. The fork remains in blank `starter` mode until `PHD_ATLAS_DATA_MODE=source` is explicitly set. Exporting does not commit or submit anything.

Device-local data is not encrypted and must not be treated as confidential storage on a shared browser or same-origin hosting service; use the loopback SQLite backend for genuinely private applicant information. GitHub source exports are public once committed.

### Build and configure a different repository explicitly

```bash
cp data/user_opportunities.example.json data/user_opportunities.json
python scripts/build_workspace.py --repository YOUR_ACCOUNT/YOUR_REPOSITORY --data-mode source --out site/data/workspace.json
python scripts/instance_config.py --repository YOUR_ACCOUNT/YOUR_REPOSITORY --site site
python -m http.server 8000 --directory site
```

Identity precedence is: explicit `--repository`, `PHD_ATLAS_REPOSITORY`, `GITHUB_REPOSITORY`, local git origin, then the upstream default. Remote detection accepts only GitHub HTTPS or SSH URLs. The optional site metadata preparation step updates the local site artifact, not the repository's GitHub About settings.

**Public-data contract:** A fork starts in `starter` mode with zero tracked applications. `PHD_ATLAS_DATA_MODE=source` requires `data/user_opportunities.json` and uses its source and independent overrides rather than the inherited workbook. Private email, credentials and receipts never belong in the public file.

### Validation

```bash
python -m unittest discover -s tests -p 'test_instance_config.py'
python -m unittest discover -s tests -p 'test_workspace.py'
node --test tests/domain.test.mjs tests/storage.test.mjs tests/local_records.test.mjs
node tests/local_records_smoke.cjs
node --check site/app.js
```

This verifies routing, metadata generation, public source links, instance identity and a minimal independent source dataset. A fork's dataset is not guaranteed complete and must be verified against primary university sources.

Browser draft keys are namespaced by host and Pages project path, preventing accidental mixing among repos. Namespacing is **not a security boundary**: pages under the same hostname can read the same browser-origin storage. Keep sensitive applicant state in the private local runtime.

Detailed [source ownership, synchronization state machines and deployment contracts](DATA_FLOW.md) describe the trust boundaries and invariants.

The repository currently has no explicit software `LICENSE` file. Users who need redistribution rights outside GitHub's platform terms should obtain permission until the maintainer selects a license.

The [independent opportunity input contract and browser-to-GitHub export workflow](USER_SOURCE.md) covers the public schema, verification requirements and update state. Fork discovery is disabled by default; opt in with Actions variable `PHD_ATLAS_ENABLE_DISCOVERY=true` only after auditing the sources.

### Private runtime isolation across local clones

A clone of another owner's fork automatically receives a private SQLite database and provider credential file under a checkout-scoped subdirectory of `~/.local/share/phd-atlas/instances/`. This is separate from the upstream installation's legacy path, which remains unchanged. Explicit `PHDAI_PRIVATE_DIR` takes precedence. A downloaded source archive without a Git origin must set `PHD_ATLAS_REPOSITORY=YOUR_ACCOUNT/YOUR_REPOSITORY` when starting the private runtime to avoid upstream fallback. Use separate identities for separate users; this is not an authenticated multi-user server.

## GitHub-hosted authenticated AI

Repository and environment secrets can power automated model calls in GitHub Actions without running a local server. Enable `PHD_ATLAS_ENABLE_HOSTED_AI=true`, configure the dedicated `phd-atlas-ai` environment secret and provider variables, and run the [Hosted AI Verification Triage workflow](../.github/workflows/hosted-ai-advisories.yml). The `Verification` view displays only current, validated, enum-based proof-gap proposals. Secrets and raw model output are not committed to Pages. See [Hosted Actions AI setup](HOSTED_ACTIONS_AI.md). For interactive chat, an independently authenticated server is still required.
