# EvidenceGraph — PhD opportunity intelligence engine

## System scope

**Current implementation:** a private, evidence-first workbook reconciliation pipeline, with an opt-in Gmail metadata connector and daily GitHub Actions execution. It does **not** automatically submit applications, infer citizenship eligibility, change a user's application state, or guarantee that a website remains current.

**Product hypothesis:** a defensible, continuously updated candidate-to-lab opportunity intelligence system that treats admissions as a time-dependent, verifiable decision, rather than a static keyword-search list.

### Research and patterns combined

- [changedetection.io](https://github.com/dgtlmoon/changedetection.io): website state tracking, change detection, targeted monitoring.
- [GPT Researcher](https://github.com/assafelovic/gpt-researcher): parallel research and provenance-linked synthesis. We implement narrowly scoped deterministic verifier workers, not an unchecked LLM writer.
- [Crawl4AI](https://github.com/unclecode/crawl4ai): future source adapters and dynamic-page extraction behind a documented interface.
- [dlt](https://github.com/dlt-hub/dlt): incremental, source-scoped state, schema contracts and idempotent merge semantics.
- [Prefect](https://github.com/PrefectHQ/prefect): retryable, inspectable workflow state. Current small-scale implementation uses Actions; Prefect is not installed.

These are researched design inputs, not copied source code or claims of a world-first invention.

## Event model

1. **Observe**: ingest primary programme sources and (with separately configured read-only OAuth) Gmail message metadata.
2. **Resolve identity**: key observations by source ID and application cycle. Preserve existing source IDs; never equate an admission year with an application year.
3. **Verify source**: only official sources can promote a candidate into the main action list. A page may corroborate a deadline but may not be used to infer funding, immigration eligibility, or fee classification.
4. **Detect disagreements**: store expected dates/anchors alongside observed source status. Contradictory source statements are queued for review; existing data are not overwritten on weak evidence.
5. **Reconcile workbook**: import a small human-curated, provenance-rich batch; deduplicate source IDs; sort by calendar deadline; refresh as-of formulas.
6. **Validate**: fail on missing tabs, duplicate IDs, missing provenance and unsorted main list.
7. **Publish**: GitHub Actions makes a committed, traceable spreadsheet snapshot. User status transitions require explicit user action.

## Information boundaries

| Class | Allowed action |
|---|---|
| Official dated call, applicant eligibility remains uncertain | Main action list with explicit risk and official URL |
| Supervisor email only | Research queue; manual verification required |
| Conflicting official website and supervisor email | Research queue with contradiction note |
| Gmail application support message | Mail signals (not an inferred submission) |
| Already-passed deadlines | Historical record or exclusion |
| Home-fee-only or other restrictive funding | Exclude or flag; never treat as universally funded |
| Untrusted web content | Data-only; no execution or prompt privileges |

## Engineering properties

- Idempotent upsert for original and new opportunity source IDs.
- Source URL allowlist on automated HTTP fetches, bounded responses, timeouts and limited parallelism.
- Distinguish `anchor_present` from comprehensive correctness; only a string-match monitor currently exists.
- Existing Excel worksheet structures, editable source IDs, previous route verdicts and user actions are preserved.
- Published files are evidence and status snapshots, not outputs from unconstrained model calls.
- Gmail OAuth (optional): **read-only** API access, newest 50 matching message metadata per run, no full message bodies, credentials stored only in repository Secrets.
- Workflow defaults to no Gmail access if secrets are missing.
- GitHub `GITHUB_TOKEN`: repository-scoped write for committing only; no personal GitHub token required.
- Automated workflow runs at 05:17 UTC daily and on manually initiated dispatch.
- For high-assurance deployment, pin action dependencies by commit SHA, add dependency scanning and sandbox crawling workers.

## Differentiated future product: Temporal EvidenceGraph

The defensible concept is not another AI job alert service. A typed graph stores assertions, their exact source, observation time, candidate dependency, and invalidating counterevidence. It answers:

1. *Which deadlines changed after I requested a letter?*
2. *Which calls fund tuition for my specific eligibility class?*
3. *What evidence is still missing for a high-probability application?*
4. *Which one action unlocks the most viable applications before their deadlines?*

Plan a constrained optimizer over resources (references, documents, application fees, supervisor contact windows) and uncertainty (unknown citizenship restrictions, fee status, optional tests). Use confirmed inputs for decisions and surface unknowns as explicit proof obligations. Feedback from interview offers, acceptance rates, and successful application portfolios should be aggregated only with explicit consent and de-identification.

## Commercial hypothesis / constraints

Potential customers include applicants, labs recruiting funded students, and universities administering graduate recruitment. Core workflows: verified deadline monitoring, funding/eligibility evidence, applicant-lab match explanation, and privacy-preserving application workflow coordination.

A billion-dollar valuation is not a verified outcome. First validation milestones: source accuracy, false deadline alerts, eligible-open-application recall, time to identify a suitable supervisor, conversion from discovery to qualified application, paid retention, source licensing and privacy/compliance costs. No market size or valuation estimate is asserted without data.

## Run and test

```bash
python -m pip install openpyxl==3.1.5
python scripts/refresh_tracker.py --date 2026-11-06
python scripts/validate_tracker.py
```

To check official page anchors, add `--online`. Daily scheduled execution is configured in [refresh-tracker.yml](../.github/workflows/refresh-tracker.yml).

To enable automatic Gmail intake, configure repository secrets `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN` for a dedicated account-specific OAuth client with `gmail.readonly` scope. No messages are sent or modified. The pipeline stores only subject, date, message link and review status.

## Known limitations

- An HTTP 200 and unchanged deadline phrase do not prove the position is open. Website parsing is a monitoring signal, not a formal verification.
- Email connector is not available inside the Action until the three OAuth secrets are configured.
- No UI, hosted database, custom model, applicant decision optimizer, or commercialization has been deployed.
- The live Google Sheet is not synchronized back from GitHub; `PhD_Action_List.xlsx` in the repository is the edited target, preserving the Google Sheet as a read-only source for this change.
