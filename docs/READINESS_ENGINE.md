# Submission readiness and proof-gap planning

The [Readiness](../site/index.html#readiness) workspace turns recorded application facts into bounded next actions using deterministic, source-aware rules. It works in GitHub Pages, local static hosting, and the Python loopback runtime without requiring model credentials.

## Record authority

The planner reads the validated public `workspace.json`, overlaid with device-local drafts and device-only applications. It does not update the source repository, store receipts in Pages, call an LLM, submit an application, or claim admission eligibility.

| Record phase | Behavior |
| --- | --- |
| Active | Show proof, preparation, follow-up, and route checks |
| Submitted | Check owner-confirmed receipt privately and follow-up; never enqueue a second submission |
| Owner blocked | Surface the explicit blocker, exclude from actionable applications |
| Expired | Date passed; confirm route availability without inferring late acceptance |
| Offer, rejected, withdrawn or archived | Closed; not in active queue |
| Research candidate | Excluded until explicitly promoted |

The planner only marks preparation work when a document is explicitly `not_started` or `in_progress`. A document state of `unknown` is a proof obligation, not a missing document. A record with no official requirements scope needs separate review. A recorded date is not proof of closing time or timezone. A submitted status is not the same as a portal receipt.

## Execution decisions

The queue sorts by actionable evidence/proof category, deadline proximity and user-entered priority. It does not compute a readiness percentage, estimated success probability, time-to-completion, or an admission score.

Actions are grouped into official-source review, deadline/cutoff verification, explicit document preparation, document scope, applicant eligibility and funding, possible duplicate routes, owner-recorded action, and faculty follow-up. The top action is a triage suggestion; the record view explains the reason and links to primary evidence.

The portfolio planner also counts shared document requirements across active applications. It never assumes a statement, recommendation letter or CV can be reused unchanged. Same-date deadline collisions are flags for review, not proof of multiple independent applications.

## Behavior and privacy

- All source and local state shown in the view is read-only until a user explicitly edits a record through existing controls.
- The export includes application IDs, name, phase, recorded dates, top action/category, proof and preparation counts, and official source URL. It never includes notes, receipts, credentials or model prompts.
- Existing CSV escaping protects against spreadsheet formula injection.
- The same code and UI run on a fork's own repository with an initially empty starter dataset. It does not read upstream applicant data in independent source mode.
- A GitHub-hosted AI advisory is not required for readiness calculations and cannot mark a source or submission verified.

## Tests and deployment

```bash
node --check site/modules/readiness.mjs
node --check site/modules/readiness-view.mjs
node --test tests/readiness.test.mjs tests/readiness_view.test.mjs
node --check site/app.js
```

The Pages build and code-quality workflow include these checks. Release manifests bind both modules to the deployed commit so a successful deploy verifies the corresponding JavaScript assets.
