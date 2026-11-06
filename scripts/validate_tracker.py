from __future__ import annotations

import json
import sys
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "PhD_Action_List.xlsx"


def main():
    wb = load_workbook(path, read_only=True, data_only=False)
    required = {
        "Read me", "Action list", "Step timeline", "What I need to do",
        "Dropped", "Not added", "Research queue", "Mail signals",
        "Evidence ledger", "Source watch",
    }
    missing = required - set(wb.sheetnames)
    assert not missing, f"Missing sheets: {sorted(missing)}"
    ws = wb["Action list"]
    assert ws["G3"].value == "Route" and ws["U3"].value == "Source id"
    ids = set()
    last = None
    records = 0
    for row in ws.iter_rows(min_row=4, max_col=21, values_only=True):
        if not row[6]:
            continue
        assert row[20], f"Missing source ID at position {records+1}"
        assert row[20] not in ids, f"Duplicate source id {row[20]}"
        ids.add(row[20])
        if isinstance(row[1], (date, datetime)):
            if last:
                assert row[1] >= last, "Action list not sorted by deadline"
            last = row[1]
        records += 1
    assert records >= 180, f"Unexpectedly low record count {records}"
    sources = json.loads((ROOT / "data" / "opportunities.json").read_text())["records"]
    for item in sources:
        if item["confidence"] == "official_plus_email":
            assert item["id"] in ids, f"Verified opportunity absent: {item['id']}"
    queue_ids = {x[0] for x in wb["Research queue"].iter_rows(min_row=2, values_only=True) if x[0]}
    for item in sources:
        if item["confidence"] != "official_plus_email":
            assert item["id"] in queue_ids, f"Unverified opportunity missing from queue: {item['id']}"
            assert item["id"] not in ids, "Unverified opportunity promoted without review"
    watches = [v[0] for v in wb["Source watch"].iter_rows(min_row=2, values_only=True) if v[0]]
    assert len(watches) >= 5 and len(watches) == len(set(watches))
    assert wb["Action list"]["B1"].value is not None
    print(json.dumps({"status":"pass","action_list_entries":records,"queued_opportunities":len(queue_ids),
                      "source_watches":len(watches),"sheets":wb.sheetnames},sort_keys=True))


if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        print(f"TRACKER_VALIDATION_FAILED: {e}", file=sys.stderr)
        raise
