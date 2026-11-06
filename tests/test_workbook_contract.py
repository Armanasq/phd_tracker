from __future__ import annotations

import pytest
from openpyxl import Workbook

from scripts.workbook_contract import snapshot, verify


def create_file(tmp_path):
    wb=Workbook()
    a=wb.active
    a.title="Action list"
    for _ in range(3):
        a.append([None]*21)
    row=[None]*21
    row[1]="2026-11-22"
    row[4]="Go"
    row[6]="Inria robotics"
    row[10]="Apply before the deadline"
    row[19]="https://jobs.inria.fr/public/classic/en/offres/2026-10570"
    row[20]="inria:2026-10570"
    a.append(row)
    t=wb.create_sheet("Step timeline")
    for _ in range(3):
        t.append([None]*7)
    t.append(["2026-11-22",None,"Inria robotics","Go","Apply","2026-11-22","inria:2026-10570"])
    for name in ("Read me", "What I need to do", "Dropped", "Not added"):
        wb.create_sheet(name)
    file=tmp_path/"tracker.xlsx"
    wb.save(file)
    return wb,file


def test_user_changes_cannot_be_silently_overwritten(tmp_path):
    wb,file=create_file(tmp_path)
    before=snapshot(file)
    wb["Action list"]["E4"]="Submitted"
    wb.save(file)
    with pytest.raises(ValueError,match="Protected cell changed"):
        verify(before,snapshot(file))


def test_derived_cells_and_new_candidates_are_allowed(tmp_path):
    wb,file=create_file(tmp_path)
    before=snapshot(file)
    wb["Action list"]["A4"]=1
    wb["Action list"]["D4"]='=B4-$B$1'
    row=[None]*21
    row[4]="Check first"
    row[6]="New verified lead"
    row[20]="new-id"
    wb["Action list"].append(row)
    wb.save(file)
    result=verify(before,snapshot(file))
    assert result["status"]=="pass"
    assert result["new_action_records"]==1


def test_deleted_source_id_is_blocked(tmp_path):
    wb,file=create_file(tmp_path)
    before=snapshot(file)
    wb["Action list"]["U4"]=None
    wb.save(file)
    with pytest.raises(ValueError,match="Source ID removed"):
        verify(before,snapshot(file))


def test_repeated_source_steps_are_valid_and_protected(tmp_path):
    wb, file = create_file(tmp_path)
    wb["Step timeline"].append([
        "2026-11-21", None, "Inria robotics", "Go",
        "Ask supervisor for funding", "2026-11-21", "inria:2026-10570",
    ])
    wb.save(file)
    baseline = snapshot(file)
    assert len(baseline["timeline_records"]) == 2
    assert verify(baseline, snapshot(file))["preserved_timeline_records"] == 2
    wb["Step timeline"]["E5"] = "Silently changed"
    wb.save(file)
    with pytest.raises(ValueError, match="Timeline step removed or modified"):
        verify(baseline, snapshot(file))
