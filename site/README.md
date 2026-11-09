# PhD Atlas — Fall 2027

GitHub Pages application management interface, preserving the repository's existing workbook, applications, evidence and notification pipelines.

## Interface

Overview, Applications, Calendar, Pipeline, Actions, Contacts, Changes, Compare, Verification, Expired / blocked and Sources. The visual system uses a calm light-first editorial layout with a compact mobile navigation instead of a conventional card-heavy dark dashboard. Search/filter/sort, side-by-side comparison, daily prioritization, faculty follow-ups, document state, candidate leads, risk flags, calendar export, CSV/JSON export, local draft editing and browser notifications.

## Authoritative data

The original workbook and committed JSON remain authoritative. `scripts/build_workspace.py` generates `site/data/workspace.json` from existing evidence and optional `data/workspace_overrides.json`. The browser never silently changes the workbook or source records. “Unknown” document state does not mean missing; date and deadline time are distinct; heuristic duplicates require owner review.

## Owner updates

1. Open an application and edit status, evidence verification, documents, next step and follow-up.
2. Save locally or copy the `/workspace {...}` command.
3. Paste the command into the authenticated owner [Action Center issue](https://github.com/Armanasq/phd_tracker/issues/1).
4. The `workspace-controls.yml` workflow checks issue marker, owner login, source ID and allowed values, and commits owner overrides to `main`.
5. The Pages publishing workflow regenerates its projection on the committed change. Discard the local draft only after confirming the source update.

Existing `/asset`, `/done`, `/snooze`, `/priority` controls remain supported by the original workflow. No implicit application submission occurs.

## Reminders

The browser can notify at 7/3/1/0-day milestones while the page is open, where permission is granted. Scheduled notifications remain the responsibility of the existing GitHub Actions notification pipeline; optional external Apprise delivery requires its configured secret.

## Deployment

Repository Settings → Pages → Source: GitHub Actions. The `publish-cockpit.yml` workflow publishes `site/` on relevant pushes and manual dispatch. GitHub Pages availability and privacy depend on the repository and account configuration.

## Privacy boundary

This repository and its GitHub Pages deployment are public. The projection suppresses Gmail links, email addresses, correspondence bodies and historical exclusion reasons. Public issue commands are intentionally limited to non-sensitive operational fields. Private notes and receipt links are device-local and deliberately excluded from GitHub synchronization. Do not paste confidential applicant information into public issues. Local drafts are browser-device-specific and should be exported regularly.

## Validation

```bash
python scripts/build_workspace.py --out site/data/workspace.json
python -m unittest discover -s tests -p 'test_workspace.py'
node --check site/app.js
```

## Integrated visualization and browser QA

The existing interactive EvidenceGraph dashboard is preserved and published at `/evidencegraph/` beside PhD Atlas. The `visual-qa.yml` workflow runs the legacy dashboard smoke test and the new PhD Atlas browser suite, including filters, calendar, pipeline drag-and-drop, comparisons, local edits, exports and mobile screenshots. It uploads rendered screenshots as a GitHub Actions artifact.
