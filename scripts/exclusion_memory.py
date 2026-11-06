from __future__ import annotations

import argparse
import json
import re
import unicodedata
from datetime import datetime, date
from pathlib import Path

from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

ROOT=Path(__file__).resolve().parents[1]
STOP={
    "phd","doctoral","doctorate","position","positions","candidate","studentship",
    "fully","funded","scholarship","research","fellow","fellowship",
    "university","institute","school","college","centre","center","of",
    "in","on","at","and","for","with","the","to","a","an",
    "united","states","uk","eu","project","lab","group","2026","2027",
}


def tokens(value: str):
    value=unicodedata.normalize("NFKD",str(value or "")).casefold()
    words=re.findall(r"[a-z0-9]{3,}",value)
    return set(words)-STOP


def similarity(left: str,right: str):
    a,b=tokens(left),tokens(right)
    if not a or not b:
        return 0.0,0
    intersection=len(a & b)
    score=intersection/len(a | b)
    return round(score,4),intersection


def history(wb):
    out=[]
    for row in wb["Dropped"].iter_rows(min_row=2,max_col=4,values_only=True):
        if not row[0]:
            continue
        out.append({"type":"Dropped","route":str(row[0]),"status":str(row[1] or ""),
                    "reason":str(row[2] or ""),"source_id":str(row[3] or "")})
    for row in wb["Not added"].iter_rows(min_row=2,max_col=2,values_only=True):
        if not row[0]:
            continue
        out.append({"type":"Not added","route":str(row[0]),"status":"Research exclusion / historical",
                    "reason":str(row[1] or ""),"source_id":""})
    return out


def evaluate(wb, candidate_records):
    entries=history(wb)
    exclusions={e["source_id"]:e for e in entries if e["source_id"]}
    matches=[]
    for hit in candidate_records:
        sid=hit.get("id","")
        title=hit.get("title","")
        exact=exclusions.get(sid)
        if exact:
            matches.append({"candidate_id":sid,"candidate":title,"source_url":hit.get("url",""),
                "matched_original":exact["route"],"reason":exact["reason"],
                "match_type":"source_id_exact","score":1.0,
                "decision":"review_current_call; do_not_block_automatically"})
            continue
        candidates=[]
        for entry in entries:
            score,overlap=similarity(title,entry["route"])
            if overlap>=4 and score>=0.7:
                candidates.append((score,entry))
        for score,entry in sorted(candidates,key=lambda p:-p[0])[:3]:
            matches.append({"candidate_id":sid,"candidate":title,"source_url":hit.get("url",""),
                "matched_original":entry["route"],"reason":entry["reason"],
                "match_type":"title_similarity_warning_only","score":score,
                "decision":"review_current_call; do_not_block_automatically"})
    return {"schema_version":1,"original_records":len(entries),
            "drop_count":sum(e["type"]=="Dropped" for e in entries),
            "unadded_count":sum(e["type"]=="Not added" for e in entries),
            "entries":entries,"potential_reappearances":matches,
            "policy":"Historical reasons must be reviewed for the NEW call; never reuse expired eligibility conclusions automatically."}


def add_sheet(wb,report):
    ws=wb["Exclusion memory"] if "Exclusion memory" in wb else wb.create_sheet("Exclusion memory")
    if ws.max_row:
        ws.delete_rows(1,ws.max_row)
    columns=["History category","Original opportunity","Historical status",
             "Historical exclusion / uncertainty reason","Source ID","Match warning"]
    ws.append(columns)
    warnings={m["matched_original"] for m in report["potential_reappearances"]}
    for e in report["entries"]:
        has_warning=e["route"] in warnings
        ws.append([e["type"],e["route"],e["status"],e["reason"],
                   e["source_id"],"Possible new match, manual review" if has_warning else ""])
        row=ws.max_row
        for j in range(1,7):
            c=ws.cell(row,j)
            c.alignment=Alignment(wrap_text=True,vertical="top")
            c.font=Font(name="Aptos",size=10,color="A65311" if has_warning else "304157")
        if has_warning:
            ws.cell(row,6).fill=PatternFill("solid",fgColor="FFF1DA")
        ws.row_dimensions[row].height=41
    for j,x in enumerate(columns,1):
        cell=ws.cell(1,j)
        cell.fill=PatternFill("solid",fgColor="152A45")
        cell.font=Font(name="Aptos",bold=True,color="FFFFFF")
    for j,width in enumerate([22,68,32,95,24,42],1):
        ws.column_dimensions[get_column_letter(j)].width=width
    ws.freeze_panes="B2"
    ws.auto_filter.ref=f"A1:F{ws.max_row}"
    ws.sheet_view.showGridLines=False


def run(book=ROOT/"PhD_Action_List.xlsx",source=ROOT/"data/discovered_candidates.json",
        target=ROOT/"data/exclusion_memory.json"):
    wb=load_workbook(book)
    if not {"Dropped","Not added"}<=set(wb.sheetnames):
        raise ValueError("Missing original exclusion evidence worksheets")
    candidates=json.loads(source.read_text(encoding="utf-8")).get("records",[]) if source.exists() else []
    report=evaluate(wb,candidates)
    add_sheet(wb,report)
    wb.save(book)
    target.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",encoding="utf-8")
    return {"historical_records":report["original_records"],
            "potential_reappearances":len(report["potential_reappearances"])}


if __name__=="__main__":
    print(json.dumps(run()))
