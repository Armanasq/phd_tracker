#!/usr/bin/env bash
set -euo pipefail

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

for attempt in 1 2 3; do
  git fetch --quiet origin main
  git reset --hard --quiet origin/main
  python scripts/gmail_intake.py
  python scripts/refresh_tracker.py --online
  python scripts/validate_tracker.py
  python scripts/review_engine.py
  git add PhD_Action_List.xlsx data/latest_run.json data/decision_queue.json
  if [ -f data/mail_inbox.json ]; then git add data/mail_inbox.json; fi
  if [ -f data/evidence_events.jsonl ]; then git add data/evidence_events.jsonl; fi

  if git diff --cached --quiet; then
    echo "No tracker changes required."
    exit 0
  fi

  git commit -m "Refresh PhD tracker from current evidence snapshot"
  if git push origin HEAD:main; then
    echo "Atomic refresh succeeded on attempt $attempt."
    exit 0
  fi
  echo "A concurrent commit changed main; fetching current workbook and retrying ($attempt/3)."
done

echo "Could not commit without overwriting concurrent changes." >&2
exit 1
