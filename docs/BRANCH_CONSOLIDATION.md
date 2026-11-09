# Branch consolidation record — 2026-11-09

The project uses a single active branch, `main`. The three previous branches were reviewed before the final history reconciliation.

| Legacy branch | Reviewed tip | Original merged PR | Disposition |
| --- | --- | --- | --- |
| `feature/experiencegraph-cockpit` | `e2d116cfde6912a2eb4a4e1ddc41895a6bc41de5` | [#2](https://github.com/Armanasq/phd_tracker/pull/2) | Six later commits adjusted an earlier README presentation and source-relative report links. The current `scripts/experience_engine.py` retains the report-link correction, has an expanded evidence and simulation workflow, and its checks remain on `main`. The compact current `README.md` and generated `docs/RESEARCH_REPORT.md` intentionally replace the older dashboard-first README. |
| `feature/atlas-context-backend` | `c5b792c8d5f9b8fb68774a0e3a6e9ca1ff83f040` | [#3](https://github.com/Armanasq/phd_tracker/pull/3) | Backend engine, relevance, conversation persistence, server, client widget and assistant contract tests match the main branch file blobs. |
| `chore/repository-release-polish` | `3d755b19ca40baa508f14deb2ca30b0f1f9bf3ed` | [#4](https://github.com/Armanasq/phd_tracker/pull/4) | Project README, site metadata, release workflow, repository metadata source, and generator code match the main branch file blobs. The generated research report on main includes subsequent automated refreshes. |

## Integration strategy

All three pull requests were merged before this reconciliation. As squash merges do not make the original branch tip an ancestor of `main`, a multi-parent reconciliation commit is used with the **current main tree** as its content. This preserves the historical branch commits in Git's ancestry without reinstating outdated generated pages, README content, or CI jobs.

No source code or application evidence is overwritten by the reconciliation. Each legacy branch ref may be deleted only if its tip equals the reviewed SHA and Git confirms it is an ancestor of the reconciliation commit. GitHub Actions performs these checks in `.github/workflows/consolidate-branches.yml`.

The `v0.1.0` release tag remains an immutable reference to the published release. Deleting obsolete working branch refs does not delete release tags, pull requests, or the branch commits made reachable by the merge.

## Repository About metadata

The live repository About description, website, and topics are separate administrative fields. Their desired values are versioned at `.github/repository-metadata.json`; the opt-in sync script at `scripts/sync_repository_metadata.py` requires a repository-administration token. Ordinary Git contents write permission is not equivalent to administration permission. The workflow attempts synchronization and reports whether GitHub accepted it; if GitHub denies the request, the user must configure a separate admin-scoped secret or use the About panel.

Canonical site: https://armanasq.github.io/phd_tracker/
