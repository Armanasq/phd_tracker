# GitHub repository configuration

These settings describe the intended repository presentation and Pages configuration. The repository admin must apply About fields in GitHub Settings; file commits do **not** alter the GitHub About metadata.

## About

- **Repository:** Armanasq/phd_tracker
- **Display name:** PhD Atlas
- **Description:** Evidence-backed PhD application tracker with deadlines, research fit, source verification, and optional private AI agents.
- **Website:** https://armanasq.github.io/phd_tracker/
- **Topics:** phd-applications, phd-tracker, research-management, source-verification, github-pages, agentic-ai, ai-agents, python, javascript, llm

Open the repository homepage, select the **About** gear icon, and enter the description, website, and topics above. Keep the repository name unchanged to preserve existing links.

The same fields are versioned in [`repository-metadata.json`](repository-metadata.json). Forks may replace the JSON repository identity with their own owner/name and customize description/topics. Run `python scripts/sync_repository_metadata.py` for a read-only preview. The [About metadata workflow](workflows/repository-metadata.yml) verifies these values on source changes; to **apply** them, a repository administrator must configure the `github-admin` protected Actions environment with a `GITHUB_ADMIN_TOKEN` secret that has repository Administration-write permission, then manually run the workflow with **Apply=true**. It never mutates About on a push and reports failure if authorization is absent or live verification disagrees. The connected GitHub App still lacks a direct About-metadata write action.

## Pages

In **Settings → Pages**, keep the build source set to **GitHub Actions**, not "Deploy from a branch". The deployment workflow is `.github/workflows/publish-cockpit.yml`, and the canonical public URL is `https://armanasq.github.io/phd_tracker/`. No custom domain is configured. Do not add a CNAME unless a domain is owned and DNS is configured.

The Pages pipeline creates `site/data/workspace.json` from committed data, packages `site/`, deploys through `actions/deploy-pages`, then verifies the published HTML, JavaScript and JSON schema. A green workflow verifies the deployed assets; it does **not** certify every university claim.

## Access and defaults

- **Default branch:** `main`
- **Visibility:** public
- **Issues:** enabled for evidence corrections and proposed leads
- **Wiki:** disabled; maintained documentation lives under `docs/`
- **Private credentials:** never stored in the repository or public Pages
- **Review policy:** prefer pull requests with passing Python and browser checks; require evidence for source-data changes

## Automation permissions

Pages uses `contents: read`, `pages: write` and `id-token: write`. Code quality runs use `contents: read`. The README renderer and versioned release workflow request `contents: write` because they publish generated files and GitHub Releases. Avoid granting broader workflow token permissions.

## Release

`VERSION` is the release identifier, `CHANGELOG.md` is the release-note source, and `.github/workflows/release.yml` creates a matching prerelease if one does not already exist. Do not move or replace an existing tag automatically; increment `VERSION` and update the changelog for a new release.

## Privacy and accuracy

The public tracker is not a user-authenticated service. The local private Python backend is a different trust boundary and requires separate startup, provider verification and explicit cloud consent. Do not imply that GitHub Pages can access the user's local vLLM, Ollama, Azure credential store or SQLite database.

## Latest verified About-field discrepancy (2026-11-09)

The repository API returned an empty description, empty homepage and no topics even though the desired values were present in the tracked metadata JSON file. An authorized repository administrator must apply these settings using GitHub About or the protected metadata workflow with an administration-write token. Verification runs on metadata changes and fails rather than reporting success when live fields do not match. Do not interpret a metadata-sync failure as evidence that the Pages application failed to build.
