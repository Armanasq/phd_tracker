from __future__ import annotations

from datetime import date

from scripts.export_calendar import export,folded,make_event


def task(kind="timeline_step",due="2026-11-06",done=False):
    return {
        "task_id":"tsk-1234567890abcdef", "type":kind, "due":due,
        "name":"Vision & World Models doctoral programme",
        "action":"Submit a research statement and CV",
        "source_id":"A1", "source":"https://university.edu/doctoral",
        "sheet":"Step timeline","row":12,
        "state":"confirmed_done" if done else "completion_unconfirmed",
        "blocked":done,"final_deadline":"2026-11-15"
    }


def test_calendar_does_not_generate_false_closing_time(tmp_path):
    output=tmp_path/"calendar.ics"
    report=export({"as_of":"2026-11-06","all_tasks":[task()]},output)
    content=output.read_text()
    assert report["events"]==1
    assert "DTSTART;VALUE=DATE:20261106" in content
    assert "DTEND;VALUE=DATE:20261107" in content
    assert "STATUS:TENTATIVE" in content
    assert "END:VCALENDAR" in content
    assert "23:59" not in content


def test_excluded_completed_and_past_events_not_exported(tmp_path):
    output=tmp_path/"calendar.ics"
    rows=[
        task(done=True),
        {**task(),"task_id":"tsk-aaaaaaaaaaaaaaaa","due":"2026-11-05"},
        {**task(),"task_id":"tsk-bbbbbbbbbbbbbbbb","due":"2027-05-01"},
    ]
    result=export({"as_of":"2026-11-06","all_tasks":rows},output)
    assert result["events"]==0
    assert "BEGIN:VEVENT" not in output.read_text()


def test_reminders_and_escaped_unsafe_text():
    row=task(kind="application_deadline")
    row["action"]="Apply, submit; deadline\nconfirm"
    event=make_event(row,date(2026,11,6))
    assert event.count("BEGIN:VALARM")==2
    assert any("Apply\\, submit\\; deadline\\nconfirm" in line for line in event)
    assert all("DTSTART;TZID" not in line for line in event)


def test_utf8_line_wrapping_is_bounded_by_octets():
    result=folded("SUMMARY:"+("Université" * 45))
    assert all(len(segment.encode("utf-8"))<=73 for segment in result.split("\r\n"))

def test_calendar_priority_and_unverified_date_are_not_final_deadlines():
    for kind, expected in (
        ("application_priority", "PRIORITY REVIEW DATE (NOT FINAL)"),
        ("application_unverified", "UNVERIFIED APPLICATION DATE"),
    ):
        entry = {**task(kind=kind), "final_deadline": None}
        event = make_event(entry, date(2026, 11, 6))
        assert any(line.startswith("SUMMARY:" + expected) for line in event)
        assert "Final programme deadline: unconfirmed / not applicable" in "\n".join(event)
