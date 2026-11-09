from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, urlsplit
from xml.sax.saxutils import escape as xml_escape

DEFAULT_REPOSITORY = "Armanasq/phd_tracker"
ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_PATTERN = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,99}/[A-Za-z0-9][A-Za-z0-9_.-]{0,99}")


def validate_repository(value: str) -> str:
    if not isinstance(value, str) or not REPOSITORY_PATTERN.fullmatch(value):
        raise ValueError("Repository must be a valid GitHub owner/name pair")
    owner, name = value.split("/", 1)
    if owner.endswith(".") or name.endswith(".") or ".." in owner or ".." in name:
        raise ValueError("Invalid GitHub repository identifier")
    return value


def git_repository(root: Path = ROOT) -> str | None:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "remote", "get-url", "origin"],
            capture_output=True, text=True, timeout=3, check=False,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    if result.returncode:
        return None
    remote = result.stdout.strip()
    if remote.startswith("git@github.com:"):
        path = remote[len("git@github.com:"):]
    else:
        parsed = urlsplit(remote)
        if parsed.scheme != "https" or parsed.hostname != "github.com" or parsed.username or parsed.password:
            return None
        path = parsed.path.lstrip("/")
    if path.endswith(".git"):
        path = path[:-4]
    try:
        return validate_repository(path)
    except ValueError:
        return None


def resolve_repository(explicit: str | None = None, *, root: Path = ROOT) -> str:
    for candidate in (
        explicit, os.environ.get("PHD_ATLAS_REPOSITORY"),
        os.environ.get("GITHUB_REPOSITORY"), git_repository(root), DEFAULT_REPOSITORY,
    ):
        if candidate:
            return validate_repository(candidate.strip())
    return DEFAULT_REPOSITORY


def resolve_data_mode(repository: str, override: str | None = None) -> str:
    repository = validate_repository(repository)
    choice = override if override is not None else os.environ.get("PHD_ATLAS_DATA_MODE", "")
    mode = str(choice or "").strip().lower()
    if not mode:
        return "source" if repository.casefold() == DEFAULT_REPOSITORY.casefold() else "starter"
    if mode not in {"source", "starter"}:
        raise ValueError("Data mode must be source or starter")
    return mode


def repository_url(repository: str) -> str:
    return "https://github.com/" + validate_repository(repository)


def pages_url(repository: str, override: str | None = None) -> str:
    owner, name = validate_repository(repository).split("/", 1)
    if override:
        parsed = urlsplit(override.strip())
        if (
            parsed.scheme != "https" or not parsed.hostname or parsed.username
            or parsed.password or parsed.port is not None or parsed.query or parsed.fragment
            or any(char in override for char in ('"', "'", "<", ">", "\\", " "))
        ):
            raise ValueError("Custom Pages URL must be an HTTPS URL without credentials, query or fragment")
        return override.rstrip("/") + "/"
    if name.casefold() == (owner + ".github.io").casefold():
        return f"https://{owner.lower()}.github.io/"
    return f"https://{owner.lower()}.github.io/{quote(name, safe='')}/"


def action_center_url(repository: str, issue_number: str | int | None = None) -> str:
    base = repository_url(repository)
    number = issue_number if issue_number is not None else os.environ.get("PHD_ATLAS_ACTION_ISSUE")
    if number not in (None, ""):
        if not re.fullmatch(r"[1-9]\d*", str(number)):
            raise ValueError("PHD_ATLAS_ACTION_ISSUE must be a positive issue number")
        return f"{base}/issues/{number}"
    if repository.casefold() == DEFAULT_REPOSITORY.casefold():
        return base + "/issues/1"
    return base + "/issues/new?template=00-owner-action-center.md"


def _replace_one(source: str, pattern: str, replacement: str) -> str:
    result, count = re.subn(pattern, lambda match: replacement, source, count=1)
    if count != 1:
        raise ValueError("Deployment metadata pattern absent or ambiguous: " + pattern)
    return result


def prepare_site(
    site: Path, repository: str, *, site_url: str | None = None, commit: str | None = None,
) -> dict:
    repository = validate_repository(repository)
    canonical = pages_url(repository, site_url)
    base = repository_url(repository)
    index = site / "index.html"
    html = index.read_text(encoding="utf-8")
    html = _replace_one(html, r'<link rel="canonical" href="[^"]+">', f'<link rel="canonical" href="{canonical}">')
    html = _replace_one(html, r'<meta property="og:url" content="[^"]+">', f'<meta property="og:url" content="{canonical}">')
    html = _replace_one(html, r'<a class="side-link" href="[^"]+"', f'<a class="side-link" href="{base}"')
    html = _replace_one(
        html, r'<a href="[^"]+/releases" target="_blank" rel="noopener noreferrer">Release history</a>',
        f'<a href="{base}/releases" target="_blank" rel="noopener noreferrer">Release history</a>',
    )
    if commit:
        if not re.fullmatch(r"[a-fA-F0-9]{40}", commit):
            raise ValueError("Commit must be a 40-character Git SHA")
        html = _replace_one(
            html, r'href="\./responsive\.css(?:\?rev=[a-fA-F0-9]{40})?"',
            f'href="./responsive.css?rev={commit}"',
        )
    index.write_text(html, encoding="utf-8")
    sitemap = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f'  <url><loc>{xml_escape(canonical)}</loc></url>\n'
        f'  <url><loc>{xml_escape(canonical + "evidencegraph/")}</loc></url>\n'
        '</urlset>\n'
    )
    (site / "sitemap.xml").write_text(sitemap, encoding="utf-8")
    result = {
        "schema_version": 1,
        "repository": repository,
        "site_url": canonical,
        "source_commit": commit or None,
        "hosting": "static_github_pages",
        "private_backend_included": False,
    }
    (site / "instance.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare a portable PhD Atlas GitHub Pages artifact")
    parser.add_argument("--site", type=Path, default=ROOT / "site")
    parser.add_argument("--repository", help="GitHub owner/repository; otherwise detect from environment or git origin")
    parser.add_argument("--site-url", default=os.environ.get("PHD_ATLAS_SITE_URL"))
    parser.add_argument("--commit", default=None)
    args = parser.parse_args()
    result = prepare_site(args.site, resolve_repository(args.repository), site_url=args.site_url, commit=args.commit)
    print(json.dumps(result, sort_keys=True))


if __name__ == "__main__":
    main()
