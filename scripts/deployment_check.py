from __future__ import annotations

import argparse
import json
import os
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Mapping
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
MODES = ("pages", "browser-local", "actions", "local-full-stack", "cloud-full-stack")
REPOSITORY = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,38})/[A-Za-z0-9_.-]{1,100}$")


@dataclass(frozen=True)
class Check:
    code: str
    status: str
    detail: str


def inspect(root: Path, mode: str, env: Mapping[str, str]) -> list[Check]:
    if mode not in MODES:
        raise ValueError("Unsupported deployment mode")
    root = root.expanduser().resolve()
    results: list[Check] = []

    def add(code: str, status: str, detail: str) -> None:
        results.append(Check(code, status, detail))

    essential = ("site/index.html", "scripts/build_workspace.py")
    if mode in ("local-full-stack", "cloud-full-stack"):
        essential += ("phd_agents/server.py", "requirements-intelligence.txt")
    for entry in essential:
        add("file:" + entry, "ok" if (root / entry).is_file() else "error", "Required application file present" if (root / entry).is_file() else "Required application file missing")

    repository = env.get("PHD_ATLAS_REPOSITORY") or env.get("GITHUB_REPOSITORY") or ""
    if repository:
        add("repository", "ok" if REPOSITORY.fullmatch(repository) else "error", "Repository identifier has owner/repository format" if REPOSITORY.fullmatch(repository) else "Repository identifier must be owner/repository")
    elif mode != "browser-local":
        add("repository", "warning", "Set PHD_ATLAS_REPOSITORY for an independent fork")

    data_mode = (env.get("PHD_ATLAS_DATA_MODE") or "starter").lower()
    if mode in ("pages", "actions", "local-full-stack"):
        if data_mode not in ("starter", "source"):
            add("data-mode", "error", "PHD_ATLAS_DATA_MODE must be starter or source")
        elif data_mode == "source":
            src = root / "data/user_opportunities.json"
            if not src.is_file():
                add("data-mode", "error", "Source mode requires data/user_opportunities.json")
            else:
                try:
                    doc = json.loads(src.read_text(encoding="utf-8"))
                    valid = isinstance(doc, dict) and doc.get("schema_version") == 1 and isinstance(doc.get("records"), list) and not (set(doc) - {"schema_version", "as_of", "timezone", "records"})
                except (OSError, ValueError):
                    valid = False
                add("data-mode", "ok" if valid else "error", "Independent source JSON parsed" if valid else "Source JSON must contain schema_version=1 and a records array")
        else:
            add("data-mode", "ok", "Starter mode does not publish inherited opportunities")

    if mode == "local-full-stack":
        limit = env.get("PHDAI_MAX_CONCURRENT_INFERENCE", "2")
        try:
            valid_limit = 1 <= int(limit) <= 8
        except ValueError:
            valid_limit = False
        add("inference-limit", "ok" if valid_limit else "error", "Inference admission limit valid" if valid_limit else "PHDAI_MAX_CONCURRENT_INFERENCE must be an integer from 1 to 8")
        private = env.get("PHDAI_PRIVATE_DIR", "")
        if private:
            private_path = Path(private).expanduser().resolve()
            add("private-storage", "error" if private_path.is_relative_to(root) else "ok", "Private state must stay outside repository" if private_path.is_relative_to(root) else "Private storage configured outside repository")
        else:
            add("private-storage", "ok", "Runtime uses its own checkout-scoped private directory")
        if env.get("PHDAI_API_TOKEN"):
            add("api-token", "warning", "API token requires an authenticated client; the bundled browser does not provide a bearer token")

    if mode == "actions":
        enabled = env.get("PHD_ATLAS_ENABLE_HOSTED_AI", "").lower() == "true"
        if not enabled:
            add("hosted-ai", "warning", "Hosted AI is opt-in and disabled")
        else:
            url = env.get("PHD_ATLAS_AI_BASE_URL", "")
            parsed = urlsplit(url)
            valid = parsed.scheme == "https" and bool(parsed.hostname) and not (parsed.username or parsed.password or parsed.query or parsed.fragment)
            add("hosted-endpoint", "ok" if valid else "error", "HTTPS model endpoint configured" if valid else "Hosted model endpoint must be HTTPS without embedded credentials")
            add("hosted-model", "ok" if env.get("PHD_ATLAS_AI_MODEL") else "error", "Model configured" if env.get("PHD_ATLAS_AI_MODEL") else "PHD_ATLAS_AI_MODEL required")
            add("hosted-key", "ok" if env.get("PHD_ATLAS_AI_API_KEY") else "warning", "Provider credential available to current process" if env.get("PHD_ATLAS_AI_API_KEY") else "Provider key must be supplied through GitHub environment secrets at workflow runtime")

    if mode == "browser-local":
        add("browser-local", "warning", "Browser CORS and Local Network Access permissions require a live browser and server test")
    if mode == "cloud-full-stack":
        add("cloud-backend", "error", "Authenticated cloud API, persistent worker service, and multi-user isolation are not implemented; do not expose the loopback API")
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Inspect PhD Atlas deployment prerequisites without printing secrets")
    parser.add_argument("--mode", choices=MODES, required=True)
    parser.add_argument("--root", type=Path, default=ROOT)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = inspect(args.root, args.mode, os.environ)
    if args.json:
        print(json.dumps({"mode": args.mode, "checks": [asdict(item) for item in result]}, indent=2))
    else:
        for item in result:
            print(f"{item.status.upper():7} {item.code}: {item.detail}")
    return int(any(item.status == "error" for item in result))


if __name__ == "__main__":
    raise SystemExit(main())
