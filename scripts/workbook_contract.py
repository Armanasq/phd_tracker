from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook

ROOT = Path(__file__).resolve().parents[1]
BOOK = ROOT / "PhD_Action_List.xlsx"
BASELINE = ROOT / "artifacts" / "protected_workbook_state.json"
PROTECTED_COLUMNS = list(range(2, 4)) + list(range(5, 22))
TIMELINE_COLUMNS = (1, 3, 4, 5, 6, 7)


def stable(value):
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def keyed_rows(ws, start: int, id_col: int, selected: tuple[int, ...] | list[int]) -> dict[str, list]:
    result = {}
    for row in ws.iter_rows(min_row=start, max_col=max(id_col, *selected), values_only=True):
        identifier = row[id_col - 1]
        if not identifier:
            continue
        key = str(identifier)
        if key in result:
            raise ValueError(f"Duplicate source ID in {ws.title}: {key}")
        result[key] = [stable(row[i - 1]) for i in selected]
    return result


def snapshot(book: Path) -> dict:
    wb = load_workbook(book, read_only=True, data_only=False)
    required = ("Read me", "Action list", "Step timeline", "What I need to do", "Dropped", "Not added")
    missing = [name for name in required if name not in wb.sheetnames]
    if missing:
        raise ValueError("Missing original tracker sheets: " + ", ".join(missing))
    return {
        "schema_version": 1,
        "original_sheets": list(required),
        "action_columns": PROTECTED_COLUMNS,
        "action_records": keyed_rows(wb["Action list"], 4, 21, PROTECTED_COLUMNS),
        "timeline_columns": TIMELINE_COLUMNS,
        "timeline_records": keyed_rows(wb["Step timeline"], 4, 7, TIMELINE_COLUMNS),
    }


def verify(reference: dict, current: dict) -> dict:
    problems = []
    for tab, key in (("Action list", "action_records"), ("Step timeline", "timeline_records")):
        expected = reference[key]
        found = current[key]
        for sid in expected:
            if sid not in found:
                problems.append(f"Source ID removed from {tab}: {sid}")
            elif expected[sid] != found[sid]:
                idx = next((i for i, (a,b) in enumerate(zip(expected[sid],found[sid])) if a != b), None)
                col = reference["action_columns"][idx] if tab == "Action list" else reference["timeline_columns"][idx]
                problems.append(f"Protected cell changed in {tab}: {sid}, column {col}")
    if problems:
        raise ValueError("Workbook contract violation:\n" + "\n".join(problems[:20]))
    return {
        "status": "pass",
        "preserved_action_records": len(reference["action_records"]),
        "preserved_timeline_records": len(reference["timeline_records"]),
        "new_action_records": len(current["action_records"]) - len(reference["action_records"]),
        "new_timeline_records": len(current["timeline_records"]) - len(reference["timeline_records"]),
    }


def main():
    p=argparse.ArgumentParser()
    p.add_argument("operation",choices=("snapshot","verify"))
    p.add_argument("--workbook",default=str(BOOK))
    p.add_argument("--baseline",default=str(BASELINE))
    args=p.parse_args()
    book=Path(args.workbook)
    target=Path(args.baseline)
    if args.operation=="snapshot":
        result=snapshot(book)
        target.parent.mkdir(parents=True,exist_ok=True)
        target.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps({"status":"snapshot","action_records":len(result["action_records"]),"timeline_records":len(result["timeline_records"])}))
    else:
        reference=json.loads(target.read_text(encoding="utf-8"))
        print(json.dumps(verify(reference,snapshot(book)),sort_keys=True))


if __name__=="__main__":
    main()
