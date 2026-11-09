from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path

from openpyxl import Workbook, load_workbook

from scripts.discovery_engine import aggregate, inria_cards, relevant_score, safe_url
from scripts.ingest_discovery import ingest
from scripts.notification_engine import evaluate, milestone_for, outstanding


def workbook(root: Path) -> Path:
    wb = Workbook()
    ws = wb.active
    ws.title = "Action list"
    for _ in range(3):
        ws.append([None] * 21)
    row = [None] * 21
    row[1] = datetime(2026, 11, 13)
    row[4] = "Go"
    row[6] = "Research lab — autonomous mapping"
    row[10] = "Prepare CV, statement of purpose, transcripts and recommendation letters"
    row[19] = "https://example.edu/phd"
    row[20] = "known-lab"
    ws.append(row)
    ws.append([None, datetime(2026, 11, 15), None, None, "Submitted", None,
               "Already submitted", None, None, None, None, None, None, None, None,
               None, None, None, None, "https://example.edu/old", "submitted"])
    queue = wb.create_sheet("Research queue")
    queue.append(["Source ID", "Deadline", "Route", "Fit", "Status", "Finding", "Application link",
                  "Official URL", "Email URL", "Next step", "Blockers"])
    path = root / "PhD_Action_List.xlsx"
    wb.save(path)
    return path


def test_inria_parser_realistic_listing():
    sample = """
    <ul><li><h2><a href="/public/classic/en/offres/2026-10570">
    PhD Position F/M Enforcing Persistence in Generative World Models for Robotics
    </a></h2><div>Job reference: 2026-10570</div>
    <div>Town/city: Paris</div><div>Inria Team: ASTRA</div>
    <div>Deadline to apply: 2026-11-20</div></li>
    <li><h2>Post-Doctoral Research Visit F/M AI</h2>
    <div>Job reference: 2026-10010</div><div>Deadline to apply: 2026-12-15</div></li></ul>
    """
    found = inria_cards(sample.encode(), "2026-11-06T10:00:00+00:00")
    assert len(found) == 1, found
    assert found[0]["id"] == "inria:2026-10570"
    assert found[0]["deadline"] == "2026-11-20"
    assert found[0]["score"] >= 4
    assert found[0]["url"].endswith("2026-10570")


def test_source_url_normalization_and_relevance():
    assert safe_url("https://example.org/jobs/abc?utm_source=mail&ref=robot") == "https://example.org/jobs/abc"
    assert safe_url("http://example.org/phd") is None
    assert safe_url("https://localhost/private") is None
    assert safe_url("https://admin:pw@example.org/private") is None
    assert relevant_score("SLAM and visual-inertial state estimation") [0] >= 10


def test_discovery_aggregation_keeps_provenance_and_deduplicates(tmp_path):
    first = {
        "schema_version": 1, "provider": "inria", "errors": [], "observed_at": "2026-11-06T10:00:00Z",
        "records": [{
            "id": "inria:2026-10570", "title": "Robotics world model PhD",
            "url": "https://jobs.inria.fr/public/classic/en/offres/2026-10570",
            "provider": "inria", "lane": "official_institution",
            "deadline": "2026-11-20", "deadline_provenance": "Inria",
            "evidence_status": "official_index", "score": 7,
            "snippet": "world model robotics", "observed_at": "2026-11-06T10:00:00Z"
        }]
    }
    directory = tmp_path / "artifacts"
    directory.mkdir()
    (directory / "inria.json").write_text(json.dumps(first))
    output = tmp_path / "discovered.json"
    report = tmp_path / "report.json"
    a = aggregate(directory, output, report)
    b = aggregate(directory, output, report)
    assert a["new_count"] == 1
    assert b["new_count"] == 0
    assert len(json.loads(output.read_text())["records"]) == 1
    assert json.loads(output.read_text())["records"][0]["first_seen"] == first["records"][0]["observed_at"]


def test_research_inbox_does_not_mutate_main_actions(tmp_path):
    path = workbook(tmp_path)
    source = tmp_path / "found.json"
    record = {
        "schema_version": 1, "records": [{
            "id": "inria:2026-10570",
            "title": "AI and robotics world model doctoral position",
            "url": "https://jobs.inria.fr/public/classic/en/offres/2026-10570",
            "deadline": "2026-11-20", "deadline_provenance": "Official Inria index",
            "evidence_status": "official_index", "score": 11, "snippet": "Robotics",
        }]
    }
    source.write_text(json.dumps(record))
    report = tmp_path / "report.json"
    a = ingest(path, source, report)
    b = ingest(path, source, report)
    assert a["new_research_queue_rows"] == 1
    assert b["new_research_queue_rows"] == 0
    wb = load_workbook(path, read_only=True)
    assert wb["Research queue"].max_row == 2
    assert wb["Action list"].cell(4, 21).value == "known-lab"
    assert wb["Action list"].cell(5, 21).value == "submitted"


def test_notification_milestones_and_submitted_filter(tmp_path):
    path = workbook(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    result = evaluate(date(2026, 11, 6), path, data)
    assert len(result["upcoming"]) == 1
    assert result["events"][0]["milestone"] == 7
    assert result["events"][0]["kind"] == "deadline"
    assert result["assets"][0]["potential_applications"] == 1
    assert milestone_for(29) == 30
    assert milestone_for(13) == 14
    assert milestone_for(3) == 3
    assert milestone_for(0) == 0
    assert milestone_for(-1) is None
    events = result["events"]
    assert len(outstanding(events, {"github": []}, "github")) == 1
    assert not outstanding(events, {"github": [events[0]["id"]]}, "github")


def test_notification_detects_contradictions(tmp_path):
    path = workbook(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    (data / "latest_run.json").write_text(json.dumps({
        "source_statuses": [{
            "id": "portal-closed", "source_url": "https://example.edu/closed",
            "status": "contradiction_closed_portal"
        }]
    }))
    result = evaluate(date(2026, 11, 6), path, data)
    assert any(event["kind"] == "conflict" for event in result["events"])


def test_conflicting_deadline_is_not_silently_overwritten(tmp_path):
    directory = tmp_path / "artifacts"
    directory.mkdir()
    record = {
        "id": "inria:2026-10570", "title": "Robotics PhD",
        "url": "https://jobs.inria.fr/public/classic/en/offres/2026-10570",
        "provider": "inria", "lane": "official_institution",
        "deadline": "2026-11-20", "deadline_provenance": "Institution",
        "evidence_status": "official_index", "score": 7,
        "observed_at": "2026-11-06T10:00:00Z",
    }
    input_path = directory / "inria.json"
    input_path.write_text(json.dumps({"provider": "inria", "records": [record], "errors": []}))
    out = tmp_path / "state.json"
    report = tmp_path / "report.json"
    aggregate(directory, out, report)
    input_path.write_text(json.dumps({"provider": "inria", "records": [
        {**record, "deadline": "2026-11-22", "observed_at": "2026-11-08T10:00:00Z"}
    ], "errors": []}))
    result = aggregate(directory, out, report)
    found = json.loads(out.read_text())["records"][0]
    assert found["deadline"] == "2026-11-20"
    assert found["proposed_deadline"] == "2026-11-22"
    assert found["deadline_change_needs_review"] is True
    assert "inria:2026-10570" in result["deadline_conflicts"]


def test_equivalent_urls_are_aliased_not_duplicated(tmp_path):
    directory = tmp_path / "artifacts"
    directory.mkdir()
    record = {
        "id": "inria:2026-10570", "title": "Robotics PhD",
        "url": "https://jobs.inria.fr/public/classic/en/offres/2026-10570",
        "provider": "inria", "lane": "official_institution",
        "deadline": "2026-11-20", "deadline_provenance": "Institution",
        "evidence_status": "official_index", "score": 7,
        "observed_at": "2026-11-06T10:00:00Z",
    }
    (directory / "a.json").write_text(json.dumps({"provider": "inria", "records": [record], "errors": []}))
    (directory / "b.json").write_text(json.dumps({"provider": "brave", "records": [{
        **record, "id": "web:duplicate", "provider": "brave",
        "url": record["url"] + "?utm_source=search", "evidence_status": "search_lead_unverified"
    }], "errors": []}))
    out = tmp_path / "state.json"
    report = tmp_path / "report.json"
    result = aggregate(directory, out, report)
    found = json.loads(out.read_text())["records"]
    assert len(found) == 1
    assert found[0]["evidence_status"] == "official_index"
    assert "web:duplicate" in found[0]["aliases"]
    assert len(result["url_aliases"]) == 1


def test_private_network_hosts_are_rejected():
    assert safe_url("https://127.0.0.1/admin") is None
    assert safe_url("https://192.168.1.10/admin") is None
    assert safe_url("https://10.0.0.7/api") is None

def test_notification_detects_deadline_mismatch(tmp_path):
    path = workbook(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    (data / "latest_run.json").write_text(json.dumps({
        "source_statuses": [{
            "id": "N263-07-LIVE",
            "application_id": "N263-07",
            "source_url": "https://example.edu/doctoral",
            "status": "contradiction_deadline_mismatch",
            "expected_deadline": "2026-11-15",
        }]
    }))
    result = evaluate(date(2026, 11, 9), path, data)
    assert any(event["kind"] == "conflict" for event in result["events"])

def test_priority_date_notification_is_not_a_final_deadline(tmp_path):
    file = workbook(tmp_path)
    wb = load_workbook(file)
    wb["Action list"]["C4"] = "Priority review; actual final deadline is 2027-01-15."
    wb.save(file)
    result = evaluate(date(2026, 11, 6), file, tmp_path / "data")
    target = next(e for e in result["events"] if e["source_id"] == "known-lab")
    assert target["kind"] == "priority"
    assert target["date_type"] == "priority"
    assert not any(e["kind"] == "deadline" and e["source_id"] == "known-lab"
                   for e in result["events"])

def test_monitor_outage_not_reported_as_application_conflict(tmp_path):
    path = workbook(tmp_path)
    data = tmp_path / "data"
    data.mkdir()
    (data / "latest_run.json").write_text(json.dumps({
        "source_statuses": [
            {"id": "monitor-unavailable", "application_id": "known-lab",
             "status": "unavailable", "source_url": "https://example.edu/phd"},
            {"id": "monitor-unsafe", "application_id": "other",
             "status": "unsafe_redirect", "source_url": "https://example.edu/other"},
        ]
    }))
    result = evaluate(date(2026, 11, 6), path, data)
    alerts = [e for e in result["events"] if e["kind"] == "source_health"]
    assert {e["source_id"] for e in alerts} == {"known-lab", "other"}
    assert not any(e["kind"] == "conflict" for e in result["events"])
