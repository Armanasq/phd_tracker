# Release readiness and source coverage

## Public application architecture

The original workbook, versioned evidence records, research candidates, execution tasks and source-monitor results are distinct datasets. The public site is a generated projection, not an authenticated database.

| Public dataset | Interpretation |
| --- | --- |
| records | Tracked application opportunities plus unpromoted research candidates |
| tasks | Relevant operating-window steps from the broader original workbook |
| archive | Summaries of historical exclusions and deferred routes |
| leads | Unpromoted research leads; not verified active positions |
| coverage.worksheets | Row counts and dated audits of each original workbook sheet |
| coverage.files | Links to versioned public evidence layers |
| coverage.discovery_errors | Observed failures and degraded third-party search sources |
| providers | Recorded source-discovery health, not guaranteed coverage |

The original workbook audit date can differ from the daily application projection. Worksheet rows, task steps, candidate leads and tracked applications must never be added together as though they have identical grain.

## Evidence gates

The verification queue is deterministic and source-aware. It flags missing exact closing-hour proof, missing official source, incomplete evidence review, unknown documents, explicitly not-started documents, possible duplicate submission routes, overdue owner decisions and missing submission receipts. A flag does not independently establish that a university requirement is missing or that an opportunity remains available.

No autonomous application submissions, referee verification or correspondence sending are available through public Pages. Sensitive owner records and model credentials remain within the separate local Python runtime.

## Deployment integrity

1. GitHub Actions builds the site/data/workspace.json projection on each Pages deployment.
2. The workflow validates Python contracts, JavaScript modules, and the evidence-assurance test suite.
3. It generates site/release-manifest.json, recording the deploying commit SHA and SHA-256 hashes of critical assets.
4. Pages deploys the generated static site.
5. The workflow retrieves published HTML, data, audit module and manifest, and checks that the published manifest corresponds to the deploying commit.

Check the specific Actions run for the current main commit before declaring release success. CI can pass while Pages is not yet updated, and a previously green deployment cannot prove the current code is live.

## Repository configuration

The desired description, homepage and topics are stored in .github/repository-metadata.json. Applying them to GitHub's About panel requires an authorization scope supporting repository administration writes. The workflow independently verifies the returned live fields and fails when permission or synchronization is missing.

The repository has no declared software license. An explicit owner decision is required before granting reuse permissions.

## Remaining production qualifications

- External source feeds can return permission errors or incomplete search results.
- Portal cutoff clocks, funding terms, international eligibility and submission receipts require current official evidence.
- Public Pages cannot securely store personal API keys or run private LLM agents.
- The loopback agent runtime lacks public multi-user authentication, managed encrypted secret storage and a service-level guarantee; it must not be exposed directly to the Internet.
- Automated browser tests are not a complete security audit, real-user performance assessment or certified WCAG conformance review.
- Public git history may contain information omitted from the generated site and requires independent privacy inspection.
