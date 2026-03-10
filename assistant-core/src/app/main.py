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
    return parser


def main() -> int:
    args = build_parser().parse_args()
    user_input = " ".join(args.command).strip()
    app = AssistantApp(config_root=Path(args.config_root), state_root=Path(args.state_root))
    result = app.handle_text(user_input or "status")
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(result["message"])
    return 0


if __name__ == "__main__":
    sys.exit(main())
