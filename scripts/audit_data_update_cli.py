#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.config import resolve_path


OUTPUT_DIR = Path("reports/data_update/provider_preflight")
DEFAULT_CSV = OUTPUT_DIR / "data_update_cli_audit.csv"
DEFAULT_MD = OUTPUT_DIR / "data_update_cli_audit.md"
SCRIPTS = [
    "scripts/update_market_data.py",
    "scripts/build_features.py",
    "scripts/check_data_freshness.py",
    "scripts/check_data_quality_for_observation.py",
    "scripts/update_market_data_safe.py",
]


def _run_help(script_path: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, script_path, "--help"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )


def _supports(help_text: str, option: str) -> bool:
    return option in help_text


def build_update_commands(target_trading_date: str, next_missing_date: str | None = None, audit_frame: pd.DataFrame | None = None) -> tuple[list[list[str]], str]:
    frame = audit_frame if audit_frame is not None else audit_data_update_cli(write_report=False)
    by_script = {str(row["script_path"]): row for row in frame.to_dict(orient="records")}
    update = by_script.get("scripts/update_market_data.py", {})
    features = by_script.get("scripts/build_features.py", {})
    if str(update.get("status")) == "FAIL" or str(features.get("status")) == "FAIL":
        return [], "UPDATE_CLI_UNSUPPORTED"

    update_cmd = [sys.executable, "scripts/update_market_data.py"]
    if bool(update.get("supports_as_of_date")):
        update_cmd.extend(["--as-of-date", target_trading_date])
    elif bool(update.get("supports_start_date")) and bool(update.get("supports_end_date")) and next_missing_date:
        update_cmd.extend(["--start-date", next_missing_date, "--end-date", target_trading_date])
    else:
        return [], "UPDATE_CLI_UNSUPPORTED"
    if bool(update.get("supports_all_stocks")):
        update_cmd.append("--all-stocks")

    feature_cmd = [sys.executable, "scripts/build_features.py"]
    if bool(features.get("supports_as_of_date")):
        feature_cmd.extend(["--as-of-date", target_trading_date])
    elif bool(features.get("supports_start_date")) and bool(features.get("supports_end_date")) and next_missing_date:
        feature_cmd.extend(["--start-date", next_missing_date, "--end-date", target_trading_date])
    else:
        return [], "FEATURE_CLI_UNSUPPORTED"
    return [update_cmd, feature_cmd], "OK"


def audit_data_update_cli(write_report: bool = True, output_csv: str | Path = DEFAULT_CSV, output_md: str | Path = DEFAULT_MD) -> pd.DataFrame:
    rows: list[dict] = []
    for script in SCRIPTS:
        path = resolve_path(script)
        exists = path.exists()
        help_returncode = None
        stdout = ""
        stderr = ""
        if exists:
            result = _run_help(script)
            help_returncode = result.returncode
            stdout = result.stdout
            stderr = result.stderr
        help_text = f"{stdout}\n{stderr}"
        supports_as_of = _supports(help_text, "--as-of-date")
        supports_start = _supports(help_text, "--start-date")
        supports_end = _supports(help_text, "--end-date")
        supports_all = _supports(help_text, "--all-stocks")
        supports_provider_health = "provider_health" in help_text or "provider health" in help_text.lower()
        supports_data_quality = "data_quality" in help_text or "data quality" in help_text.lower()
        if not exists:
            status = "FAIL"
            recommendation = "脚本不存在，不能执行数据更新链路。"
        elif help_returncode != 0:
            status = "FAIL"
            recommendation = "--help 不可运行，先修复 CLI。"
        elif script == "scripts/update_market_data.py" and not (supports_as_of or (supports_start and supports_end)):
            status = "FAIL"
            recommendation = "update_market_data.py 必须支持 --as-of-date 或 --start-date/--end-date。"
        elif script == "scripts/update_market_data.py" and not supports_as_of and supports_start and supports_end:
            status = "WARN"
            recommendation = "update_market_data.py 不支持 --as-of-date；safe update 将采用 --start-date/--end-date 等价区间。"
        elif script == "scripts/build_features.py" and not (supports_as_of or (supports_start and supports_end)):
            status = "FAIL"
            recommendation = "build_features.py 必须支持 --as-of-date 或 --start-date/--end-date。"
        elif script == "scripts/build_features.py" and not supports_as_of and supports_start and supports_end:
            status = "WARN"
            recommendation = "build_features.py 不支持 --as-of-date；safe update 将采用 --start-date/--end-date 等价区间。"
        elif script == "scripts/build_features.py" and not (supports_start and supports_end):
            status = "WARN"
            recommendation = "build_features.py 只支持单日 --as-of-date；safe update 将采用单日构建。"
        else:
            status = "PASS"
            recommendation = "CLI 可用于 preflight 计划。"
        rows.append(
            {
                "script_path": script,
                "exists": exists,
                "help_returncode": help_returncode if help_returncode is not None else "",
                "supports_as_of_date": supports_as_of,
                "supports_start_date": supports_start,
                "supports_end_date": supports_end,
                "supports_all_stocks": supports_all,
                "supports_provider_health": supports_provider_health,
                "supports_data_quality": supports_data_quality,
                "detected_usage_summary": " ".join(stdout.splitlines()[:2])[:500],
                "status": status,
                "recommendation": recommendation,
            }
        )
    frame = pd.DataFrame(rows)
    if write_report:
        csv_path = resolve_path(output_csv)
        md_path = resolve_path(output_md)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
        overall = "FAIL" if (frame["status"] == "FAIL").any() else "WARN" if (frame["status"] == "WARN").any() else "PASS"
        lines = [
            "# data update CLI audit",
            "",
            f"- overall_status: {overall}",
            f"- fail_count: {int((frame['status'] == 'FAIL').sum())}",
            f"- warn_count: {int((frame['status'] == 'WARN').sum())}",
            "",
            "## checks",
            "",
        ]
        for row in frame.to_dict(orient="records"):
            lines.append(
                f"- {row['status']} | {row['script_path']} | as_of={row['supports_as_of_date']} | start/end={row['supports_start_date']}/{row['supports_end_date']} | {row['recommendation']}"
            )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return frame


def cli_status(frame: pd.DataFrame) -> str:
    if (frame["status"] == "FAIL").any():
        return "FAIL"
    if (frame["status"] == "WARN").any():
        return "WARN"
    return "PASS"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit data update script CLI surfaces without writing data.")
    parser.add_argument("--write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frame = audit_data_update_cli(write_report=args.write_report)
    return 1 if cli_status(frame) == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
