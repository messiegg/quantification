#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.report_metadata import metadata_header, write_json
from src.utils.config import resolve_path


JSON_PATH = "reports/backtest/release/test_status.json"
MD_PATH = "reports/backtest/release/test_status.md"


def record_test_status(status: str, command: str, exit_code: int = 0, note: str = "") -> dict:
    payload = {
        **metadata_header(),
        "status": status,
        "command": command,
        "exit_code": exit_code,
        "note": note,
    }
    write_json(JSON_PATH, payload)
    path = resolve_path(MD_PATH)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        "\n".join(
            [
                "# test status",
                "",
                f"- status: {status}",
                f"- command: {command}",
                f"- exit_code: {exit_code}",
                f"- git_commit: {payload['git_commit']}",
                f"- config_hash: {payload['config_hash']}",
                f"- note: {note}",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    return payload


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Record the latest pytest status for release guard integration.")
    parser.add_argument("--status", choices=["PASS", "WARN", "FAIL"], required=True)
    parser.add_argument("--command", required=True)
    parser.add_argument("--exit-code", type=int, default=0)
    parser.add_argument("--note", default="")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    record_test_status(args.status, args.command, args.exit_code, args.note)
    return 0 if args.status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
