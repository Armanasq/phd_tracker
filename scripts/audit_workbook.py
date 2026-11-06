from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from datetime import date, datetime, timedelta
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.utils import get_column_letter

ROOT = Path(__file__).resolve().parents[1]
DATE = date.fromisoformat("2026-11-06")
HEADERS = {"Action list":3, "Step timeline":3}
YEAR = r"20\d\d"
DATE_RE = re.compile(r"\b(20\d\d)[-/.](\d{1,2})[-/.](\d{1,2})\b")
MONTH_NAMES = "January February March April May June July August September October November December".split()
MONTHS = {m.lower(): i + 1 for i, m in enumerate(MONTH_NAMES)}
MONTHS.update({m[:3].lower(): i + 1 for i, m in enumerate(MONTH_NAMES)})
MONTH_NAME_RE = re.compile(
    r"\b(?:(" + "|".join(MONTHS) + r")\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(20\d\d))?|(\d{1,2})(?:st|nd|rd|th)?\s+(" +
    "|".join(MONTHS) + r")\.?\s*(20\d\d)?)\b", re.I
)


def serialized(value):
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value).strip()[:300] if value is not None else ""


def identify_dates(value):
    if isinstance(value, datetime):
        return [value.date()]
    if isinstance(value, date):
        return [value]
    if not isinstance(value, str):
        return []
    found = []
    for m in DATE_RE.finditer(value):
        try:
            found.append(date(int(m.group(1)), int(m.group(2)), int(m.group(3))))
        except ValueError:
            pass
    for m in MONTH_NAME_RE.finditer(value):
        if m.group(1):
            month, day, yr = MONTHS[m.group(1).lower()[:3]], int(m.group(2)), m.group(3)
        else:
            month, day, yr = MONTHS[m.group(5).lower()[:3]], int(m.group(4)), m.group(6)
        try:
            if yr:
                found.append(date(int(yr), month, day))
        except ValueError:
            pass
    return sorted(set(found))


def row_data(ws, cells):
    return {
        "row": cells[0].row if cells else 0,
        "values": {
            get_column_letter(cell.column): serialized(cell.value)
            for cell in cells if cell.value is not None and str(cell.value).strip()
        },
    }


def summarize(wb, today):
    report = {"as_of":today.isoformat(), "sheets":{}, "today_all_sheets":[],
              "next_7_days_all_sheets":[], "source_id_gaps":{}, "dedup_warnings":[]}
    for ws in wb.worksheets:
        nonempty=0
        samples=[]
        today_rows=[]
        week_rows=[]
        dates=Counter()
        statuses=Counter()
        missing_ids=[]
        header_row=HEADERS.get(ws.title)
        for cells in ws.iter_rows():
            nonblank=[c for c in cells if c.value is not None and str(c.value).strip()]
            if not nonblank:
                continue
            nonempty+=1
            data=row_data(ws,cells)
            if len(samples)<14:
                samples.append(data)
            if ws.title=="Action list" and cells[0].row>=4 and cells[6].value:
                statuses[serialized(cells[4].value) or "[blank]"] += 1
                if not cells[20].value:
                    missing_ids.append(cells[0].row)
            selected=[]
            if ws.title=="Action list" and cells[0].row>=4:
                selected=identify_dates(cells[1].value)
            elif ws.title=="Step timeline" and cells[0].row>=4:
                selected=identify_dates(cells[0].value)
                selected += identify_dates(cells[5].value)
            else:
                for cell in nonblank[:max(2,len(nonblank))]:
                    selected.extend(identify_dates(cell.value))
            selected=sorted(set(selected))
            for d in selected:
                dates[d.isoformat()]+=1
            if today in selected:
                today_rows.append(data)
                report["today_all_sheets"].append({"sheet":ws.title,**data})
            elif any(today < d <= today + timedelta(days=7) for d in selected):
                week_rows.append(data)
                report["next_7_days_all_sheets"].append({"sheet":ws.title,**data})
        report["sheets"][ws.title]={
            "max_row":ws.max_row,"max_column":ws.max_column,
            "populated_rows":nonempty,"header_row":header_row,
            "sample_rows":samples,"today_count":len(today_rows),
            "today_rows":today_rows,"next_7_count":len(week_rows),
            "next_7_sample":week_rows[:30],
            "dates_within_14_days":{k:v for k,v in sorted(dates.items())
                                    if today.isoformat()<=k<=(today+timedelta(days=14)).isoformat()},
            "status_distribution":dict(statuses),
            "hidden_rows":sum(bool(d.hidden) for d in ws.row_dimensions.values()),
            "tables":list(ws.tables),
            "freeze_panes":str(ws.freeze_panes or ""),
            "merged_cells":[str(x) for x in list(ws.merged_cells.ranges)[:15]],
        }
        if missing_ids:
            report["source_id_gaps"][ws.title]={"count":len(missing_ids),"rows":missing_ids[:80]}
    report["total_today_rows"]=len(report["today_all_sheets"])
    report["total_next_7_rows"]=len(report["next_7_days_all_sheets"])
    return report


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--workbook",default=str(ROOT/"PhD_Action_List.xlsx"))
    p.add_argument("--output",default=str(ROOT/"data/workbook_audit.json"))
    p.add_argument("--as-of",default=DATE.isoformat())
    args=p.parse_args()
    wb=load_workbook(args.workbook,read_only=False,data_only=False)
    report=summarize(wb,date.fromisoformat(args.as_of))
    out=Path(args.output)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(json.dumps(report,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps({"as_of":report["as_of"],"today":report["total_today_rows"],
         "next_7":report["total_next_7_rows"],
         "sheets":{k:{"rows":v["populated_rows"],"today":v["today_count"],"week":v["next_7_count"]}
                   for k,v in report["sheets"].items()}},ensure_ascii=False))


if __name__=="__main__":
    main()
