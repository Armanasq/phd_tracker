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
3. Run **Actions -> PhD Atlas | Publish GitHub Pages Workspace -> Run workflow**, or push edited source data to `main`. The default deployment intentionally contains no application records. After replacing and verifying your own sources, set repository Actions variable `PHD_ATLAS_DATA_MODE=source` and rerun the publisher. It derives the site identity from `GITHUB_REPOSITORY` and publishes under your account.
4. Inspect the deployed `instance.json`, `release-manifest.json`, `data/workspace.json`, sitemap, and source links. The manifest binds published files to the source commit. A green deploy does not establish university claim accuracy.
5. To use owner-controlled public status updates, enable Issues, create an **Owner Action Center** issue from the included issue template, and set repository Actions variable `PHD_ATLAS_ACTION_ISSUE` to its number. Without the variable, the application links to the issue-creation template rather than guessing `issues/1`.

For a custom domain, configure the actual Pages domain in GitHub first, and set the Actions repository variable `PHD_ATLAS_SITE_URL` to the HTTPS site root. This controls the generated canonical link, Open Graph URL and sitemap; a variable alone cannot register DNS or a Pages custom domain.

The publisher never writes credentials to the static artifact. Forks must independently configure GitHub Actions permissions and optional discovery sources; upstream GitHub secrets and local SQLite files are not inherited.

### Browser-local opportunities on any deployment

The Applications view provides **Add opportunity**, **Local backup**, and **Import backup**. Opportunity details can be edited and deleted without a backend. These records remain only in the current browser storage and are explicitly marked device-only; clearing browser data deletes them unless a backup has been exported. Import merges distinct local IDs and never overwrites an existing record automatically.

Use **Export → GitHub source JSON (public fields)** to create `experience_view.json` from device-local opportunities. The export deliberately omits local notes, receipt links, and local submission state. Before publishing it to a fork, review the generated records and remove inherited application data from other files under `data/`, especially `data/opportunities.json`, `data/decision_queue.json` and `data/workspace_overrides.json`. The fork remains in blank `starter` mode until `PHD_ATLAS_DATA_MODE=source` is explicitly set. Exporting does not commit or submit anything.

Device-local data is not encrypted and must not be treated as confidential storage on a shared browser or same-origin hosting service; use the loopback SQLite backend for genuinely private applicant information. GitHub source exports are public once committed.

### Build and configure a different repository explicitly

```bash
python scripts/build_workspace.py --repository YOUR_ACCOUNT/YOUR_REPOSITORY --data-mode source --out site/data/workspace.json
python scripts/instance_config.py --repository YOUR_ACCOUNT/YOUR_REPOSITORY --site site
python -m http.server 8000 --directory site
```

Identity precedence is: explicit `--repository`, `PHD_ATLAS_REPOSITORY`, `GITHUB_REPOSITORY`, local git origin, then the upstream default. Remote detection accepts only GitHub HTTPS or SSH URLs. The optional site metadata preparation step updates the local site artifact, not the repository's GitHub About settings.

**Public-data contract:** A fork starts in `starter` mode with zero tracked applications. `PHD_ATLAS_DATA_MODE=source` opts in to serving only that repository's source files. Private applicant notes, correspondence, receipts and credentials must not enter `data/*.json`, GitHub Issues or Pages artifacts.

### Validation

```bash
python -m unittest discover -s tests -p 'test_instance_config.py'
python -m unittest discover -s tests -p 'test_workspace.py'
node --test tests/domain.test.mjs tests/storage.test.mjs tests/local_records.test.mjs
node --check site/app.js
```

This verifies routing, metadata generation, public source links, instance identity and a minimal independent source dataset. A fork's dataset is not guaranteed complete and must be verified against primary university sources.

Browser draft keys are namespaced by host and Pages project path, preventing accidental mixing among repos. Namespacing is **not a security boundary**: pages under the same hostname can read the same browser-origin storage. Keep sensitive applicant state in the private local runtime.

Detailed [source ownership, synchronization state machines and deployment contracts](DATA_FLOW.md) describe the trust boundaries and invariants.

The repository currently has no explicit software `LICENSE` file. Users who need redistribution rights outside GitHub's platform terms should obtain permission until the maintainer selects a license.
