from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Alignment, Font, PatternFill

ROOT = Path(__file__).resolve().parents[1]


def write_radar(workbook: Path, papers_file: Path) -> dict:
    data = json.loads(papers_file.read_text(encoding="utf-8"))
    papers = data.get("papers", [])
    wb = load_workbook(workbook)
    ws = wb["Research radar"] if "Research radar" in wb else wb.create_sheet("Research radar")
    ws.delete_rows(1, ws.max_row)
    headers = ["Published", "Paper", "Research theme", "Authors", "Relevance", "Paper URL", "Classification", "Use"]
    ws.append(headers)
    for p in sorted(papers, key=lambda x: (x.get("published", ""), x.get("relevance_score", 0)), reverse=True)[:200]:
        when = datetime.fromisoformat(p["published"]) if p.get("published") else None
        ws.append([when, p.get("title", "")[:300], p.get("topic", ""),
                   ", ".join(p.get("authors", [])[:8]), p.get("relevance_score"),
                   p.get("paper_url", ""), "Research publication — NOT a job opening",
                   "Research context and possible SOP reading, not evidence that a lab recruits"])
    ws.freeze_panes = "C2"
    ws.sheet_view.showGridLines = False
    ws.auto_filter.ref = f"A1:H{ws.max_row}"
    widths = [17, 82, 22, 54, 13, 48, 39, 64]
    for j, width in enumerate(widths, 1):
        ws.column_dimensions[ws.cell(1, j).column_letter].width = width
        head = ws.cell(1, j)
        head.fill = PatternFill("solid", fgColor="172B45")
        head.font = Font(name="Aptos", bold=True, color="FFFFFF")
    for i in range(2, ws.max_row + 1):
        ws.row_dimensions[i].height = 50
        ws.cell(i, 1).number_format = "yyyy-mm-dd"
        for j in range(1, 9):
            ws.cell(i, j).alignment = Alignment(vertical="top", wrap_text=True)
    wb.save(workbook)
    return {"rows": len(papers), "workbook_rows": ws.max_row - 1, "sheet": ws.title}


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--workbook", default=str(ROOT / "PhD_Action_List.xlsx"))
    p.add_argument("--source", default=str(ROOT / "data/research_radar.json"))
    args = p.parse_args()
    print(json.dumps(write_radar(Path(args.workbook), Path(args.source))))
