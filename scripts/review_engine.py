from __future__ import annotations

import json
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load(path, key):
    p = ROOT / path
    return json.loads(p.read_text(encoding="utf-8")).get(key, []) if p.exists() else []


def plan(today: date):
    items = load("data/opportunities.json", "records")
    monitor = load("data/latest_run.json", "source_statuses")
    observations = {x["id"]: x["status"] for x in monitor}
    due = []
    for item in items:
        obligations = []
        confidence = item["confidence"]
        primary = confidence == "official_plus_email"
        if not primary:
            obligations.append("Verify live institutional announcement and application route")
        if item["deadline"] is None:
            obligations.append("Obtain an explicit official deadline and timezone")
        if item["funding"] and ("confirm" in item["funding"].casefold() or "verify" in item["funding"].casefold()):
            obligations.append("Confirm funded stipend and international tuition eligibility")
        if "German" in item["eligibility"] and "German" in item["blockers"]:
            obligations.append("Confirm German-language requirement")
        if confidence == "contradictory":
            obligations.append("Resolve conflict between recruiter email and lab website")
        if observations.get(item["id"]) in ("review_source_changed","contradiction_closed_portal","contradiction_deadline_mismatch"):
            obligations.append("Recheck official page: observed source contradicts expected evidence")
        day_count = (date.fromisoformat(item["deadline"]) - today).days if item["deadline"] else None
        if day_count is not None and day_count < 0:
            tier = "expired"
        elif day_count is not None and day_count <= 7:
            tier = "urgent"
        elif day_count is not None and day_count <= 30:
            tier = "near-term"
        elif day_count is not None:
            tier = "upcoming"
        else:
            tier = "unposted"
        due.append({
            "id": item["id"],
            "programme": item["name"],
            "deadline": item["deadline"],
            "days_to_deadline": day_count,
            "deadline_kind": item["deadline_kind"],
            "tier": tier,
            "research_status": "source_verified" if primary else "human_review_required",
            "obligations": sorted(set(obligations)),
            "official_source": item["source_url"],
            "original_email": item["source_email"],
            "next_step": item["next_step"],
        })
    order = {"urgent":0,"near-term":1,"unposted":2,"upcoming":3,"expired":4}
    due.sort(key=lambda r:(order[r["tier"]],r["days_to_deadline"] if r["days_to_deadline"] is not None else 9999,r["id"]))
    return {"as_of":today.isoformat(),"decision_policy":"Evidence obligations, not model confidence probabilities",
            "items":due,"source_conflicts":[m for m in monitor if m["status"] in ("review_source_changed","contradiction_closed_portal","contradiction_deadline_mismatch")]}


def main():
    today = date.fromisoformat(json.loads((ROOT / "data/latest_run.json").read_text(encoding="utf-8"))["date"])
    result = plan(today)
    target = ROOT / "data" / "decision_queue.json"
    target.write_text(json.dumps(result,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    print(json.dumps({"items":len(result["items"]),"with_obligations":sum(bool(x["obligations"]) for x in result["items"]),
                      "source_conflicts":len(result["source_conflicts"])},sort_keys=True))


if __name__=="__main__":
    main()
