from __future__ import annotations

import argparse
import hashlib
import ipaddress
import json
import os
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.request import Request, urlopen

from bs4 import BeautifulSoup
if __package__:
    from .marketplace_sources import collect_board
else:
    from marketplace_sources import collect_board

ROOT = Path(__file__).resolve().parents[1]
INRIA_INDEX = "https://jobs.inria.fr/public/classic/en/offres?filtre=doctorants"
BRAVE_ENDPOINT = "https://api.search.brave.com/res/v1/web/search"
MAX_RESPONSE = 1_500_000
TOPICS = {
    "robot_perception": [
        '"funded PhD" robotics SLAM visual inertial 2027 university',
        '"doctoral position" world models robot perception university',
    ],
    "machine_learning": [
        '"PhD position" machine learning foundation models 2027 university',
        '"funded doctoral" trustworthy AI optimization 2027',
    ],
    "space_autonomy": [
        '"PhD" satellite navigation spacecraft autonomy 2027 funded',
        '"doctoral position" aerospace state estimation orbital robotics',
    ],
    "medical_ai": [
        '"PhD position" biomedical AI multimodal imaging 2027 funded',
        '"doctoral research" medical robotics clinical machine learning',
    ],
    "robot_learning": [
        '"PhD position" robot learning manipulation 2027',
        '"doctoral researcher" embodied AI locomotion robotics 2027',
    ],
}
WEIGHTS = {
    "slam": 7, "visual-inertial": 7, "state estimation": 6,
    "robotics": 4, "robot": 3, "perception": 3, "world model": 5,
    "navigation": 4, "manipulation": 3, "reinforcement learning": 3,
    "machine learning": 3, "artificial intelligence": 2, "spacecraft": 5,
    "satellite": 5, "aerospace": 4, "computer vision": 4,
    "multimodal": 2, "medical": 2, "optimization": 2, "optimisation": 2,
}
IGNORE_PARAMS = {"utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term", "fbclid", "gclid", "ref"}
USER_AGENT = "PhDTrackerEvidenceGraph/1.0 (+research; public academic positions)"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def safe_url(value: str) -> str | None:
    try:
        p = urlsplit(str(value))
        if p.scheme != "https" or not p.hostname or p.username or p.password:
            return None
        if p.port not in (None, 443):
            return None
        host = p.hostname.lower()
        if host == "localhost" or host.endswith((".local", ".internal")):
            return None
        try:
            address = ipaddress.ip_address(host)
            if not address.is_global:
                return None
        except ValueError:
            pass
        query = urlencode(sorted((k, v) for k, v in parse_qsl(p.query, keep_blank_values=True) if k.lower() not in IGNORE_PARAMS))
        return urlunsplit(("https", host, p.path.rstrip("/") or "/", query, ""))
    except (ValueError, TypeError):
        return None


def evidence_id(provider: str, url: str, reference: str | None = None) -> str:
    if reference and provider == "inria":
        return f"inria:{reference}"
    return "web:" + hashlib.sha256(url.encode("utf-8")).hexdigest()[:20]


def relevant_score(text: str) -> tuple[int, list[str]]:
    low = re.sub(r"\s+", " ", text).lower()
    matches = [name for name in WEIGHTS if name in low]
    return sum(WEIGHTS[m] for m in matches), matches


def load_json(path: Path, default: dict) -> dict:
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def fetch_bytes(url: str, headers: dict[str, str] | None = None, max_size: int = MAX_RESPONSE) -> tuple[bytes, str]:
    if not safe_url(url):
        raise ValueError("Unsafe or malformed URL")
    req = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json", **(headers or {})})
    with urlopen(req, timeout=20) as response:
        final = response.geturl()
        if not safe_url(final):
            raise ValueError("Unsafe redirect")
        if int(response.headers.get("Content-Length", "0") or 0) > max_size:
            raise ValueError("Response exceeds cap")
        data = response.read(max_size + 1)
    if len(data) > max_size:
        raise ValueError("Response exceeds cap")
    return data, final


def inria_cards(html_bytes: bytes, observed: str) -> list[dict]:
    soup = BeautifulSoup(html_bytes, "html.parser")
    strings = [re.sub(r"\s+", " ", x).strip() for x in soup.stripped_strings]
    found: dict[str, dict] = {}
    for idx, token in enumerate(strings):
        if not re.search(r"^(?:PhD Position|Doctorant(?:e)?\s|Doctoral position)", token, re.I):
            continue
        window = " ".join(strings[idx : idx + 12])
        ref = re.search(r"(20\d{2}-\d{4,5})", window)
        deadline = re.search(r"(?:Deadline to apply|Date limite pour postuler)\s*:\s*(20\d{2}-\d{2}-\d{2})", window, re.I)
        if not ref or not deadline:
            continue
        title = token[:240]
        canonical = f"https://jobs.inria.fr/public/classic/en/offres/{ref.group(1)}"
        score, hits = relevant_score(title)
        if score < 2:
            continue
        found[ref.group(1)] = {
            "id": evidence_id("inria", canonical, ref.group(1)),
            "title": title,
            "url": canonical,
            "provider": "inria",
            "lane": "official_institution",
            "deadline": deadline.group(1),
            "deadline_provenance": "Inria official listing",
            "evidence_status": "official_index",
            "funding_status": "not_independently_verified",
            "score": score,
            "matched_topics": hits,
            "snippet": window[:400],
            "observed_at": observed,
        }
    for anchor in soup.select('a[href*="/offres/"]'):
        title = anchor.get_text(" ", strip=True)
        if not re.search(r"^(?:PhD Position|Doctorant)", title, re.I):
            continue
        href = urljoin(INRIA_INDEX, anchor.get("href", ""))
        ref = re.search(r"/(20\d{2}-\d{4,5})(?:\?|$|/)", href)
        if ref and ref.group(1) in found:
            full = safe_url(href)
            if full:
                found[ref.group(1)]["url"] = full
    return sorted(found.values(), key=lambda r: (r["deadline"], r["id"]))


def collect_inria(observed: str) -> list[dict]:
    data, final = fetch_bytes(INRIA_INDEX)
    records = inria_cards(data, observed)
    if not records:
        raise ValueError(f"Inria parser returned zero relevant doctoral positions: {final}")
    return records


def choose_queries(state_file: Path, week: int, max_queries: int = 5) -> list[tuple[str, str]]:
    old = load_json(state_file, {"records": []}).get("records", [])
    counts = {lane: sum(r.get("lane") == lane for r in old if r.get("evidence_status") != "expired") for lane in TOPICS}
    lanes = sorted(TOPICS, key=lambda key: (counts[key], key))
    return [(lane, TOPICS[lane][(week + idx) % len(TOPICS[lane])]) for idx, lane in enumerate(lanes[:max_queries])]


def collect_brave(observed: str, state_file: Path) -> tuple[list[dict], str | None]:
    token = os.environ.get("BRAVE_SEARCH_API_KEY", "").strip()
    if not token:
        return [], "BRAVE_SEARCH_API_KEY missing: broad multi-country search disabled"
    queries = choose_queries(state_file, date.today().isocalendar().week)
    def search(item: tuple[str, str]) -> tuple[str, list[dict]]:
        lane, query = item
        args = urlencode({"q": query, "count": 20, "freshness": "pm", "search_lang": "en"})
        payload, _ = fetch_bytes(BRAVE_ENDPOINT + "?" + args, {"X-Subscription-Token": token, "Accept": "application/json"})
        response = json.loads(payload)
        rows = []
        for raw in response.get("web", {}).get("results", []):
            url = safe_url(raw.get("url", ""))
            title = str(raw.get("title") or "")[:240]
            desc = str(raw.get("description") or "")[:450]
            if not url:
                continue
            text = title + " " + desc
            if not re.search(r"\b(phd|doctoral|studentship|doctorant|research fellow)\b", text, re.I):
                continue
            score, hits = relevant_score(text)
            if score < 3:
                continue
            matches = re.findall(r"(?:deadline|apply by|closing date)\s*[:\-]?\s*(20\d{2}-\d{2}-\d{2})", text, re.I)
            rows.append({
                "id": evidence_id("brave", url), "title": title,
                "url": url, "provider": "brave", "lane": lane,
                "deadline": matches[0] if matches else None,
                "deadline_provenance": "Search snippet; unverified" if matches else "Unknown",
                "evidence_status": "search_lead_unverified",
                "funding_status": "not_independently_verified",
                "score": score, "matched_topics": hits,
                "snippet": desc, "observed_at": observed,
            })
        return lane, rows
    errors: list[str] = []
    results: list[dict] = []
    with ThreadPoolExecutor(max_workers=3) as pool:
        futures = [pool.submit(search, item) for item in queries]
        for item, future in zip(queries, futures):
            try:
                _, rows = future.result()
                results.extend(rows)
            except (ValueError, URLError, HTTPError, OSError) as e:
                errors.append(f"{item[0]}: {type(e).__name__}: {str(e)[:90]}")
    if errors and not results:
        raise ValueError("; ".join(errors))
    return results, "; ".join(errors) if errors else None


def collect(provider: str, output: Path, state: Path) -> dict:
    observed = utc_now()
    errors: list[str] = []
    records: list[dict] = []
    try:
        if provider == "inria":
            records = collect_inria(observed)
        elif provider == "brave":
            records, warning = collect_brave(observed, state)
        elif provider in ("academictransfer", "academicpositions"):
            records = collect_board(provider, observed, fetch_bytes, safe_url, relevant_score, evidence_id)
            if warning:
                errors.append(warning)
        else:
            raise ValueError(f"Unknown provider: {provider}")
    except (ValueError, URLError, HTTPError, OSError, json.JSONDecodeError) as e:
        errors.append(f"{type(e).__name__}: {str(e)[:160]}")
    result = {"schema_version": 1, "provider": provider, "observed_at": observed,
              "records": records, "errors": errors}
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return result


def aggregate(input_dir: Path, output: Path, report_path: Path) -> dict:
    sources = sorted(input_dir.glob("*.json"))
    if not sources:
        raise ValueError("No collector artifacts: refusing to publish discovery")
    previous = load_json(output, {"schema_version": 1, "records": []})
    records = {r["id"]: r for r in previous.get("records", [])}
    by_url = {safe_url(r.get("url", "")): r["id"] for r in records.values() if safe_url(r.get("url", ""))}
    errors: dict[str, list[str]] = {}
    new_ids: list[str] = []
    counts: dict[str, int] = {}
    aliases: list[dict] = []
    new_by_provider: dict[str, int] = {}
    duplicates_by_provider: dict[str, int] = {}
    for filename in sources:
        result = json.loads(filename.read_text(encoding="utf-8"))
        provider = result["provider"]
        errors[provider] = result.get("errors", [])
        counts[provider] = len(result["records"])
        for entry in result["records"]:
            canonical = safe_url(entry.get("url", ""))
            if not canonical or entry.get("score", 0) < 2:
                continue
            entry = {**entry, "url": canonical}
            incoming_id = entry["id"]
            key = by_url.get(canonical, incoming_id)
            if key not in records:
                records[key] = {**entry, "first_seen": entry["observed_at"],
                                "last_seen": entry["observed_at"], "seen_count": 1,
                                "aliases": [], "deadline_change_needs_review": False,
                                "source_observations": [{
                                    "provider": provider, "at": entry["observed_at"],
                                    "deadline": entry.get("deadline"),
                                    "confidence": entry.get("evidence_status"),
                                }]}
                by_url[canonical] = key
                new_ids.append(key)
                new_by_provider[provider] = new_by_provider.get(provider, 0) + 1
                continue
            duplicates_by_provider[provider] = duplicates_by_provider.get(provider, 0) + 1
            original = records[key]
            if incoming_id != key:
                original.setdefault("aliases", [])
                if incoming_id not in original["aliases"]:
                    original["aliases"].append(incoming_id)
                    aliases.append({"canonical_id": key, "alias": incoming_id})
            recorded = original.get("deadline")
            proposed = entry.get("deadline")
            if recorded and proposed and recorded != proposed:
                original["proposed_deadline"] = proposed
                original["deadline_change_needs_review"] = True
            elif not recorded and proposed:
                original["deadline"] = proposed
                original["deadline_provenance"] = entry.get("deadline_provenance", "")
            original["last_seen"] = entry["observed_at"]
            original["seen_count"] = original.get("seen_count", 1) + 1
            original["score"] = max(original.get("score", 0), entry.get("score", 0))
            original.setdefault("source_observations", []).append({
                "provider": provider, "at": entry["observed_at"],
                "deadline": proposed, "confidence": entry.get("evidence_status"),
            })
            original["source_observations"] = original["source_observations"][-12:]
            if original.get("evidence_status") == "search_lead_unverified" and entry.get("evidence_status") == "official_index":
                original.update({"evidence_status": "official_index", "provider": provider,
                                 "title": entry.get("title", original["title"]),
                                 "snippet": entry.get("snippet", original.get("snippet", ""))})
    cutoff = date.today().isoformat()
    results = sorted(records.values(), key=lambda r: (-r.get("score", 0), r.get("deadline") or "9999", r["id"]))[:2000]
    stale = []
    for item in results:
        observed = (item.get("last_seen") or "")[:10]
        try:
            if (date.today() - date.fromisoformat(observed)).days > 21:
                stale.append(item["id"])
        except ValueError:
            stale.append(item["id"])
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps({"schema_version": 2, "records": results}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    report = {
        "run_date": cutoff, "new_ids": new_ids, "new_count": len(new_ids),
        "seen_by_provider": counts, "source_errors": errors, "total": len(results),
        "source_yield": {name: {
            "observed": count,
            "new_unique": new_by_provider.get(name, 0),
            "reobservations": duplicates_by_provider.get(name, 0),
            "unique_yield": round(new_by_provider.get(name, 0) / count, 4) if count else None,
            "health": "disabled" if count == 0 and any("missing" in e.lower() for e in errors.get(name, []))
                      else "degraded" if errors.get(name) or count == 0 else "ok",
        } for name, count in counts.items()},
        "actionable_new": [r["id"] for r in results if r["id"] in new_ids and
                           r["score"] >= 5 and (not r["deadline"] or r["deadline"] >= cutoff)][:25],
        "deadline_conflicts": [r["id"] for r in results if r.get("deadline_change_needs_review")],
        "stale_observations": stale[:100],
        "url_aliases": aliases[:100],
    }
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    first = sub.add_parser("collect")
    first.add_argument("--source", choices=("inria", "brave", "academictransfer", "academicpositions"), required=True)
    first.add_argument("--output", required=True)
    first.add_argument("--state", default="data/discovered_candidates.json")
    second = sub.add_parser("aggregate")
    second.add_argument("--input", default="artifacts/discovery")
    second.add_argument("--output", default="data/discovered_candidates.json")
    second.add_argument("--report", default="data/discovery_report.json")
    args = parser.parse_args()
    if args.command == "collect":
        result = collect(args.source, Path(args.output), Path(args.state))
    else:
        result = aggregate(Path(args.input), Path(args.output), Path(args.report))
    print(json.dumps({k: v for k, v in result.items() if k != "records"}, ensure_ascii=False, default=str))


if __name__ == "__main__":
    main()
