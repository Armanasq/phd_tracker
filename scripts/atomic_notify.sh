#!/usr/bin/env bash
set -euo pipefail

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

for attempt in 1 2 3; do
  git fetch --quiet origin main
  git reset --hard --quiet origin/main
  python scripts/notification_engine.py --send
  git add data/notification_state.json data/notification_report.json
  if git diff --cached --quiet; then
    echo "Notification digest is unchanged"
    exit 0
  fi
  git commit -m "Record delivered deadline milestones and research notifications"
  if git push origin HEAD:main; then
    echo "Notification ledger published from latest main"
    exit 0
  fi
  echo "Concurrent commit detected; recomputing notification digest"
done

echo "Failed to persist notification ledger" >&2
exit 1
