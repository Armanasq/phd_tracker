from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any, Iterable

_LICENSE_FILES = frozenset({
    "license", "license.md", "license.txt", "license.rst",
    "copying", "copying.md", "copying.txt",
})
_ASSET_EXTENSIONS = frozenset({
    ".svg", ".png", ".jpg", ".jpeg", ".gif", ".webp",
    ".ico", ".ttf", ".otf", ".woff", ".woff2", ".stl",
})
_REQUIREMENTS = re.compile(r"^requirements[^/]*\.txt$")
_EXTERNAL_ACTION = re.compile(r"^\s*-\s*uses:\s*([^\s#]+)", re.I)


def tracked_paths(root: Path) -> list[str]:
    process = subprocess.run(
        ["git", "-C", str(root), "ls-files", "-z"],
        capture_output=True, check=True, shell=False,
    )
    return [value.decode("utf-8") for value in process.stdout.split(b"\0") if value]


def _safe_files(root: Path, names: Iterable[str]) -> list[str]:
    files: set[str] = set()
    for name in names:
        if not isinstance(name, str) or not name:
            raise ValueError("Tracked path must be a nonempty string")
        relative = Path(name)
        if relative.is_absolute() or ".." in relative.parts or "\\" in name:
            raise ValueError("Tracked path must stay inside the repository")
        target = root / relative
        if target.is_symlink() or not target.resolve().is_relative_to(root):
            raise ValueError("Provenance inventory refuses symlinks and paths outside the repository")
        if target.is_file():
            files.add(relative.as_posix())
    return sorted(files)


def audit_redistribution(
    root: Path, *, filenames: Iterable[str] | None = None,
) -> dict[str, Any]:
    root = Path(root).expanduser().resolve()
    names = _safe_files(root, tracked_paths(root) if filenames is None else filenames)
    license_files = [
        name for name in names if "/" not in name and name.casefold() in _LICENSE_FILES
    ]
    requirements = [
        name for name in names if "/" not in name and _REQUIREMENTS.fullmatch(name)
    ]
    packages: list[dict[str, str]] = []
    for name in requirements:
        for line in (root / name).read_text(encoding="utf-8").splitlines():
            declaration = line.split("#", 1)[0].strip()
            if declaration:
                packages.append({"manifest": name, "declaration": declaration})
    actions: list[dict[str, str]] = []
    for name in names:
        if not name.startswith(".github/workflows/") or not name.endswith((".yml", ".yaml")):
            continue
        for line in (root / name).read_text(encoding="utf-8").splitlines():
            match = _EXTERNAL_ACTION.match(line)
            if match and not match[1].startswith("./"):
                actions.append({"workflow": name, "reference": match[1]})
    assets = [
        name for name in names if Path(name).suffix.casefold() in _ASSET_EXTENSIONS
    ]
    data = [
        name for name in names
        if name.startswith("data/") or name.lower().endswith((".xlsx", ".xls", ".pdf"))
    ]
    source = [
        name for name in names
        if name.startswith(("phd_agents/", "site/", "scripts/", "dashboard/"))
        and Path(name).suffix.casefold() in {".py", ".js", ".mjs", ".html", ".css"}
    ]
    return {
        "schema_version": 1,
        "status": "blocked_pending_rightsholder_and_data_provenance_attestation",
        "license": {
            "file_present": bool(license_files),
            "files": license_files,
            "legal_grant_verified": False,
        },
        "counts": {
            "tracked_files": len(names),
            "application_source_files": len(source),
            "research_data_files": len(data),
            "bundled_visual_or_font_assets": len(assets),
            "declared_python_dependencies": len(packages),
            "external_workflow_action_references": len(actions),
        },
        "python_dependencies": packages,
        "workflow_actions": actions,
        "research_data_paths": data,
        "visual_asset_paths": assets,
        "review_required": [
            "Obtain the copyright holder's authorized software-license decision.",
            "Check external package, workflow Action, and artwork license obligations.",
            "Review research records, imported workbooks and source extracts for redistribution rights.",
            "Separate generated and synthetic outputs from user-owned private data and third-party assets.",
            "Audit public Git history for credentials and personal information independently.",
        ],
        "limitations": (
            "Tracked paths and dependency declarations do not prove copyright ownership, "
            "license compatibility, data permissions, or privacy compliance. "
            "This audit does not grant rights or certify an open-source release."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Inventory redistribution evidence without granting any license"
    )
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    result = audit_redistribution(args.root)
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        for name, count in result["counts"].items():
            print(f"{name}: {count}")
        print("status: " + result["status"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
