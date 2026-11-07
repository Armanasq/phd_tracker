from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from scripts.scenario_lab import report, scenario


def view() -> dict:
    return {
        "as_of": "2026-11-07",
        "resources": [
            {"id": "academic_cv", "state": "unknown"},
            {"id": "transcripts", "state": "ready"},
        ],
        "applications": [
            {
                "id": "A", "name": "Robotics position", "deadline": "2026-11-08",
                "documents": ["academic_cv", "transcripts"],
                "proof_obligations": ["Verify funding"],
                "source": "https://example.edu/apply",
                "decision": "Go",
            },
            {
                "id": "B", "name": "Clinical AI position", "deadline": "2026-11-08",
                "documents": ["academic_cv"],
                "proof_obligations": [],
                "source": "https://example.edu/clinical",
                "decision": "Go",
            },
            {
                "id": "C", "name": "Future deadline", "deadline": "2026-12-20",
                "documents": [], "proof_obligations": [], "source": "", "decision": "Review",
            },
        ],
        "clocks": {
            "submission_deadlines": [{"due": "2026-11-07"}],
            "preparation_steps": [{"due": "2026-11-08"}],
            "shared_tasks": [{"due": "2026-11-09"}],
        },
        "insights": {
            "deadline_collisions": [
                {"date": "2026-11-08", "count": 2, "applications": [{"id": "A"}, {"id": "B"}]}
            ],
            "source_anomalies": [{"application_id": "A", "status": "contradiction_closed_portal"}],
        },
        "providers": [{"name": "inria", "health": "ok", "observed": 2, "new_unique": 1}],
        "research": [{"id": "arxiv:1"}],
    }


def test_scenario_tracks_calendar_and_source_findings() -> None:
    outcome = scenario(view(), 7, "verification", set())
    assert outcome["application_count"] == 2
    assert outcome["applications"][0]["source_anomalies"] == ["contradiction_closed_portal"]
    assert outcome["applications"][0]["unconfirmed_document_mentions"] == ["academic_cv"]
    assert outcome["deadline_collisions"][0]["count"] == 2
    assert outcome["clock_counts"]["preparation_steps"] == 1
    assert "Robotics position" in report(outcome)


def test_scenario_is_counterfactual_only() -> None:
    state = view()
    scenario_view = scenario(state, 14, "resources", {"academic_cv"})
    assert scenario_view["applications"][0]["scenario_all_mentioned_covered"]
    assert state["resources"][0]["state"] == "unknown"
    assert state["applications"][0]["documents"] == ["academic_cv", "transcripts"]


def test_rejects_unrecognized_settings() -> None:
    for horizon, lens, ready in [
        (5, "deadlines", set()),
        (7, "unrecognized", set()),
        (7, "resources", {"not_a_document"}),
    ]:
        with pytest.raises(ValueError):
            scenario(view(), horizon, lens, ready)


def test_rendered_report_is_deterministic_and_explicit() -> None:
    s = scenario(view(), 30, "research", {"academic_cv"})
    assert "Research and source coverage" in report(s)
    assert "not a live institutional portal check" in report(s)
    assert "2026-11-07" in report(s)
    assert json.dumps(s, sort_keys=True) == json.dumps(scenario(view(), 30, "research", {"academic_cv"}), sort_keys=True)
