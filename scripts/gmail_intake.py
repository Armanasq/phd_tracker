from __future__ import annotations

import base64
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / "data" / "mail_inbox.json"
REQUIRED = ("GMAIL_CLIENT_ID", "GMAIL_CLIENT_SECRET", "GMAIL_REFRESH_TOKEN")


def request_json(url, token=None, form=None):
    data = urlencode(form).encode() if form else None
    req = Request(url, data=data)
    req.add_header("Accept", "application/json")
    if form:
        req.add_header("Content-Type", "application/x-www-form-urlencoded")
    if token:
        req.add_header("Authorization", "Bearer " + token)
    with urlopen(req, timeout=20) as response:
        return json.loads(response.read(500000).decode("utf-8"))


def safe_text(value, limit=190):
    v = re.sub(r"[\x00-\x1f]+", " ", str(value or "")).strip()[:limit]
    return "'" + v if v.startswith(("=", "+", "-", "@")) else v


def main():
    if not all(os.getenv(k) for k in REQUIRED):
        print("Gmail intake disabled; configure read-only OAuth secrets to activate.")
        return
    token = request_json(
        "https://oauth2.googleapis.com/token",
        form={"client_id":os.environ["GMAIL_CLIENT_ID"],
              "client_secret":os.environ["GMAIL_CLIENT_SECRET"],
              "refresh_token":os.environ["GMAIL_REFRESH_TOKEN"],
              "grant_type":"refresh_token"},
    )["access_token"]
    since = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y/%m/%d")
    search = '(subject:PhD OR subject:doctoral OR subject:studentship OR subject:application) after:' + since + ' -category:promotions -in:spam -in:trash'
    base = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
    ids = request_json(base + "?" + urlencode({"q":search,"maxResults":50}),token).get("messages",[])
    old = json.loads(TARGET.read_text(encoding="utf-8")) if TARGET.exists() else {"schema_version":1,"messages":[]}
    known = {m["id"] for m in old["messages"]}
    for m in ids:
        if m["id"] in known:
            continue
        detail = request_json(base + "/" + m["id"] + "?format=metadata&metadataHeaders=Subject&metadataHeaders=Date",token)
        headers = {h["name"].lower():h["value"] for h in detail.get("payload",{}).get("headers",[])}
        old["messages"].append({
            "id":m["id"],
            "date":datetime.fromtimestamp(int(detail["internalDate"])/1000,timezone.utc).strftime("%Y-%m-%d"),
            "subject":safe_text(headers.get("subject")),
            "gmail_url":"https://mail.google.com/mail/u/0/#all/"+m["id"],
            "review_status":"unclassified_inbox_signal",
        })
    old["messages"] = sorted(old["messages"],key=lambda m:(m["date"],m["id"]),reverse=True)[:1000]
    TARGET.parent.mkdir(parents=True,exist_ok=True)
    TARGET.write_text(json.dumps(old,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"mail_signal_count":len(old["messages"]),"fetched_message_ids":len(ids)}))


if __name__=="__main__":
    main()
