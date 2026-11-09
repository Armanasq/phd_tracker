# Running PhD Atlas on a local machine or another GitHub repository

## Deployment and data ownership

| Deployment | User interface | Public evidence | Private state | Model execution |
| --- | --- | --- | --- | --- |
| GitHub Pages (upstream or fork) | Static HTML/JS | Published \`data/workspace.json\` | Browser-local drafts only | No |
| Local static server | Same HTML/JS | Locally built snapshot | Browser-local drafts | No |
| Python runtime on loopback | Same HTML/JS | Locally built snapshot | Private SQLite | Yes, when configured and consented |

GitHub Pages is a static host. Python, SQLite, API keys, provider authentication, and recurring private agent runs do **not** run on GitHub Pages. The public application deliberately does not call a local service from a hosted origin. For authenticated AI execution, open the **same UI served by the local runtime**.

### Run locally

Requirements: Python 3.11+, git, and a browser. From your own clone:

\`\`\`bash
git clone https://github.com/Armanasq/phd_tracker.git
cd phd_tracker
python -m pip install -r requirements-intelligence.txt
python scripts/build_workspace.py --out site/data/workspace.json
python -m http.server 8000 --directory site
\`\`\`

Open \`http://127.0.0.1:8000/\`. File URLs (\`file://\`) are not supported because module imports and data fetches require HTTP. The static server does not expose the private Python agent API.

To use local/cloud model providers, private application updates, scheduled workflows and SQLite:

\`\`\`bash
python -m phd_agents serve --port 8765
\`\`\`

Open \`http://127.0.0.1:8765/#settings\`. Configure a real OpenAI-compatible/other supported endpoint in Settings; local models must already be running. The private server listens only on loopback and is not suitable for internet exposure without an independently designed authentication and reverse-proxy deployment.

### Publish your own GitHub Pages site

1. Fork or copy the repository to \`YOUR_ACCOUNT/YOUR_REPOSITORY\`. A fork initially includes the original maintainer's *public* opportunities and source data; they do not become your own applications. **Replace the source files before publishing your personal tracking information.** Never publish private emails, credentials or application receipts.
2. Keep \`main\` as the default branch. In **Settings → Actions**, enable GitHub Actions for the fork as required. In **Settings → Pages → Build and deployment**, select **GitHub Actions**.
3. Run **Actions → PhD Atlas | Publish GitHub Pages Workspace → Run workflow**, or push your edited source data to \`main\`. The publisher uses \`GITHUB_REPOSITORY\` for repository identity and automatically computes \`https://YOUR_ACCOUNT.github.io/YOUR_REPOSITORY/\` (or \`https://YOUR_ACCOUNT.github.io/\` for a user-site repository).
4. Inspect the deployed \`instance.json\`, \`release-manifest.json\`, \`data/workspace.json\`, sitemap, and source links. The manifest binds published files to the source commit. A green deploy does not establish university claim accuracy.
5. To use owner-controlled public status updates, enable Issues, create an **Owner Action Center** issue from the included issue template, and set repository Actions variable \`PHD_ATLAS_ACTION_ISSUE\` to its number. Without the variable, the application links to the issue-creation template rather than guessing \`issues/1\`.

For a custom domain, configure the actual Pages domain in GitHub first, and set the Actions repository variable \`PHD_ATLAS_SITE_URL\` to the HTTPS site root. This controls the generated canonical link, Open Graph URL and sitemap; a variable alone cannot register DNS or a Pages custom domain.

The publisher never writes credentials to the static artifact. Forks must independently configure GitHub Actions permissions and optional discovery sources; upstream GitHub secrets and local SQLite files are not inherited.

### Build and configure a different repository explicitly

\`\`\`bash
python scripts/build_workspace.py --repository YOUR_ACCOUNT/YOUR_REPOSITORY --out site/data/workspace.json
python scripts/instance_config.py --repository YOUR_ACCOUNT/YOUR_REPOSITORY --site site
python -m http.server 8000 --directory site
\`\`\`

Identity precedence is: explicit \`--repository\`, \`PHD_ATLAS_REPOSITORY\`, \`GITHUB_REPOSITORY\`, local git origin, then the upstream default. Remote detection accepts only GitHub HTTPS or SSH URLs. The optional site metadata preparation step updates the local site artifact, not the repository's GitHub About settings.

**Public-data contract:** only reviewed, sanitized evidence should enter \`data/*.json\` and Pages snapshots. Never commit secrets or applicant correspondence. Personal application statuses and agent conversations remain in private SQLite, unless deliberately reduced to non-sensitive fields and confirmed through the owner Action Center.

### Validation

\`\`\`bash
python -m unittest tests.test_instance_config
python -m unittest discover -s tests -p 'test_workspace.py'
node --test tests/domain.test.mjs
node --check site/app.js
\`\`\`

This verifies routing, metadata generation, public source links, instance identity and a minimal independent source dataset. A fork's dataset is not guaranteed complete and must be verified against primary university sources.
