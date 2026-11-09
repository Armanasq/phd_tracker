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
