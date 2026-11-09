from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
METADATA = ROOT / ".github" / "repository-metadata.json"
API_ROOT = "https://api.github.com/repos/Armanasq/phd_tracker"
TOPIC = re.compile(r"^[a-z0-9][a-z0-9-]{0,49}$")


def load_metadata(path: Path = METADATA) -> dict[str, object]:
    settings = json.loads(path.read_text(encoding="utf-8"))
    if settings.get("repository") != "Armanasq/phd_tracker":
        raise ValueError("Metadata repository does not match this project")
    description = settings.get("description")
    homepage = settings.get("homepage")
    topics = settings.get("topics")
    if not isinstance(description, str) or not 1 <= len(description) <= 160:
        raise ValueError("GitHub description must contain 1–160 characters")
    if homepage != "https://armanasq.github.io/phd_tracker/":
        raise ValueError("Homepage must be the verified canonical Pages URL")
    if not isinstance(topics, list) or not 1 <= len(topics) <= 20 or any(
        not isinstance(topic, str) or not TOPIC.fullmatch(topic) for topic in topics
    ) or len(set(topics)) != len(topics):
        raise ValueError("Invalid or duplicate repository topics")
    return {"description": description, "homepage": homepage, "topics": topics}


def write_metadata(settings: dict[str, object], token: str) -> None:
    for method, suffix, payload in (
        ("PATCH", "", {"description": settings["description"], "homepage": settings["homepage"]}),
        ("PUT", "/topics", {"names": settings["topics"]}),
    ):
        request = Request(
            API_ROOT + suffix,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                "Authorization": "Bearer " + token,
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
                "Content-Type": "application/json",
                "User-Agent": "phd-atlas-metadata-sync",
            },
            method=method,
        )
        try:
            with urlopen(request, timeout=20) as response:
                if response.status not in {200, 201}:
                    raise RuntimeError("GitHub metadata update returned unexpected HTTP status")
        except HTTPError as error:
            raise RuntimeError(
                "GitHub rejected " + suffix.lstrip("/") + " metadata update (HTTP " + str(error.code) + ")"
            ) from None
        except (URLError, TimeoutError) as error:
            raise RuntimeError("GitHub metadata API is unavailable") from error


def main() -> None:
    parser = argparse.ArgumentParser(description="Preview or synchronize GitHub About fields")
    parser.add_argument("--apply", action="store_true", help="Write with an admin-scoped GitHub token")
    args = parser.parse_args()
    metadata = load_metadata()
    if not args.apply:
        print(json.dumps(metadata, indent=2))
        print("Dry run only. Use --apply with GITHUB_ADMIN_TOKEN to update GitHub About metadata.")
        return
    token = os.environ.get("GITHUB_ADMIN_TOKEN", "")
    if not token:
        parser.error("--apply requires GITHUB_ADMIN_TOKEN with repository administration permission")
    write_metadata(metadata, token)
    print("Repository description, homepage, and topics updated.")


if __name__ == "__main__":
    main()
