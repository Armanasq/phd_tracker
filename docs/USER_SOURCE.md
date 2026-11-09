# Independent opportunity source contract

A fork's Pages build starts with an empty workspace. To publish your own opportunities, create `data/user_opportunities.json`; independent builds never consume the original workbook or upstream owner status records.

## Browser-to-GitHub flow

1. Open the forked Pages site and use **Applications → Add opportunity**. Records remain in the browser until exported.
2. Open **Updates → Export GitHub source**. This downloads `user_opportunities.json`, strips local notes and receipts and resets publication verification to `unverified`.
3. Review source URLs and privacy, then commit this file at `data/user_opportunities.json` on the fork's `main`.
4. Set repository Actions variable `PHD_ATLAS_DATA_MODE=source` and run **PhD Atlas | Publish GitHub Pages Workspace**.
5. Inspect the deployed `data/workspace.json` and `instance.json` for repository ownership, source mode, source SHA and record counts.

Alternatively start from the intentionally empty [JSON template](../data/user_opportunities.example.json):

```bash
cp data/user_opportunities.example.json data/user_opportunities.json
python scripts/build_workspace.py --repository YOUR_ACCOUNT/YOUR_REPOSITORY --data-mode source --out site/data/workspace.json
python -m http.server 8000 --directory site
```

## Schema

```json
{
  "schema_version": 1,
  "as_of": null,
  "timezone": "Europe/Berlin",
  "records": [
    {
      "id": "MY-001",
      "name": "Illustrative programme; replace with a real listing",
      "record_type": "tracked",
      "deadline": null,
      "deadline_type": "unverified",
      "verification": "unverified",
      "status": "unconfirmed",
      "source_url": "",
      "documents": ["academic_cv"],
      "document_states": {"academic_cv": "unknown"},
      "next_step": "Verify the official primary-source call"
    }
  ]
}
```

This example record is **not a real PhD opening**. The checked-in template includes an empty records array to prevent accidentally publishing fabricated opportunities.

Fields `id` and `name` are required. IDs must be unique and safe (alphanumeric start, up to 80 characters, remaining characters alphanumeric, period, hyphen or underscore). The source accepts at most 5,000 records. `timezone` must be a valid IANA timezone; `as_of`, `deadline`, `followup` and `source_date` must be actual ISO dates or null. Invalid or unsupported fields cause a build failure.

Accepted `record_type`: `tracked`, `candidate`. Accepted `verification`: `unverified`, `needs_review`, `source_verified`, `owner_verified`. Accepted `status`: `unconfirmed`, `shortlisted`, `preparing`, `submitted`, `interview`, `offer`, `rejected`, `withdrawn`, `blocked`, `archived`. Accepted `deadline_type`: `unverified`, `final`, `rolling`, `internal`, `other`.

Supported document keys: `academic_cv`, `research_statement`, `transcripts`, `recommendations`, `english_proof`, `research_portfolio`. Supported document states: `unknown`, `ready`, `in_progress`, `not_started`, `not_applicable`. Priority is `low`, `normal`, `high`. Other public fields include institution, country, faculty, funding, eligibility, fit, topic, next_step, blockers, decision, contact_status, evidence and boolean duplicate_submission_advisory.

`source_url` and `apply_url` must be public HTTPS links without embedded credentials. Marking `source_verified` or `owner_verified` requires a primary URL, `source_date` and explanatory `evidence`; the validator checks these fields but **cannot prove a university page remains current**.

Private `notes`, `receipt`, `submission_receipt`, applicant email and authentication tokens must not enter this file. Unknown keys are rejected. The file is public after a GitHub commit.

## Owner updates and private runtime

For public-safe status changes, enable Issues, create an Owner Action Center issue, set `PHD_ATLAS_ACTION_ISSUE` to its number, and post the UI-generated `/workspace` command. Only the repository owner can run it. Optimistic version checks apply, and accepted updates write only to `data/user_workspace_overrides.json`. Browser draft status is not evidence of a successful GitHub commit.

The local private runtime starts with:

```bash
PHD_ATLAS_DATA_MODE=source python -m phd_agents serve --port 8765
```

Open `http://127.0.0.1:8765/#settings` and configure private model providers there. Do not expose this loopback server to the internet without an independently designed authenticated service. On GitHub Pages, JavaScript `localStorage` is origin-wide even when keys are namespaced by project path; browser drafts are not confidential storage.

The inherited scheduled discovery job is disabled on forks unless the owner sets Actions variable `PHD_ATLAS_ENABLE_DISCOVERY=true`. Publishing the fork's own opportunities never requires enabling discovery.
