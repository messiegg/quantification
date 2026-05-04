#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_data_freshness import build_data_freshness_report, resolve_target_trading_date, trading_dates_between
from scripts.check_data_quality_for_observation import build_data_quality_observation_report
from src.utils.config import load_yaml_optional, resolve_path


UPDATE_TYPES = [
    "daily行情",
    "benchmark",
    "features",
    "valuation quantiles",
    "industry valuation",
    "universe history check",
    "provider health",
    "data quality",
]


def _parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def build_update_plan(as_of_date: str, target_trading_date: str | None = None) -> dict:
    cfg = load_yaml_optional("config/observation.yml")
    obs_cfg = cfg.get("observation", {}) if isinstance(cfg, dict) else {}
    target_info = resolve_target_trading_date(
        as_of_date,
        market=str(obs_cfg.get("calendar_market", "A_SHARE")),
        observation_config=obs_cfg,
        target_trading_date=target_trading_date,
    )
    freshness = build_data_freshness_report(as_of_date, target_trading_date=target_trading_date, write_report=False)
    gap_dates = trading_dates_between(
        freshness.get("data_max_date"),
        target_info.get("target_trading_date"),
        market=str(obs_cfg.get("calendar_market", "A_SHARE")),
        observation_config=obs_cfg,
    )
    tdx_dirs = [str(item) for item in load_yaml_optional("config/data_sources.yml").get("tdx", {}).get("local_dirs", []) or []]
    local_tdx_dirs = [path for path in tdx_dirs if resolve_path(path).exists()]
    return {
        "as_of_date": as_of_date,
        **target_info,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "current_data_max_date": freshness.get("data_max_date", ""),
        "current_feature_max_date": freshness.get("feature_max_date", ""),
        "current_benchmark_max_date": freshness.get("benchmark_max_date", ""),
        "gap_trading_dates": gap_dates,
        "update_types": UPDATE_TYPES,
        "dry_run_writes_data": False,
        "local_tdx_data_source_available": bool(local_tdx_dirs),
        "network_providers_configured": True,
        "notes": [
            "dry-run 只生成计划，不写行情、特征、账本或订单文件。",
            "非 dry-run 只编排现有数据脚本，不新增抓取器，不生成 observation report。",
            "大体量 parquet、缓存、真实 paper ledger 不应提交到 GitHub。",
        ],
    }


def _write_plan_reports(plan: dict, base: Path) -> None:
    _write_json(base / "market_data_update_plan.json", plan)
    lines = [
        "# market data safe update plan",
        "",
        f"- as_of_date: {plan['as_of_date']}",
        f"- requested_as_of_is_trading_day: {str(plan['requested_as_of_is_trading_day']).lower()}",
        f"- target_trading_date: {plan['target_trading_date'] or '无法解析'}",
        f"- calendar_source: {plan['calendar_source']}",
        f"- current_data_max_date: {plan['current_data_max_date']}",
        f"- current_feature_max_date: {plan['current_feature_max_date']}",
        f"- current_benchmark_max_date: {plan['current_benchmark_max_date']}",
        f"- dry_run_writes_data: {str(plan['dry_run_writes_data']).lower()}",
        "",
        "## 需要补齐的交易日",
        "",
    ]
    lines.extend([f"- {date}" for date in plan["gap_trading_dates"]] or ["- 无"])
    lines.extend(["", "## 计划更新的数据类型", ""])
    lines.extend([f"- {item}" for item in plan["update_types"]])
    lines.extend(["", "## 说明", ""])
    lines.extend([f"- {item}" for item in plan["notes"]])
    (base / "market_data_update_plan.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _run_command(args: list[str]) -> dict:
    result = subprocess.run(args, cwd=ROOT, text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    return {
        "command": " ".join(args),
        "returncode": result.returncode,
        "stdout_tail": result.stdout[-4000:],
        "stderr_tail": result.stderr[-4000:],
    }


def run_safe_update(
    as_of_date: str,
    target_trading_date: str | None = None,
    dry_run: bool = False,
    write_report: bool = False,
    skip_provider_health: bool = False,
    skip_quality_check: bool = False,
) -> dict:
    plan = build_update_plan(as_of_date, target_trading_date)
    base = resolve_path(Path("reports/data_update") / as_of_date)
    if write_report:
        _write_plan_reports(plan, base)
    if dry_run:
        return {"status": "DRY_RUN", "plan": plan, "wrote_data": False}
    target = plan.get("target_trading_date")
    if not target:
        result = {"status": "FAIL", "failure_reason": "TARGET_TRADING_DATE_UNRESOLVED", "plan": plan, "wrote_data": False}
    else:
        commands = [
            [sys.executable, "scripts/update_market_data.py", "--as-of-date", str(target), "--all-stocks"],
            [sys.executable, "scripts/build_features.py", "--as-of-date", str(target)],
        ]
        executions = [_run_command(command) for command in commands]
        failed = [item for item in executions if item["returncode"] != 0]
        freshness = build_data_freshness_report(as_of_date, target_trading_date=target, write_report=False)
        quality = {} if skip_quality_check else build_data_quality_observation_report(as_of_date, target_trading_date=target, write_report=False)
        status = "FAIL" if failed or freshness.get("allowed_actions") != "observation_report_allowed" or quality.get("status") == "FAIL" else "PASS"
        result = {
            "status": status,
            "plan": plan,
            "commands": executions,
            "wrote_data": True,
            "skip_provider_health": skip_provider_health,
            "skip_quality_check": skip_quality_check,
            "freshness_after_update": freshness,
            "quality_after_update": quality,
            "failure_reason": ";".join(item["command"] for item in failed) if failed else "",
        }
    if write_report:
        _write_json(base / "market_data_update_result.json", result)
        lines = [
            "# market data safe update result",
            "",
            f"- status: {result['status']}",
            f"- as_of_date: {as_of_date}",
            f"- target_trading_date: {plan.get('target_trading_date') or '无法解析'}",
            f"- wrote_data: {str(result.get('wrote_data', False)).lower()}",
            f"- failure_reason: {result.get('failure_reason', '') or '无'}",
        ]
        (base / "market_data_update_result.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return result


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Safely update local market data to the observation target trading date.")
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--target-trading-date", default="")
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--write-report", action="store_true")
    parser.add_argument("--skip-provider-health", default="false")
    parser.add_argument("--skip-quality-check", default="false")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    result = run_safe_update(
        args.as_of_date,
        target_trading_date=args.target_trading_date or None,
        dry_run=args.dry_run,
        write_report=args.write_report,
        skip_provider_health=_parse_bool(args.skip_provider_health),
        skip_quality_check=_parse_bool(args.skip_quality_check),
    )
    return 1 if result["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
