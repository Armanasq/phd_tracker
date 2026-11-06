from __future__ import annotations

import json
from pathlib import Path

import pytest
from openpyxl import Workbook, load_workbook

import scripts.reconcile_uploaded_source as source


def fixture(tmp_path, monkeypatch):
    wb = Workbook()
    ws = wb.active
    ws.title = "Action list"
    for _ in range(3):
        ws.append([None] * 21)
    ws["U3"] = "Source id"
    ws["E4"] = "Go"
    ws["G4"] = "Imaging doctorate"
    ws["U4"] = "ORIGINAL"
    ws["E5"] = "Go"
    ws["G5"] = "New institutional research opportunity"
    ws["U5"] = "REPO-ONLY"
    raw = [ws.cell(4, i).value for i in source.COLUMNS]
    digest = source.fingerprint(raw)
    expected_mask = sum(1 << (i - 1) for i in source.COLUMNS if ws.cell(4, i).value is None)
    path = tmp_path / "test.xlsx"
    ws["J4"] = "contact@wrong.institution"
    ws["T4"] = "https://unrelated.example.org"
    wb.save(path)
    monkeypatch.setattr(source, "source_manifest", lambda _: {"ORIGINAL": (expected_mask, digest)})
    return path


def test_import_restores_upload_blanks_and_keeps_new_repository_records(tmp_path, monkeypatch):
    path = fixture(tmp_path, monkeypatch)
    report = tmp_path / "reconcile.json"
    result = source.reconcile(path, tmp_path / "source.txt", report, apply=True)
    assert result["status"] == "verified"
    assert result["blank_cells_corrected"] == 2
    assert result["additional_repository_applications_retained"] == ["REPO-ONLY"]
    output = load_workbook(path)
    assert output["Action list"]["J4"].value is None
    assert output["Action list"]["T4"].value is None
    assert output["Action list"]["G5"].value == "New institutional research opportunity"
    assert json.loads(report.read_text())["status"] == "verified"


def test_changed_nonblank_values_fail_closed(tmp_path, monkeypatch):
    path = fixture(tmp_path, monkeypatch)
    wb = load_workbook(path)
    wb["Action list"]["G4"] = "Different position"
    wb.save(path)
    with pytest.raises(ValueError, match="nonblank rows"):
        source.reconcile(path, tmp_path / "unused.txt", tmp_path / "report.json", apply=True)
    assert load_workbook(path)["Action list"]["J4"].value == "contact@wrong.institution"
    assert json.loads((tmp_path / "report.json").read_text())["status"] == "mismatch"


def test_manifest_rejects_wrong_row_count(tmp_path):
    path = tmp_path / "manifest.txt"
    path.write_text("ORIGINAL 0 " + "0" * 20 + "\n")
    with pytest.raises(ValueError, match="180"):
        source.source_manifest(path)
