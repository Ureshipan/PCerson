from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from orchestration.app import AssistantApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PCerson assistant-core CLI")
    parser.add_argument("command", nargs="*", help="User command for assistant")
    parser.add_argument("--config-root", default="config", help="Config root directory")
    parser.add_argument("--state-root", default="state", help="State root directory")
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print structured response as JSON",
    )
    parser.add_argument(
        "--chat",
        action="store_true",
        help="Run interactive text chat loop",
    )
    return parser


def run_chat(app: AssistantApp, as_json: bool) -> int:
    print("PCerson chat mode. Type 'exit' or 'quit' to stop.")
    while True:
        try:
            user_input = input("you> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return 0
        if not user_input:
            continue
        if user_input.lower() in {"exit", "quit", "q"}:
            return 0
        result = app.handle_text(user_input)
        if as_json:
            print(json.dumps(result, ensure_ascii=False, indent=2))
        else:
            print(f"assistant> {result['message']}")


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if hasattr(sys.stderr, "reconfigure"):
        sys.stderr.reconfigure(encoding="utf-8")
    args = build_parser().parse_args()
    user_input = " ".join(args.command).strip()
    app = AssistantApp(config_root=Path(args.config_root), state_root=Path(args.state_root))
    if args.chat:
        return run_chat(app=app, as_json=args.json)
    result = app.handle_text(user_input or "status")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["message"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
