from __future__ import annotations
from scripts.discovery_engine import safe_url, relevant_score, evidence_id
from scripts.marketplace_sources import parse_anchor_leads, parse_job_postings


def test_heading_fallback_for_academictransfer():
    html = b"""
    <main><article>
    <a href="/en/jobs/98765/phd-position-in-robot-navigation/">View vacancy</a>
    <h3>PhD Position in Robot Navigation and SLAM</h3>
    <div>Deadline 12 Nov '26 - Delft University</div>
    </article><article>
    <a href="/en/jobs/22222/assistant-professor/">Link</a>
    <h3>Assistant Professor in Robotics</h3></article></main>
    """
    found = parse_anchor_leads(html, "academictransfer", "2026-11-06T07:00:00Z",
                              safe_url, relevant_score, evidence_id)
    assert len(found) == 1
    assert "robot-navigation" in found[0]["url"]
    assert found[0]["deadline"] is None
    assert found[0]["evidence_status"] == "third_party_listing_unverified"


def test_jobposting_metadata_preserves_unverified_deadline():
    html = b"""
    <script type="application/ld+json">
    {"@type": "JobPosting", "title": "PhD Position Computer Vision and Machine Learning",
     "url": "https://academicpositions.com/ad/test-university/12345",
     "validThrough": "2026-12-15T23:59:00+01:00",
     "description": "Robotics perception and 3D mapping"}
    </script>
    """
    found = parse_job_postings(html,"academicpositions","2026-11-06T07:00:00Z",
                               safe_url,relevant_score,evidence_id)
    assert len(found) == 1
    assert found[0]["deadline"] == "2026-12-15"
    assert found[0]["evidence_status"] == "third_party_listing_unverified"
