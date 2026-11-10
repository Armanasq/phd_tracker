from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

from .catalog import PROVIDERS
from .engine import catalog, run_agent, scheduler_once
from .job_queue import worker_once
from .server import ROOT, serve
from .store import Store, private_directory
from scripts.instance_config import resolve_repository

def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m phd_agents")
    parser.add_argument("--repo", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    server = commands.add_parser("serve")
    server.add_argument("--port", type=int, default=8765)
    commands.add_parser("scheduler-once")
    commands.add_parser("worker-once")
    worker = commands.add_parser("worker-loop")
    worker.add_argument("--interval-seconds", type=int, default=3)
    worker.add_argument("--max-jobs", type=int, default=0)
    commands.add_parser("catalog")
    commands.add_parser("diagnostics")
    compare = commands.add_parser("compare-sources")
    compare.add_argument("--previous", type=Path, required=True)
    compare.add_argument("--current", type=Path, required=True)
    backup_command = commands.add_parser("backup")
    backup_command.add_argument("--retain", type=int, default=7)
    verify_command = commands.add_parser("verify-backup")
    verify_command.add_argument("filename")
    verify_command.add_argument("--sha256")
    restore_command = commands.add_parser("restore-backup")
    restore_command.add_argument("filename")
    restore_command.add_argument("--sha256")
    restore_command.add_argument("--confirm", action="store_true")
    encrypted = commands.add_parser("encrypt-backup")
    encrypted.add_argument("filename")
    encrypted.add_argument("--sha256")
    encrypted.add_argument("--output", type=Path, required=True)
    encrypted_drill = commands.add_parser("drill-encrypted-backup")
    encrypted_drill.add_argument("encrypted_path", type=Path)
    encrypted_drill.add_argument("--sha256", required=True)
    drill_command = commands.add_parser("drill-backup")
    drill_command.add_argument("filename")
    drill_command.add_argument("--sha256")
    agent = commands.add_parser("run")
    agent.add_argument("--agent", default="portfolio_planner")
    agent.add_argument("--provider", default="ollama")
    agent.add_argument("--application")
    agent.add_argument("--task", default="")
    agent.add_argument("--allow-cloud", action="store_true")
    args = parser.parse_args()
    if not os.environ.get("PHDAI_PRIVATE_DIR") and args.repo.resolve() != ROOT.resolve():
        os.environ["PHDAI_PRIVATE_DIR"] = str(private_directory(args.repo, resolve_repository(root=args.repo)))
    if args.command == "serve":
        serve(port=args.port, root=args.repo)
        return
    if args.command in {"verify-backup", "restore-backup", "drill-backup"}:
        from .recovery import drill_backup, restore_backup, verify_backup
        if args.command == "verify-backup":
            result = verify_backup(args.filename, sha256=args.sha256)
        elif args.command == "drill-backup":
            result = drill_backup(args.filename, sha256=args.sha256)
        else:
            result = restore_backup(args.filename, sha256=args.sha256, confirm=args.confirm)
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return
    if args.command == "compare-sources":
        from .source_changes import compare_sources, load_snapshot
        result = compare_sources(load_snapshot(args.previous), load_snapshot(args.current))
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command in {"encrypt-backup", "drill-encrypted-backup"}:
        from getpass import getpass
        from .recovery_encrypted import drill_encrypted_backup, export_encrypted_backup
        password = getpass("Backup encryption passphrase: ")
        if args.command == "encrypt-backup":
            repeat = getpass("Repeat backup passphrase: ")
            if password != repeat:
                parser.error("Backup passphrases do not match")
            result = export_encrypted_backup(
                args.filename, args.output, password,
                sha256=args.sha256, repo_root=args.repo,
            )
        else:
            result = drill_encrypted_backup(
                args.encrypted_path, password, sha256=args.sha256,
            )
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return
    if args.command == "worker-loop":
        if not 1 <= args.interval_seconds <= 60 or not 0 <= args.max_jobs <= 100000:
            parser.error("Worker interval must be 1–60 seconds and max-jobs 0–100000")
    store = Store()
    try:
        if args.command == "worker-once":
            result = worker_once(store, args.repo)
        elif args.command == "worker-loop":
            processed = 0
            try:
                while not args.max_jobs or processed < args.max_jobs:
                    value = worker_once(store, args.repo)
                    if value.get("status") != "idle":
                        processed += 1
                        print(json.dumps(value, ensure_ascii=False), flush=True)
                    else:
                        time.sleep(args.interval_seconds)
            except KeyboardInterrupt:
                pass
            return
        elif args.command == "catalog":
            result = catalog(store)
            for item in result["providers"]:
                item["configured"] = not item["api_key_env"] or bool(os.environ.get(item["api_key_env"]))
        elif args.command == "scheduler-once":
            result = scheduler_once(store, args.repo)
        elif args.command == "diagnostics":
            result = store.diagnostics()
        elif args.command == "backup":
            result = store.create_backup(retain=args.retain)
        elif args.command == "run":
            result = run_agent(store, args.repo, agent_id=args.agent, provider_id=args.provider,
                               application_id=args.application, input_text=args.task,
                               cloud_consent=args.allow_cloud)
        else:
            raise ValueError("Unknown command")
        print(json.dumps(result, indent=2, ensure_ascii=False))
    finally:
        store.close()

if __name__ == "__main__":
    main()
