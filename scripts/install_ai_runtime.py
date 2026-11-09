from __future__ import annotations

import argparse
import os
import subprocess
import sys
from pathlib import Path

UNITS = ("phd-atlas-ai.service", "phd-atlas-ai-scheduler.service", "phd-atlas-ai-scheduler.timer")


def unit_value(value: object) -> str:
    text = str(value)
    if not text or any(char in text for char in "\n\r\x00"):
        raise ValueError("Invalid path or command argument")
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'


def generate(repo: Path, python: Path, envfile: Path, port: int) -> dict[str, str]:
    repo = repo.expanduser().resolve()
    python = python.expanduser().resolve()
    envfile = envfile.expanduser().resolve()
    if not 1024 <= port <= 65535:
        raise ValueError("Private runtime port must be in [1024,65535]")
    if not (repo / "phd_agents" / "server.py").is_file():
        raise ValueError("Repository root is missing phd_agents/server.py")
    common = ("WorkingDirectory=" + unit_value(repo) + "\n"
              "EnvironmentFile=-" + str(envfile).replace("%", "%%") + "\n"
              "UMask=0077\nNoNewPrivileges=yes\nPrivateTmp=yes\n")
    run = ("[Unit]\nDescription=PhD Atlas private AI runtime\nAfter=network.target\n"
           "[Service]\nType=simple\n" + common +
           "ExecStart=" + unit_value(python) + " -m phd_agents serve --port " + str(port) + "\n"
           "Restart=on-failure\nRestartSec=7\n[Install]\nWantedBy=default.target\n")
    tick = ("[Unit]\nDescription=PhD Atlas scheduled AI workflow check\nAfter=network.target\n"
            "[Service]\nType=oneshot\n" + common +
            "ExecStart=" + unit_value(python) + " -m phd_agents scheduler-once\n")
    timer = ("[Unit]\nDescription=Evaluate enabled PhD Atlas AI workflows twice daily\n"
             "[Timer]\nOnCalendar=*-*-* 08,20:00:00\nPersistent=true\n"
             "Unit=phd-atlas-ai-scheduler.service\n"
             "[Install]\nWantedBy=timers.target\n")
    return dict(zip(UNITS, (run, tick, timer)))


def install(units: dict[str, str], location: Path, envfile: Path, *, overwrite: bool) -> list[Path]:
    location.mkdir(parents=True, exist_ok=True, mode=0o700)
    envfile.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if not envfile.exists():
        fd = os.open(envfile, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        os.close(fd)
    result = []
    for filename, content in units.items():
        dest = location / filename
        if dest.exists() and not overwrite:
            raise FileExistsError(str(dest) + " already exists; use --overwrite to replace it")
        dest.write_text(content, encoding="utf-8")
        result.append(dest)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--python", type=Path, default=Path(sys.executable))
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--install", action="store_true")
    parser.add_argument("--enable", action="store_true")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args()
    root = Path.home()
    envfile = root / ".config" / "phd-atlas-ai" / "provider.env"
    units = generate(args.repo, args.python, envfile, args.port)
    location = root / ".config" / "systemd" / "user"
    if not args.install and not args.enable:
        for filename, content in units.items():
            print("--- " + filename + " ---\n" + content)
        print("Preview only; use --install to write user service files.")
        return
    paths = install(units, location, envfile, overwrite=args.overwrite)
    for path in paths:
        print(path)
    if args.enable:
        subprocess.run(["systemctl", "--user", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "--user", "enable", "--now", "phd-atlas-ai.service", "phd-atlas-ai-scheduler.timer"], check=True)
        print("Enabled private runtime and scheduled checker; workflows remain individually disabled until approved.")
    else:
        print("Services installed but not activated. Use --enable when configured.")


if __name__ == "__main__":
    main()
