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
  python scripts/build_workspace.py --out /tmp/phd-owner-workspace-validated.json
  if [[ "${GITHUB_REPOSITORY,,}" == "armanasq/phd_tracker" ]]; then
    git add data/workspace_overrides.json
  else
    git add data/user_workspace_overrides.json
  fi
  git commit -m "Confirm owner PhD application workspace update"
  if git push origin HEAD:main; then
    gh workflow run publish-cockpit.yml --ref main || echo 'Publication dispatch unavailable; committed owner state is preserved'
    exit 0
  fi
  echo "Concurrent change; reapplying verified owner command" >&2
done
exit 1
