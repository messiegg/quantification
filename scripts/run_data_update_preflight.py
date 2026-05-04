#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_data_update_cli import audit_data_update_cli, cli_status
from scripts.check_data_freshness import build_data_freshness_report
from scripts.check_provider_readiness import check_provider_readiness
from scripts.check_release_sync_consistency import build_release_sync_consistency_check
from scripts.check_report_freshness import build_report_freshness_check
from scripts.update_market_data_safe import run_safe_update
from scripts.verify_combined_v2_rc import verify_release_candidate
from src.utils.config import resolve_path


OUTPUT_DIR = Path("reports/data_update/provider_preflight")
SUMMARY_JSON = OUTPUT_DIR / "data_update_preflight_summary.json"
SUMMARY_MD = OUTPUT_DIR / "data_update_preflight_summary.md"


def _status_from_frame(frame: pd.DataFrame) -> str:
    if frame.empty or "status" not in frame.columns:
        return "FAIL"
    values = set(frame["status"].astype(str).str.upper())
    if "FAIL" in values:
        return "FAIL"
    if "WARN" in values:
        return "WARN"
    return "PASS"


def _provider_requirements(provider: dict) -> list[str]:
    needs: list[str] = []
    if not provider.get("local_tdx_available"):
        needs.append("如需离线更新，配置可读的本地 TDX vipdoc 路径。")
    token_present = provider.get("token_present", {})
    if isinstance(token_present, dict):
        if not token_present.get("tushare"):
            needs.append("如需 Tushare，设置 TUSHARE_TOKEN 环境变量或 .env 条目。")
        if not token_present.get("jqdata_username") or not token_present.get("jqdata_password"):
            needs.append("如需 JQData，设置 JQDATA_USERNAME / JQDATA_PASSWORD。")
    if provider.get("provider_health_stale") or not provider.get("provider_health_date"):
        needs.append("重新运行 provider health 验证，确认数据源当前可用。")
    if provider.get("data_quality_stale") or not provider.get("data_quality_date"):
        needs.append("数据更新后重新运行 observation 数据质量检查。")
    if provider.get("status") == "FAIL":
        needs.append("修复 FAIL 项后再允许非 dry-run 更新。")
    return list(dict.fromkeys(needs))


def build_data_update_preflight_summary(
    as_of_date: str,
    target_trading_date: str | None = None,
    no_network: bool = False,
    write_report: bool = True,
) -> dict:
    stale_frame = build_report_freshness_check(write_report=True)
    rc_frame = verify_release_candidate(write_report=True)
    release_frame = build_release_sync_consistency_check(write_report=False)
    freshness = build_data_freshness_report(as_of_date, target_trading_date=target_trading_date, write_report=True)
    cli_frame = audit_data_update_cli(write_report=True)
    provider = check_provider_readiness(
        as_of_date,
        target_trading_date=target_trading_date,
        no_network=no_network,
        write_report=True,
    )
    safe = run_safe_update(
        as_of_date,
        target_trading_date=target_trading_date,
        preflight_only=True,
        no_network=no_network,
        write_report=True,
    )

    stale_status = _status_from_frame(stale_frame)
    rc_status = _status_from_frame(rc_frame)
    release_status = _status_from_frame(release_frame)
    cli_audit_status = cli_status(cli_frame)
    provider_status = str(provider.get("status", "FAIL"))
    safe_preflight_status = str(safe.get("preflight_status", "FAIL"))

    blocking_layers: list[str] = []
    if stale_status == "FAIL":
        blocking_layers.append("STALE_REPORT_CHECK_FAIL")
    if rc_status == "FAIL":
        blocking_layers.append("RC_VERIFY_FAIL")
    if release_status == "FAIL":
        blocking_layers.append("RELEASE_SYNC_CONSISTENCY_FAIL")
    if cli_audit_status == "FAIL":
        blocking_layers.append("DATA_UPDATE_CLI_AUDIT_FAIL")
    if provider_status == "FAIL":
        blocking_layers.append("PROVIDER_READINESS_FAIL")
    elif provider_status == "WARN":
        blocking_layers.append("PROVIDER_READINESS_WARN")
    if safe_preflight_status == "FAIL":
        blocking_layers.append(str(safe.get("skipped_reason") or "SAFE_UPDATE_PREFLIGHT_FAIL"))

    cli_can_plan = cli_audit_status in {"PASS", "WARN"} and bool(safe.get("commands_planned"))
    can_attempt = (
        stale_status != "FAIL"
        and rc_status != "FAIL"
        and release_status != "FAIL"
        and cli_can_plan
        and provider_status == "PASS"
        and safe_preflight_status in {"PASS", "WARN"}
    )
    next_command = (
        f"./.venv/bin/python scripts/update_market_data_safe.py --as-of-date {as_of_date} --execute --write-report"
        if can_attempt and not no_network
        else f"./.venv/bin/python scripts/run_data_update_preflight.py --as-of-date {as_of_date} --write-report"
    )
    if can_attempt and no_network:
        next_command = f"./.venv/bin/python scripts/update_market_data_safe.py --as-of-date {as_of_date} --execute --no-network --write-report"
    next_note = (
        "该命令只更新本地数据，不连接券商，不自动下单；执行前仍需人工确认。"
        if can_attempt
        else "当前只建议继续修复并重跑 preflight；该命令不写行情数据、不生成订单。"
    )

    summary = {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "as_of_date": as_of_date,
        "target_trading_date": freshness.get("target_trading_date", target_trading_date or ""),
        "no_network": no_network,
        "can_attempt_non_dry_run": can_attempt,
        "blocking_layers": list(dict.fromkeys(blocking_layers)),
        "next_safe_command": next_command,
        "next_safe_command_note": next_note,
        "statuses": {
            "stale_report_check": stale_status,
            "verify_combined_v2_rc": rc_status,
            "release_sync_consistency": release_status,
            "data_freshness_allowed_actions": freshness.get("allowed_actions", ""),
            "data_update_cli_audit": cli_audit_status,
            "provider_readiness": provider_status,
            "safe_update_preflight": safe_preflight_status,
        },
        "provider_requirements": _provider_requirements(provider),
        "freshness": freshness,
        "provider_readiness": {
            "local_tdx_available": provider.get("local_tdx_available", False),
            "network_providers_available": provider.get("network_providers_available", False),
            "token_present": provider.get("token_present", {}),
            "provider_health_date": provider.get("provider_health_date", ""),
            "provider_health_stale": provider.get("provider_health_stale", False),
            "data_quality_date": provider.get("data_quality_date", ""),
            "data_quality_stale": provider.get("data_quality_stale", False),
        },
        "safe_update_preflight": {
            "will_write_data": safe.get("will_write_data", False),
            "wrote_data": safe.get("wrote_data", False),
            "skipped_reason": safe.get("skipped_reason", ""),
            "commands_planned": safe.get("commands_planned", []),
        },
    }

    if write_report:
        output_dir = resolve_path(OUTPUT_DIR)
        output_dir.mkdir(parents=True, exist_ok=True)
        (output_dir / SUMMARY_JSON.name).write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines = [
            "# data update preflight summary",
            "",
            f"- as_of_date: {as_of_date}",
            f"- target_trading_date: {summary['target_trading_date'] or '无法解析'}",
            f"- can_attempt_non_dry_run: {str(can_attempt).lower()}",
            f"- blocking_layers: {'|'.join(summary['blocking_layers']) if summary['blocking_layers'] else 'NONE'}",
            f"- next_safe_command: `{next_command}`",
            f"- next_safe_command_note: {next_note}",
            "",
            "## statuses",
            "",
        ]
        for name, status in summary["statuses"].items():
            lines.append(f"- {name}: {status}")
        lines.extend(["", "## safe update preflight", ""])
        lines.append(f"- will_write_data: {str(safe.get('will_write_data', False)).lower()}")
        lines.append(f"- wrote_data: {str(safe.get('wrote_data', False)).lower()}")
        lines.append(f"- skipped_reason: {safe.get('skipped_reason', '') or '无'}")
        lines.extend(["", "## commands_planned", ""])
        lines.extend([f"- `{command}`" for command in safe.get("commands_planned", [])] or ["- 无"])
        lines.extend(["", "## 用户需要补充或确认", ""])
        lines.extend([f"- {item}" for item in summary["provider_requirements"]] or ["- 当前 preflight 未发现需要补充的 provider 配置。"])
        (output_dir / SUMMARY_MD.name).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the full market data update preflight without writing market data.")
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--target-trading-date", default="")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    build_data_update_preflight_summary(
        args.as_of_date,
        target_trading_date=args.target_trading_date or None,
        no_network=args.no_network,
        write_report=args.write_report,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
