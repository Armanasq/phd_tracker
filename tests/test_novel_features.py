from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from scripts.issue_controls import MARKER, parse, apply
from scripts.notification_engine import apply_policy, outstanding
from scripts.research_radar import merge, parse_atom


def issue(body="/snooze inria:2026-10570 3d", actor="Armanasq", number=121):
    return {
        "action": "created",
        "issue": {"number": 1, "body": MARKER, "title": "PhD Intelligence — Action Center"},
        "comment": {"id": number, "body": body, "user": {"login": actor}},
    }


def preferences():
    return {"schema_version": 1, "muted": [], "priority": [],
            "snoozed_until": {}, "processed_comment_ids": []}


def test_snooze_is_authorized_and_idempotent():
    today = date(2026, 11, 6)
    original = preferences()
    updated, result = parse(issue(), "Armanasq", {"inria:2026-10570"}, today, original)
    assert result["accepted"]
    assert updated["snoozed_until"]["inria:2026-10570"] == "2026-11-09"
    assert not original["snoozed_until"]
    repeated, status = parse(issue(), "Armanasq", {"inria:2026-10570"}, today, updated)
    assert not status["accepted"] and status["reason"] == "duplicate"
    assert repeated == updated


def test_malicious_command_and_unknown_author_are_ignored():
    for event in [issue(actor="unknown"), issue(body="/snooze inria:2026-10570 40d"),
                  issue(body="/snooze inria:2026-10570 3d; cat /etc/passwd"),
                  issue(body="/priority unknown-repository")]:
        modified, outcome = parse(event, "Armanasq", {"inria:2026-10570"}, date(2026,11,6), preferences())
        assert not outcome["accepted"]
        assert modified == preferences()


def test_priority_and_unmute_restore_options():
    known = {"inria:2026-10570"}
    state, ok = parse(issue("/priority inria:2026-10570", number=41), "Armanasq", known, date(2026,11,6), preferences())
    assert ok["accepted"] and state["priority"] == ["inria:2026-10570"]
    state, ok = parse(issue("/unpriority inria:2026-10570", number=42), "Armanasq", known, date(2026,11,6), state)
    assert ok["accepted"] and state["priority"] == []


def test_critical_deadline_bypasses_snooze_and_mute():
    inputs = [
        {"id": "a", "source_id": "N263-09", "kind": "deadline", "days": 1},
        {"id": "b", "source_id": "N263-09", "kind": "deadline", "days": 7},
        {"id": "c", "source_id": "inria:abc", "kind": "new_lead"},
    ]
    settings = {"muted": ["N263-09", "inria:abc"],
                "snoozed_until": {"N263-09": "2026-11-12"},
                "priority": ["N263-09"]}
    got = apply_policy(inputs, settings, date(2026, 11, 6))
    assert [x["id"] for x in got] == ["a"]
    assert len(outstanding(got, {"github": []}, "github")) == 1


def test_radar_parser_never_labels_papers_as_open_positions():
    xml = """<?xml version="1.0"?>
    <feed xmlns="http://www.w3.org/2005/Atom">
      <entry>
        <id>http://arxiv.org/abs/2611.01234v2</id>
        <title>Visual Inertial SLAM for Robot Navigation</title>
        <summary>Learning a world model for robotic localization.</summary>
        <published>2026-11-04T00:00:00Z</published>
        <author><name>A Researcher</name></author>
      </entry>
      <entry>
        <id>http://arxiv.org/abs/2611.05678</id>
        <title>Unrelated astrophysics</title>
        <summary>Spectra of quasars.</summary>
        <published>2026-11-04T00:00:00Z</published>
      </entry>
    </feed>"""
    records = parse_atom(xml.encode(), "slam", "2026-11-06T10:00:00Z")
    assert len(records) == 1
    assert records[0]["id"] == "arxiv:2611.01234"
    assert records[0]["hiring_status"] == "unknown_not_inferred"
    assert records[0]["source_type"] == "research_publication_not_a_job"


def test_radar_merge_deduplicates_and_preserves_first_seen(tmp_path):
    raw = tmp_path / "raw.json"
    target = tmp_path / "data.json"
    report = tmp_path / "report.json"
    paper = {"id": "arxiv:2611.01234", "title": "Robot SLAM", "published": "2026-11-04",
             "relevance_score": 15, "paper_url": "https://arxiv.org/abs/2611.01234"}
    raw.write_text(json.dumps({"observed_at":"2026-11-06T10:00:00Z",
                               "papers":[paper],"errors":[]}))
    first = merge(raw,target,report)
    second = merge(raw,target,report)
    assert first["new_count"] == 1
    assert second["new_count"] == 0
    assert json.loads(target.read_text())["papers"][0]["first_seen"] == "2026-11-06T10:00:00Z"


def test_explicit_owner_asset_ready_command_updates_only_asset_state(tmp_path):
    data=tmp_path / "data"
    data.mkdir()
    prefs=data / "notification_preferences.json"
    prefs.write_text(json.dumps(preferences()))
    assets=data / "application_assets.json"
    assets.write_text(json.dumps({
        "valid_statuses":["unknown","ready","in_progress","not_started","not_applicable"],
        "resources":{"academic_cv":{"label":"CV","status":"unknown"}}
    }))
    event=tmp_path / "comment.json"
    event.write_text(json.dumps(issue("/asset academic_cv ready",actor="Armanasq",number=441)))
    output=data / "result.json"
    result=apply(event,prefs,output,"Armanasq",date(2026,11,6))
    assert result["accepted"] and result["operation"]=="asset"
    assert json.loads(assets.read_text())["resources"]["academic_cv"]["status"]=="ready"
    assert json.loads(prefs.read_text())["processed_comment_ids"]==["441"]
    assert json.loads(output.read_text())["new_status"]=="ready"


def test_asset_change_is_ignored_from_non_owner(tmp_path):
    data=tmp_path / "data"
    data.mkdir()
    prefs=data / "notification_preferences.json"
    prefs.write_text(json.dumps(preferences()))
    assets=data / "application_assets.json"
    original={"valid_statuses":["unknown","ready"],"resources":{"academic_cv":{"status":"unknown"}}}
    assets.write_text(json.dumps(original))
    event=tmp_path / "comment.json"
    event.write_text(json.dumps(issue("/asset academic_cv ready",actor="attacker",number=442)))
    result=apply(event,prefs,data/"result.json","Armanasq",date(2026,11,6))
    assert not result["accepted"]
    assert json.loads(assets.read_text())==original
