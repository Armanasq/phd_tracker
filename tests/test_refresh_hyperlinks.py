from __future__ import annotations

from datetime import date, datetime
from openpyxl import Workbook, load_workbook
import scripts.refresh_tracker as refresh


def test_sorted_workbook_does_not_inherit_wrong_hyperlinks(tmp_path, monkeypatch):
    wb = Workbook()
    ws = wb.active
    ws.title = "Action list"
    for _ in range(2):
        ws.append([None] * 21)
    for col, label in enumerate(refresh.HEADERS, 1):
        ws.cell(3, col).value = label
    ws["B1"] = datetime(2026, 11, 6)
    later = [None] * 21
    later[1] = datetime(2026, 11, 15)
    later[4] = "Go"
    later[6] = "Later opportunity"
    later[8] = "https://example.edu/later"
    later[19] = "https://example.edu/later"
    later[20] = "LATER"
    ws.append(later)
    for column in ("I4", "T4"):
        ws[column].hyperlink = "https://example.edu/later"
    earlier = [None] * 21
    earlier[1] = datetime(2026, 11, 6)
    earlier[4] = "Check first"
    earlier[6] = "Earlier opportunity without application URL"
    earlier[20] = "EARLIER"
    ws.append(earlier)
    timeline = wb.create_sheet("Step timeline")
    for _ in range(3):
        timeline.append([None] * 7)
    monkeypatch.setattr(refresh, "read_records", lambda *args: [])
    monkeypatch.setattr(refresh, "ROOT", tmp_path)
    refresh.refresh(wb, date(2026, 11, 6), False)
    file = tmp_path / "tracker.xlsx"
    wb.save(file)
    result = load_workbook(file)["Action list"]
    assert result["U4"].value == "EARLIER"
    assert result["I4"].value is None
    assert result["I4"].hyperlink is None
    assert result["T4"].value is None
    assert result["T4"].hyperlink is None
    assert result["U5"].value == "LATER"
    assert result["I5"].value == "https://example.edu/later"
    assert result["I5"].hyperlink.target == "https://example.edu/later"
    assert result["T5"].hyperlink.target == "https://example.edu/later"
