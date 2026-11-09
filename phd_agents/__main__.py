from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from .catalog import PROVIDERS
from .engine import catalog, run_agent, scheduler_once
from .server import ROOT, serve
from .store import Store

def main() -> None:
    parser = argparse.ArgumentParser(prog="python -m phd_agents")
    parser.add_argument("--repo", type=Path, default=ROOT)
    commands = parser.add_subparsers(dest="command", required=True)
    server = commands.add_parser("serve")
    server.add_argument("--port", type=int, default=8765)
    commands.add_parser("scheduler-once")
    commands.add_parser("catalog")
    agent = commands.add_parser("run")
    agent.add_argument("--agent", default="portfolio_planner")
    agent.add_argument("--provider", default="ollama")
    agent.add_argument("--application")
    agent.add_argument("--task", default="")
    agent.add_argument("--allow-cloud", action="store_true")
    args = parser.parse_args()
    if args.command == "serve":
        serve(port=args.port, root=args.repo)
        return
    store = Store()
    try:
        if args.command == "catalog":
            result = catalog(store)
            for item in result["providers"]:
                item["configured"] = not item["api_key_env"] or bool(os.environ.get(item["api_key_env"]))
        elif args.command == "scheduler-once":
            result = scheduler_once(store, args.repo)
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
