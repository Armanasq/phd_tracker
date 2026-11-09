#!/usr/bin/env bash
set -euo pipefail
git config user.name "github-actions[bot]"
git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
for attempt in 1 2 3; do
  git fetch --quiet origin main
  git reset --hard --quiet origin/main
  python scripts/workspace_controls.py --event "$GITHUB_EVENT_PATH" --owner "$OWNER_LOGIN"
  if ! python -c 'import json; assert json.load(open("data/workspace_control_result.json"))["accepted"]' >/dev/null 2>&1; then
    cat data/workspace_control_result.json
    exit 0
  fi
  python scripts/build_workspace.py --out site/data/workspace.json
  git add data/workspace_overrides.json site/data/workspace.json
  git commit -m "Confirm owner PhD application workspace update"
  if git push origin HEAD:main; then exit 0; fi
  echo "Concurrent change; reapplying verified owner command" >&2
done
exit 1
