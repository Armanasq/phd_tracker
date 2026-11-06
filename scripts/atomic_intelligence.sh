#!/usr/bin/env bash
set -euo pipefail

python -m pytest -q tests

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

for attempt in 1 2 3; do
  git fetch --quiet origin main
  git reset --hard --quiet origin/main
  python scripts/workbook_contract.py snapshot
  python scripts/discovery_engine.py aggregate \
    --input artifacts/discovery \
    --output data/discovered_candidates.json \
    --report data/discovery_report.json
  python scripts/research_radar.py merge --input artifacts/research_radar.json
  python scripts/gmail_intake.py
  python scripts/refresh_tracker.py --online
  python scripts/ingest_discovery.py
  python scripts/exclusion_memory.py
  python scripts/review_engine.py
  python scripts/portfolio_frontier.py
  python scripts/radar_workbook.py
  python scripts/full_workbook_planner.py
  python scripts/workbook_contract.py verify
  python scripts/validate_tracker.py
  python scripts/notification_engine.py
  python scripts/render_readme.py
  python scripts/render_command_center.py

  git add README.md docs/TODAY.md assets/readme/ PhD_Action_List.xlsx \
    data/discovered_candidates.json \
    data/discovery_report.json \
    data/ingestion_report.json \
    data/latest_run.json \
    data/decision_queue.json \
    data/portfolio_frontier.json \
    data/execution_plan.json \
    data/exclusion_memory.json \
    data/research_radar.json \
    data/research_radar_report.json \
    data/notification_report.json
  if [ -f data/mail_inbox.json ]; then git add data/mail_inbox.json; fi
  if [ -f data/evidence_events.jsonl ]; then git add data/evidence_events.jsonl; fi

  if git diff --cached --quiet; then
    echo "No material changes"
    exit 0
  fi
  git commit -m "Reconcile funded PhD research from independent verified sources"
  if git push origin HEAD:main; then
    echo "Committed research and workbook from current main at attempt $attempt"
    exit 0
  fi
  echo "Concurrent writer; recomputing from updated main ($attempt/3)"
done
echo "Failed to publish research without conflict after three attempts" >&2
exit 1
