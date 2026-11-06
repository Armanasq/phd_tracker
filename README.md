# EvidenceGraph — PhD Application Tracker

Private, provenance-aware tracker for funded doctoral opportunities, application deadlines, funding eligibility, evidence conflicts and reviewable Gmail signals.

## Current dataset

- [Excel workbook](PhD_Action_List.xlsx), including the original six tabs and four new operational tabs: **Research queue**, **Mail signals**, **Evidence ledger**, **Source watch**.
- [Curated opportunities and evidence](data/opportunities.json) — 3 official-source-backed entries promoted to the deadline-ordered action list, 5 leads kept in review.
- [Gmail findings](data/mail_signals.json) — condensed status evidence from this user's authorized Gmail search; no raw email bodies.
- [Primary source monitors](data/watchlist.json) and [latest run report](data/latest_run.json) (created after the automated refresh).
- [Architecture, research, threat model and roadmap](docs/ARCHITECTURE.md).

## Automation

[Daily evidence-first GitHub Action](.github/workflows/refresh-tracker.yml) runs at **05:17 UTC**, or manually from Actions. It:

1. Optionally reads recently arrived Gmail *metadata* through a separately configured OAuth client.
2. Checks a strictly allowlisted set of official source URLs with four bounded workers.
3. Updates only corroborated opportunities in the main action list; sends uncertain leads to review.
4. Refreshes the as-of date and deadline formulas without changing user submission statuses.
5. Detects source-state transitions, preserves provenance, validates, and commits changes.

Use **Actions → Evidence-first PhD tracker refresh → Run workflow** for an immediate run.

To run locally:

```bash
python -m pip install openpyxl==3.1.5
python scripts/refresh_tracker.py --date 2026-11-06 --online
python scripts/validate_tracker.py
```

Optional Gmail secrets: `GMAIL_CLIENT_ID`, `GMAIL_CLIENT_SECRET`, `GMAIL_REFRESH_TOKEN`, created for an OAuth client authorized with the `gmail.readonly` scope. Without those secrets, the workflow still monitors official sources and refreshes the tracker. Email intake stores **IDs, dates, subjects and review links only**, never message bodies. The initial five reviewed Gmail signals were imported manually.

## Integrity controls

- An email advertisement is **not** proof of an open, internationally funded vacancy.
- The site monitor records `anchor_present` or `review_source_changed`; it does **not** infer eligibility.
- Personal applicant actions and submission states are never changed without confirmation.
- The original [Google Sheet](https://docs.google.com/spreadsheets/d/1mbdVt1Acg_-a6wzQE4c9Vr1S2JAMzcD3zWnuaHpY5vk/edit) remains unchanged. GitHub contains the updated workbook snapshot.
- Application decisions require human review. AI-generated application materials must respect each university's policies.

## Product direction

**Temporal EvidenceGraph**: a verifiable network of deadlines, funding rules, eligibility constraints, supervisor research interests and application dependencies. The candidate's next action is optimized for evidence and deadline constraints—not merely keyword rank. This is a product hypothesis, not an unverified claim of global novelty or future valuation.

[Detailed design and comparable open-source research](docs/ARCHITECTURE.md).
