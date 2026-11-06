# Operating playbooks

[Command center](../README.md) · [Capabilities](CAPABILITY_ATLAS.md) · [Today's agenda](TODAY.md)

## 1 — A final application deadline is within 72 hours

1. Open [Today's plan](TODAY.md) and distinguish final submission deadlines from preparation tasks.
2. Verify the institution's primary posting, its actual portal status, closing time/time zone, international funding, nationality eligibility, and required references.
3. Review the [proof-obligation frontier](../data/portfolio_frontier.json). Unknown asset readiness remains unknown; a mention of transcripts does not establish that they are missing.
4. Prepare shared materials once, but adapt the research statement to the exact supervisor and programme.
5. Save the submission receipt, then explicitly update user-owned status. Never infer completion from email keywords.
6. For dated tasks, copy the stable task ID and use /done TASK_ID on the [Action Center](../../issues/1).

## 2 — A new funded PhD lead appears

1. Open [Discovered candidates](../data/discovered_candidates.json) and check stable ID, source URL, first_seen, evidence status and relevant research topics.
2. Locate the current institutional advertisement. A search engine snippet, a scientific paper, or an aggregator mirror is not enough.
3. Independently verify date, funding including international tuition, nationality/residency constraints, supervisor, admissions route and documents.
4. Compare source URL and cycle with existing rows and [exclusion memory](../data/exclusion_memory.json). Reappearance of a previously rejected source means review, not permanent exclusion.
5. Resolve evidence contradictions before considering promotion from Research queue to Action list.

## 3 — The deadline changed or the portal closed

1. Inspect both stored and proposed dates in [source observations](../data/discovered_candidates.json).
2. Confirm the university webpage and the application portal separately. Record both URLs and observation time.
3. Contact programme administration when those disagree.
4. Do not overwrite the old date automatically; preserve the conflict as a review item.
5. Run the [reconciliation workflow](../.github/workflows/phd-intelligence.yml), then inspect the diff and workbook audit.

## 4 — Which task should be done first?

1. Confirm actual readiness for shared CV, research statement, transcripts, references and English proof in [application assets](../data/application_assets.json).
2. Inspect [portfolio leverage](../data/portfolio_frontier.json), considering deadline proximity and the number of opportunities sharing each resource.
3. Prioritize confirmed blockers before cosmetic document work. Keep uncertain eligibility as a separate proof obligation.
4. Recheck reference-arrival deadlines, not just dates to request letters.

## 5 — Control reminders without alert fatigue

Comment on the [private Action Center](../../issues/1) using one command per comment:

~~~text
/priority N263-09
/snooze N263-09 3d
/unsnooze N263-09
/mute N263-09
/unmute N263-09
/asset academic_cv ready
/asset research_statement in_progress
/done tsk-51298cbed7152c90
/reopen tsk-51298cbed7152c90
~~~

Commands are owner-scoped, restricted to known IDs and deliberately non-executable. Deadline-day and day-before reminders bypass ordinary muting/snoozing. They do not submit applications.

## 6 — Connect discovery and outbound notifications

GitHub Issues notifications work through the repository. External channels supported by the Apprise adapter require an APPRISE_URLS secret and verified delivery. Broad search requires BRAVE_SEARCH_API_KEY. Automatic Gmail metadata polling requires GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, and GMAIL_REFRESH_TOKEN with gmail.readonly authorization. Email bodies are not committed.

## 7 — A green workflow returns no new opportunities

1. Inspect [source telemetry](../data/discovery_report.json) independently of the GitHub Action status.
2. Differentiate disabled connector, HTTP 403, no matching vacancies, true duplicates and parser breakage.
3. Measure unique verified opportunities, reobservations and how long the source has been stale.
4. Do not interpret zero crawl results as zero vacancies worldwide. Repair the adapter or credentials before widening a claim.

## 8 — A new paper resembles your research trajectory

[Research radar](../data/research_radar.json) helps select technical reading and potential research directions. Verify the author's current institution and research group independently; a publication is neither a vacancy nor a funding commitment.

## 9 — Recovery after a faulty automation update

Inspect the commit, evidence provenance and [cross-sheet audit](../data/workbook_audit.json). Restore affected artifacts from a known-good commit without overwriting human-maintained statuses. Run the regression suite and verify the workbook's source IDs, formulas and sheet inventory.

## Evidence truth table

| Never infer | Required confirmation |
|---|---|
| Vacancy open | Current official advert and accessible portal |
| International tuition funded | Explicit funding/fee category evidence |
| Application submitted | Portal receipt or explicit user confirmation |
| Recommender completed | Submission confirmation |
| A past task unfinished | Explicit task state |
| Publishing lab hiring | Separate recruiting notice |
| Worldwide search complete | Measured source-panel recall |
