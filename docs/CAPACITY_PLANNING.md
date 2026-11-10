# Shared-capacity planning and scenario comparison

The private PhD Atlas runtime now schedules multiple applications under **one shared weekly time budget**. This replaces optimistic per-application feasibility claims with earliest-deadline-first capacity screening. It does not compute admission probabilities or execute submissions.

## Execution

Open the local private runtime (`python -m phd_agents serve --port 8765`), select **Operations → Capacity planning**, enter available hours per week, and evaluate. Application estimates are entered in each private application. Optional shared document hours are entered in the private applicant profile. All estimates remain in local SQLite; only an explicit user-initiated CSV export leaves the runtime.

The `POST /api/schedule` endpoint accepts `hours_per_week`, validates a finite value in (0,168], merges owner-entered application estimates with the current public evidence snapshot, and returns a bounded JSON scenario. It does not call an LLM, a provider, an admissions portal, or GitHub. The algorithm is in `phd_agents/capacity.py`, with the compatibility wrapper in `phd_agents/operations.py`.

## Two scenarios

- **Application-only baseline:** Sum of owner-entered remaining hours, allocated by earliest recorded closing date across one daily time budget.
- **Application + shared preparation:** Adds each recorded outstanding shared document type **once**, using its earliest dependent application deadline. The additional hours may overlap with per-application estimates, so the difference is a conservative sensitivity scenario rather than a verified requirement.

The budget assumes `weekly_hours / 7` available each calendar day, including the recorded closing date. It does not establish portal cutoff times or the user's actual working days. The 365-day planning horizon and 500-record limit bound computation. A maximum of 1,200 allocation blocks is exported; totals and shortage counts remain based on the full run when the display is truncated.

Unknown application estimates, deadlines, document inventories, and shared preparation hours remain **unresolved inputs**, not zero-hour tasks. Passed deadlines, submitted applications, owner-blocked routes, archived records, and research-only candidates are excluded from new submission preparation. The combined schedule identifies deadline bottlenecks and unallocated work without claiming the plan is optimal.

## Guarantees and limitations

1. One time budget is shared across all estimated applications; scheduling does not independently reuse the same hours.
2. Shared document work is counted once per document type in the additive scenario.
3. Every computed day respects the entered daily budget before rounding for display.
4. A passed deadline cannot be scheduled retroactively.
5. The calculation never infers admission probability, sponsor availability, eligibility, document reuse rights, actual final submission, or verified deadline cutoff instants.
6. CSV export is initiated by the user and sanitizes cells against spreadsheet-formula injection; it contains task IDs, dates and estimated hours but no personal notes, receipts or credentials.

The planner currently does not optimize holidays, weekends, external referee delivery, per-university document customization or job precedence. Explicitly estimated applicant work may already include shared document preparation; the baseline/additive comparison makes this potential double counting visible.

## Verification

```bash
python -m pytest tests/test_phd_joint_capacity.py tests/test_phd_operations.py -q
node --test tests/capacity_view.test.mjs
node --check site/modules/capacity-view.mjs
node --check site/modules/operations.mjs
```

These tests use synthetic estimates and do not invoke any external service.
