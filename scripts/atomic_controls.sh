#!/usr/bin/env bash
set -euo pipefail

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

for attempt in 1 2 3; do
  git fetch --quiet origin main
  git reset --hard --quiet origin/main
  python scripts/workbook_contract.py snapshot
  python scripts/issue_controls.py \
    --event "$GITHUB_EVENT_PATH" \
    --owner "$GITHUB_REPOSITORY_OWNER" \
    --output data/last_control_result.json
  if ! python -c 'import json; assert json.load(open("data/last_control_result.json"))["accepted"]' >/dev/null 2>&1; then
    echo "No valid owner action in this comment"
    exit 0
  fi
  if python -c 'import json; r=json.load(open("data/last_control_result.json")); assert r["operation"] == "asset"' >/dev/null 2>&1; then
    python scripts/portfolio_frontier.py
    python scripts/workbook_contract.py verify
    python scripts/validate_tracker.py
  fi
  if python -c 'import json; r=json.load(open("data/last_control_result.json")); assert r["operation"] in ("task_done","task_reopen")' >/dev/null 2>&1; then
    python scripts/full_workbook_planner.py
    python scripts/export_calendar.py
    python scripts/workbook_contract.py verify
    python scripts/validate_tracker.py
    python scripts/render_readme.py
    python scripts/render_command_center.py
  fi
  git add data/notification_preferences.json data/last_control_result.json data/application_assets.json
  if [ -f data/task_completion.json ]; then git add data/task_completion.json; fi
  if [ -f data/execution_plan.json ]; then git add data/execution_plan.json; fi
  if [ -f data/portfolio_frontier.json ]; then git add data/portfolio_frontier.json; fi
  if [ -d assets/readme ]; then git add assets/readme README.md; fi
  if [ -f docs/TODAY.md ]; then git add docs/TODAY.md; fi
  if [ -f calendar/phd_deadlines.ics ]; then git add calendar/phd_deadlines.ics; fi
  git add PhD_Action_List.xlsx
  git commit -m "Apply verified owner notification preference"
  if git push origin HEAD:main; then
    python scripts/issue_ack.py \
      --result data/last_control_result.json \
      --issue "$ISSUE_NUMBER"
    exit 0
  fi
  echo "Concurrent update; retrying verified control from latest state"
done
echo "Notification control could not be committed without conflict" >&2
exit 1
