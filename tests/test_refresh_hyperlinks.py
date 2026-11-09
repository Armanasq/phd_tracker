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

def test_primary_official_research_promotion_preserves_review_gate(tmp_path, monkeypatch):
    wb = Workbook()
    ws = wb.active
    ws.title = "Action list"
    for _ in range(2):
        ws.append([None] * 21)
    for col, heading in enumerate(refresh.HEADERS, 1):
        ws.cell(3, col).value = heading
    ws["B1"] = datetime(2026, 11, 9)
    timeline = wb.create_sheet("Step timeline")
    for _ in range(3):
        timeline.append([None] * 7)
    approved = {
        "id": "VERIFIED", "name": "Official PhD", "deadline": "2026-11-20",
        "deadline_kind": "final", "source_url": "https://example.edu/verified",
        "evidence": "University advert", "fit": "robotics", "funding": "salaried",
        "eligibility": "Masters", "apply": "https://example.edu/apply",
        "contact": "PI", "next_step": "Submit verified application",
        "documents": "CV", "blockers": "Check eligibility",
        "confidence": "official_institution", "decision": "Go",
        "source_date": "2026-11-09", "source_email": "",
    }
    risk = {**approved, "id": "RISK", "decision": "Go with risk"}
    review = {**approved, "id": "REVIEW", "decision": "Check first"}
    unverified = {**approved, "id": "LEAD", "confidence": "search_lead_unverified"}
    monkeypatch.setattr(
        refresh,
        "read_records",
        lambda path, key: [approved, risk, review, unverified] if key == "records" else [],
    )
    monkeypatch.setattr(refresh, "ROOT", tmp_path)
    first = refresh.refresh(wb, date(2026, 11, 9), False)
    second = refresh.refresh(wb, date(2026, 11, 9), False)
    ids = {wb["Action list"].cell(i, 21).value for i in range(4, wb["Action list"].max_row + 1)}
    queue_ids = {wb["Research queue"].cell(i, 1).value for i in range(2, wb["Research queue"].max_row + 1)}
    assert ids == {"VERIFIED", "RISK"}
    assert {"REVIEW", "LEAD"}.issubset(queue_ids)
    assert first["main_count"] == second["main_count"] == 2
    assert sum(wb["Step timeline"].cell(i, 7).value == "VERIFIED" for i in range(4, wb["Step timeline"].max_row + 1)) == 1

def test_main_list_promotion_policy_shared_with_validator():
    from scripts.validate_tracker import should_promote as validator_policy

    assert validator_policy is refresh.should_promote
    base = {"deadline": "2026-11-29", "decision": "Go"}
    assert refresh.should_promote({**base, "confidence": "official_plus_email"})
    assert refresh.should_promote({**base, "confidence": "official_institution"})
    assert refresh.should_promote({**base, "confidence": "official_institution", "decision": "Go with risk"})
    assert not refresh.should_promote({**base, "confidence": "official_institution", "decision": "Check first"})
    assert not refresh.should_promote({**base, "confidence": "search_lead_unverified"})
    assert not refresh.should_promote({**base, "confidence": "email_only"})
    assert not refresh.should_promote({**base, "confidence": "official_institution", "deadline": None})

def test_source_watch_deadline_mismatch_is_distinct_from_portal_closure(monkeypatch):
    class Response:
        def __init__(self, content):
            self.content = content
        def __enter__(self):
            return self
        def __exit__(self, *args):
            return False
        def geturl(self):
            return "https://www.mos.ed.tum.de/en/avs/career/our-jobs/ki-motorsport-1/"
        def read(self, _):
            return self.content.encode("utf8")

    watch = {
        "id": "N263-07-LIVE",
        "url": "https://www.mos.ed.tum.de/en/avs/career/our-jobs/ki-motorsport-1/",
        "anchor": "15th of November 2026",
        "negative_anchor": "July 17, 2026",
        "negative_state": "contradiction_deadline_mismatch",
    }
    monkeypatch.setattr(refresh, "urlopen", lambda *args, **kwargs: Response("Application Deadline: Friday, July 17, 2026"))
    assert refresh.monitor_one(watch)[1] == "contradiction_deadline_mismatch"
    monkeypatch.setattr(refresh, "urlopen", lambda *args, **kwargs: Response("Application Deadline: 15th of November 2026"))
    assert refresh.monitor_one(watch)[1] == "anchor_present"
