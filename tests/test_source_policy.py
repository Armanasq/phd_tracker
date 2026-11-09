from scripts.source_policy import classify_deadline_note, primary_source_verified


def test_deadline_kind_distinguishes_priority_from_final():
    assert classify_deadline_note("priority; final 2027-01-15") == "priority"
    assert classify_deadline_note("best-consideration Jan 15, 2027, not final") == "priority"
    assert classify_deadline_note("EURAXESS index only; not independently confirmed") == "unverified"
    assert classify_deadline_note("Final application deadline: 2026-11-14") == "final"


def test_authoritative_sources_are_not_misclassified():
    assert primary_source_verified("official_institution")
    assert primary_source_verified("official_plus_email")
    assert not primary_source_verified("third_party_listing_unverified")
    assert not primary_source_verified(None)

def test_multiple_source_watch_states_prioritize_conflicts_over_late_success():
    from scripts.source_policy import summarize_watch_statuses

    observations = [
        {"id": "portal", "application_id": "A", "status": "contradiction_closed_portal"},
        {"id": "info", "application_id": "A", "status": "anchor_present"},
        {"id": "other", "application_id": "B", "status": "unavailable"},
        {"id": "other-ok", "application_id": "B", "status": "anchor_present"},
    ]
    assert summarize_watch_statuses(observations) == {
        "A": "contradiction_closed_portal", "B": "unavailable",
    }
