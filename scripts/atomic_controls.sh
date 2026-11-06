#!/usr/bin/env bash
set -euo pipefail

git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"

for attempt in 1 2 3; do
  git fetch --quiet origin main
  git reset --hard --quiet origin/main
  python scripts/issue_controls.py \
    --event "$GITHUB_EVENT_PATH" \
    --owner "$GITHUB_REPOSITORY_OWNER" \
    --output data/last_control_result.json
  if ! python -c 'import json; assert json.load(open("data/last_control_result.json"))["accepted"]' >/dev/null 2>&1; then
    echo "No valid owner action in this comment"
    exit 0
  fi
  git add data/notification_preferences.json data/last_control_result.json
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
