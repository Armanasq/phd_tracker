from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--result", default=str(ROOT / "data" / "last_control_result.json"))
    parser.add_argument("--issue", required=True, type=int)
    args = parser.parse_args()
    result = json.loads(Path(args.result).read_text(encoding="utf-8"))
    if not result.get("accepted"):
        return
    token = os.environ.get("GITHUB_TOKEN")
    repo = os.environ.get("GITHUB_REPOSITORY", "")
    if not token or not re.fullmatch(r"[a-zA-Z0-9_.-]+/[a-zA-Z0-9_.-]+", repo):
        raise RuntimeError("Repository and GitHub token required")
    op = result["operation"]
    sid = result.get("source_id") or result.get("task_id")
    until = result.get("until")
    summary = f"Recorded /{op} for {sid}."
    if op in ("task_done","task_reopen"):
        label = "completed" if op == "task_done" else "reopened"
        summary = f"Task {sid} marked {label} explicitly by the owner. The full-workbook Execution board and README have been regenerated; no original source or application submission status changed."
    elif op == "asset":
        summary = f"Recorded your explicit readiness update: {sid} = {result['new_status']}. The decision frontier was recalculated without changing application submission states."
    elif op == "snooze":
        summary += f" Noncritical reminders are suppressed through {until}; deadlines within 1 day still notify."
    elif op == "mute":
        summary += " Research leads and noncritical reminders are muted; day-of and day-before alerts are never muted."
    elif op == "priority":
        summary += " Future relevant alerts are prioritized."
    summary += "\n\nChange applied to data/notification_preferences.json."
    url = f"https://api.github.com/repos/{repo}/issues/{args.issue}/comments"
    body = json.dumps({"body": summary}).encode("utf-8")
    req = Request(url, method="POST", data=body, headers={
        "Authorization": "Bearer " + token,
        "Accept": "application/vnd.github+json",
        "Content-Type": "application/json",
        "X-GitHub-Api-Version": "2022-11-28",
    })
    with urlopen(req, timeout=20) as response:
        if response.status != 201:
            raise RuntimeError("Could not acknowledge notification control")


if __name__ == "__main__":
    main()
