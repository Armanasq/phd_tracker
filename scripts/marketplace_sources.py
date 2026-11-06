from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.parse import urljoin
from bs4 import BeautifulSoup

URLS = {
    "academictransfer": "https://www.academictransfer.com/en/jobs/",
    "academicpositions": "https://academicpositions.com/find-jobs/phd-jobs-in-all-countries-in-all-fields",
}
HOSTS = {
    "academictransfer": {"www.academictransfer.com", "academictransfer.com"},
    "academicpositions": {"academicpositions.com", "www.academicpositions.com"},
}
DATE_PATTERN = re.compile(r"\b(20\d{2}-\d{2}-\d{2})\b")
DOCTORAL = re.compile(r"\b(phd|doctoral|doctorant|doctoral researcher|doctoral candidate|ph\.d)\b", re.I)
EXCLUDE = re.compile(r"\b(postdoc|post-doctoral|professor|assistant professor|lecturer|tenure track|internship)\b", re.I)


def jsonld_job(value, accumulator):
    if isinstance(value, list):
        for row in value:
            jsonld_job(row, accumulator)
    elif isinstance(value, dict):
        kind = value.get("@type")
        if (kind == "JobPosting" or isinstance(kind, list) and "JobPosting" in kind):
            accumulator.append(value)
        if "@graph" in value:
            jsonld_job(value["@graph"], accumulator)


def parse_job_postings(body: bytes, provider: str, observed: str, canonical, score_fn, id_fn):
    soup = BeautifulSoup(body, "html.parser")
    records = []
    seen = set()
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            payload = json.loads(script.string or script.get_text())
        except (TypeError, ValueError):
            continue
        jobs = []
        jsonld_job(payload, jobs)
        for job in jobs:
            title = re.sub(r"\s+", " ", str(job.get("title") or "")).strip()
            if not DOCTORAL.search(title) or EXCLUDE.search(title):
                continue
            source_url = canonical(urljoin(URLS[provider], str(job.get("url") or "")))
            if not source_url or source_url in seen:
                continue
            seen.add(source_url)
            desc = BeautifulSoup(str(job.get("description") or ""), "html.parser").get_text(" ", strip=True)
            score, hits = score_fn(title + " " + desc[:2000])
            if score < 3:
                continue
            deadline = str(job.get("validThrough") or "")[:10]
            deadline = deadline if DATE_PATTERN.fullmatch(deadline) else None
            records.append({
                "id": id_fn(provider, source_url), "provider": provider, "lane": "third_party_index",
                "title": title[:240], "url": source_url, "deadline": deadline,
                "deadline_provenance": "Third-party JobPosting metadata; requires primary-source confirmation" if deadline else "Unknown",
                "evidence_status": "third_party_listing_unverified",
                "funding_status": "not_independently_verified",
                "score": score, "matched_topics": hits,
                "snippet": desc[:350], "observed_at": observed,
            })
    return records


def parse_anchor_leads(body: bytes, provider: str, observed: str, canonical, score_fn, id_fn):
    soup = BeautifulSoup(body, "html.parser")
    candidates = {}
    for link in soup.select("a[href]"):
        href = str(link.get("href") or "")
        if not href or href.startswith(("#", "mailto:", "javascript:")):
            continue
        title = re.sub(r"\s+", " ", link.get_text(" ", strip=True)).strip()
        if not (14 <= len(title) <= 240) or not DOCTORAL.search(title) or EXCLUDE.search(title):
            continue
        if provider == "academictransfer" and "/jobs/" not in href:
            continue
        if provider == "academicpositions" and not any(x in href for x in ("/ad/", "/jobs/", "/job/")):
            continue
        source_url = canonical(urljoin(URLS[provider], href))
        if not source_url:
            continue
        score, hits = score_fn(title)
        if score < 3:
            continue
        block = link.find_parent(["article", "li"]) or link.parent
        context = re.sub(r"\s+", " ", block.get_text(" ", strip=True))[:500]
        candidates[source_url] = {
            "id": id_fn(provider, source_url), "provider": provider, "lane": "third_party_index",
            "title": title, "url": source_url, "deadline": None,
            "deadline_provenance": "Not extracted from verified primary source",
            "evidence_status": "third_party_listing_unverified",
            "funding_status": "not_independently_verified",
            "score": score, "matched_topics": hits, "snippet": context,
            "observed_at": observed,
        }
    for heading in soup.select("h2,h3,h4"):
        title = re.sub(r"\s+", " ", heading.get_text(" ", strip=True)).strip()
        if not (14 <= len(title) <= 240) or not DOCTORAL.search(title) or EXCLUDE.search(title):
            continue
        score, hits = score_fn(title)
        if score < 3:
            continue
        parent = heading
        links = []
        for depth in range(4):
            parent = parent.parent
            if parent is None:
                break
            links = [a for a in parent.select("a[href]") if a.get("href")]
            if links:
                break
        if not links:
            continue
        candidates_link = [
            a for a in links
            if provider == "academictransfer" and "/jobs/" in str(a.get("href", ""))
            or provider == "academicpositions" and any(x in str(a.get("href", "")) for x in ("/ad/", "/jobs/", "/job/"))
        ]
        if not candidates_link:
            continue
        href = str(candidates_link[0].get("href"))
        source_url = canonical(urljoin(URLS[provider], href))
        if not source_url or source_url in candidates:
            continue
        context = re.sub(r"\s+", " ", parent.get_text(" ", strip=True))[:550]
        candidates[source_url] = {
            "id": id_fn(provider, source_url), "provider": provider, "lane": "third_party_index",
            "title": title, "url": source_url, "deadline": None,
            "deadline_provenance": "Not verified; extract on primary vacancy page",
            "evidence_status": "third_party_listing_unverified",
            "funding_status": "not_independently_verified",
            "score": score, "matched_topics": hits, "snippet": context,
            "observed_at": observed,
        }
    return list(candidates.values())


def collect_board(provider: str, observed: str, fetch_fn, canonical, score_fn, id_fn):
    if provider not in URLS:
        raise ValueError("Unknown academic board")
    data, redirect = fetch_fn(URLS[provider])
    if redirect.split("/")[2].lower() not in HOSTS[provider]:
        raise ValueError("Unexpected board redirect")
    rich = parse_job_postings(data, provider, observed, canonical, score_fn, id_fn)
    links = parse_anchor_leads(data, provider, observed, canonical, score_fn, id_fn)
    by_url = {r["url"]: r for r in links}
    by_url.update({r["url"]: r for r in rich})
    return sorted(by_url.values(), key=lambda x: (-x["score"], x["id"]))[:100]
