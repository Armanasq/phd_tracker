from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
URL = "https://export.arxiv.org/api/query"
ATOM = "{http://www.w3.org/2005/Atom}"
QUERIES = {
    "slam": "cat:cs.RO AND all:SLAM",
    "robot_learning": "cat:cs.RO AND all:robot learning",
    "medical_ai": "cat:cs.CV AND all:medical imaging",
}
TERMS = {
    "SLAM": 8,
    "visual inertial": 7,
    "localization": 5,
    "navigation": 4,
    "robotic": 3,
    "robot": 3,
    "world model": 6,
    "embodied": 4,
    "reinforcement learning": 2,
    "medical imaging": 4,
    "multimodal": 3,
    "segmentation": 2,
}


def parse_atom(payload: bytes, topic: str, observed: str, min_score: int = 4) -> list[dict]:
    root = ET.fromstring(payload)
    collected = []
    for entry in root.findall(f"{ATOM}entry"):
        link = (entry.findtext(f"{ATOM}id") or "").strip()
        title = " ".join((entry.findtext(f"{ATOM}title") or "").split())
        abstract = " ".join((entry.findtext(f"{ATOM}summary") or "").split())
        published = (entry.findtext(f"{ATOM}published") or "")[:10]
        authors = [x.findtext(f"{ATOM}name", default="") for x in entry.findall(f"{ATOM}author")]
        identifier = re.search(r"arxiv\.org/abs/(\d{4}\.\d{4,5})(?:v\d+)?", link)
        if not identifier or not title:
            continue
        score = sum(weight for phrase, weight in TERMS.items() if phrase.casefold() in (title + " " + abstract).casefold())
        if score < min_score:
            continue
        paper_id = identifier.group(1)
        collected.append({
            "id": "arxiv:" + paper_id,
            "title": title[:350],
            "authors": authors[:14],
            "abstract_excerpt": abstract[:580],
            "paper_url": "https://arxiv.org/abs/" + paper_id,
            "published": published,
            "topic": topic,
            "relevance_score": score,
            "source_type": "research_publication_not_a_job",
            "hiring_status": "unknown_not_inferred",
            "observed_at": observed,
        })
    return collected


def fetch(topic: str, query: str, observed: str) -> list[dict]:
    params = urlencode({"search_query": query, "max_results": 18,
                        "sortBy": "submittedDate", "sortOrder": "descending"})
    request = Request(URL + "?" + params, headers={
        "User-Agent": "PhDResearchRadar/1.0 (noncommercial academic research)",
        "Accept": "application/atom+xml",
    })
    with urlopen(request, timeout=25) as response:
        if response.geturl().split("?")[0] != URL:
            raise ValueError("Unexpected API redirect")
        raw = response.read(600001)
    if len(raw) > 600000:
        raise ValueError("arXiv feed response exceeded size limit")
    return parse_atom(raw, topic, observed)


def crawl(output: Path) -> dict:
    observed = datetime.now(timezone.utc).isoformat(timespec="seconds")
    matches: dict[str, dict] = {}
    errors = []
    for idx, (topic, query) in enumerate(QUERIES.items()):
        if idx:
            time.sleep(3.1)
        try:
            for paper in fetch(topic, query, observed):
                if paper["id"] not in matches or paper["relevance_score"] > matches[paper["id"]]["relevance_score"]:
                    matches[paper["id"]] = paper
        except (HTTPError, URLError, TimeoutError, ValueError, OSError, ET.ParseError) as e:
            errors.append(f"{topic}: {type(e).__name__}: {str(e)[:110]}")
    result = {"schema_version": 1, "observed_at": observed,
              "papers": list(matches.values()), "errors": errors,
              "disclaimer": "Publications are research signals, not PhD vacancy announcements"}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"papers": len(matches), "errors": errors}


def merge(source: Path, target: Path, report_path: Path, since_days: int = 35) -> dict:
    incoming = json.loads(source.read_text(encoding="utf-8"))
    previous = json.loads(target.read_text(encoding="utf-8")) if target.exists() else {"papers": []}
    known = {p["id"]: p for p in previous.get("papers", [])}
    fresh: list[str] = []
    observed = incoming["observed_at"]
    cutoff = (date.fromisoformat(observed[:10]) - timedelta(days=since_days)).isoformat()
    for p in incoming.get("papers", []):
        if p["published"] < cutoff:
            continue
        if p["id"] not in known:
            known[p["id"]] = {**p, "first_seen": observed, "last_seen": observed}
            fresh.append(p["id"])
        else:
            known[p["id"]]["last_seen"] = observed
            if p["relevance_score"] > known[p["id"]]["relevance_score"]:
                known[p["id"]].update({k: p[k] for k in ("title", "abstract_excerpt", "relevance_score", "topic")})
    rows = sorted(known.values(), key=lambda x: (x["published"], x["relevance_score"], x["id"]), reverse=True)[:350]
    target.write_text(json.dumps({"schema_version": 1, "papers": rows}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {"as_of": observed[:10], "fetched": len(incoming.get("papers", [])),
              "new_ids": fresh, "new_count": len(fresh), "total_retained": len(rows),
              "source_errors": incoming.get("errors", []),
              "classification": "research_signal_only"}
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="cmd", required=True)
    a = commands.add_parser("crawl")
    a.add_argument("--output", default="artifacts/research_radar.json")
    b = commands.add_parser("merge")
    b.add_argument("--input", default="artifacts/research_radar.json")
    b.add_argument("--target", default="data/research_radar.json")
    b.add_argument("--report", default="data/research_radar_report.json")
    args = parser.parse_args()
    result = crawl(Path(args.output)) if args.cmd == "crawl" else merge(
        Path(args.input), Path(args.target), Path(args.report))
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
