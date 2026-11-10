from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

if __package__:
    from .instance_config import DEFAULT_REPOSITORY, pages_url, resolve_repository
else:
    from instance_config import DEFAULT_REPOSITORY, pages_url, resolve_repository

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / ".github" / "repository-metadata.json"
TOPIC = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")


def load_metadata(path: Path = METADATA, *, repository: str | None = None) -> dict[str, object]:
    settings = json.loads(path.read_text(encoding="utf-8"))
    target = resolve_repository(repository)
    if settings.get("repository") not in {DEFAULT_REPOSITORY, target}:
        raise ValueError("Metadata source must identify the upstream or current fork")
    description, topics = settings.get("description"), settings.get("topics")
    if not isinstance(description, str) or not 1 <= len(description) <= 160:
        raise ValueError("GitHub description must contain 1–160 characters")
    if not isinstance(topics, list) or not 1 <= len(topics) <= 20 or any(
        not isinstance(topic, str) or not TOPIC.fullmatch(topic) for topic in topics
    ) or len(set(topics)) != len(topics):
        raise ValueError("Invalid or duplicate repository topics")
    desired_homepage = pages_url(target, os.environ.get("PHD_ATLAS_SITE_URL"))
    if target.casefold() == DEFAULT_REPOSITORY.casefold() and settings.get("homepage") != desired_homepage:
        raise ValueError("Canonical homepage differs from the upstream metadata configuration")
    return {"description": description, "homepage": desired_homepage, "topics": topics}


def api_root(repository: str | None = None) -> str:
    return "https://api.github.com/repos/" + resolve_repository(repository)


def github_request(url: str, *, method: str = "GET", payload: dict | None = None,
                   token: str = "") -> dict:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "phd-atlas-metadata-sync",
    }
    if token:
        headers["Authorization"] = "Bearer " + token
    if payload is not None:
        headers["Content-Type"] = "application/json"
    request = Request(
        url, data=json.dumps(payload).encode("utf-8") if payload is not None else None,
        headers=headers, method=method,
    )
    try:
        with urlopen(request, timeout=20) as response:
            if response.status not in {200, 201}:
                raise RuntimeError("GitHub metadata API returned unexpected status")
            data = json.load(response)
    except HTTPError as error:
        raise RuntimeError("GitHub metadata request rejected (HTTP " + str(error.code) + ")") from None
    except (URLError, TimeoutError) as error:
        raise RuntimeError("GitHub metadata API is unavailable") from error
    if not isinstance(data, dict):
        raise RuntimeError("GitHub metadata API returned an invalid response")
    return data


def write_metadata(settings: dict[str, object], token: str, *, repository: str | None = None) -> None:
    if not token:
        raise ValueError("Repository Administration-write token is required")
    root = api_root(repository)
    github_request(root, method="PATCH", payload={"description": settings["description"],
                   "homepage": settings["homepage"]}, token=token)
    github_request(root + "/topics", method="PUT",
                   payload={"names": settings["topics"]}, token=token)


def verify_metadata(settings: dict[str, object], token: str = "", *,
                    repository: str | None = None) -> None:
    root = api_root(repository)
    current = github_request(root, token=token)
    topics = github_request(root + "/topics", token=token)
    if (current.get("description") != settings["description"]
            or current.get("homepage") != settings["homepage"]
            or set(topics.get("names", [])) != set(settings["topics"])):
        raise RuntimeError("Live GitHub About metadata differs from the desired configuration")


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview, verify or synchronize GitHub About fields")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--apply", action="store_true", help="Write with an Administration-write token")
    mode.add_argument("--verify", action="store_true", help="Verify live metadata without changing it")
    parser.add_argument("--repository", help="Override the current fork owner/name")
    args = parser.parse_args()
    repository = resolve_repository(args.repository)
    metadata = load_metadata(repository=repository)
    if args.apply:
        token = os.environ.get("GITHUB_ADMIN_TOKEN", "")
        if not token:
            parser.error("--apply requires GITHUB_ADMIN_TOKEN with repository Administration-write permission")
        write_metadata(metadata, token, repository=repository)
        verify_metadata(metadata, token, repository=repository)
        print("GitHub About metadata updated and independently verified for " + repository)
    elif args.verify:
        verify_metadata(metadata, os.environ.get("GITHUB_ADMIN_TOKEN", ""), repository=repository)
        print("Live GitHub About metadata independently verified for " + repository)
    else:
        print(json.dumps({"repository": repository, **metadata}, indent=2))
        print("Preview only. Use --verify to check live state or --apply with GITHUB_ADMIN_TOKEN.")


if __name__ == "__main__":
    main()
