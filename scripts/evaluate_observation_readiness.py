#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.report_metadata import metadata_header, write_json
from src.utils.config import load_yaml, resolve_path


POLICY_PATH = "config/observation_readiness.yml"
OUT_JSON = "reports/observation/readiness_report.json"
OUT_MD = "reports/observation/readiness_report.md"


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = resolve_path(path_like)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_log(path_like: str | Path) -> pd.DataFrame:
    path = resolve_path(path_like)
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def evaluate_observation_readiness(
    *,
    policy_path: str = POLICY_PATH,
    write_report: bool = True,
) -> dict[str, Any]:
    policy = load_yaml(policy_path)
    log_path = str(policy.get("manual_review_log_path", "data/observation/manual_review_log.csv"))
    log = _read_log(log_path)
    manifest = _read_json("reports/backtest/release/combined_v2_rc_manifest.json")
    sensitivity_coverage = _read_json("reports/backtest/robustness/sensitivity_trigger_coverage.json")
    account = _read_json("reports/backtest/account_suitability_report.json") or _read_json("reports/backtest/account_constraints_report.json")
    evidence = _read_json("reports/observation/2026-05-04/evidence_chain.json")

    checks: list[dict[str, Any]] = []
    observation_days = int(log["target_trade_date"].nunique()) if not log.empty and "target_trade_date" in log else 0
    checks.append(
        {
            "check_id": "READY-OBS-DAYS",
            "status": "PASS" if observation_days >= int(policy["minimum_observation_trading_days"]) else "WARN",
            "expected": int(policy["minimum_observation_trading_days"]),
            "actual": observation_days,
        }
    )
    if policy.get("require_manual_review_log", True):
        checks.append(
            {
                "check_id": "READY-MANUAL-LOG",
                "status": "PASS" if not log.empty else "WARN",
                "expected": "manual review log exists",
                "actual": log_path if not log.empty else "missing",
            }
        )
    fail_count = 0 if str(manifest.get("status", "")).upper() != "FAIL" else 1
    checks.append(
        {
            "check_id": "READY-HARD-FAILS",
            "status": "PASS" if fail_count <= int(policy["maximum_hard_fail_count"]) else "FAIL",
            "expected": int(policy["maximum_hard_fail_count"]),
            "actual": fail_count,
        }
    )
    classifications = sensitivity_coverage.get("classifications", []) or []
    unknown_count = sum(1 for item in classifications if item.get("classification") == "UNKNOWN")
    not_wired_count = sum(1 for item in classifications if item.get("classification") == "PARAM_NOT_WIRED")
    checks.append(
        {
            "check_id": "READY-SENS-UNKNOWN",
            "status": "PASS" if unknown_count <= int(policy["maximum_unknown_sensitivity_params"]) else "WARN",
            "expected": int(policy["maximum_unknown_sensitivity_params"]),
            "actual": unknown_count,
        }
    )
    checks.append(
        {
            "check_id": "READY-SENS-NOT-WIRED",
            "status": "PASS" if not_wired_count <= int(policy["maximum_param_not_wired_count"]) else "FAIL",
            "expected": int(policy["maximum_param_not_wired_count"]),
            "actual": not_wired_count,
        }
    )
    base_case = account.get("base_case", account)
    ratio = base_case.get("executable_raw_buy_ratio")
    min_ratio = float(policy["minimum_executable_raw_buy_ratio"])
    checks.append(
        {
            "check_id": "READY-EXEC-RATIO",
            "status": "PASS" if ratio is not None and float(ratio) >= min_ratio else "WARN",
            "expected": min_ratio,
            "actual": ratio if ratio is not None else "missing",
        }
    )
    checks.append(
        {
            "check_id": "READY-EVIDENCE-CHAIN",
            "status": "PASS" if not policy.get("require_evidence_chain_every_day", True) or evidence else "FAIL",
            "expected": "evidence chain present",
            "actual": "present" if evidence else "missing",
        }
    )
    status_values = policy.get("status_values", {}) or {}
    if any(item["status"] == "FAIL" for item in checks):
        readiness = status_values.get("not_ready", "NOT_READY")
    elif any(item["status"] == "WARN" for item in checks):
        readiness = status_values.get("not_ready", "NOT_READY")
    else:
        readiness = status_values.get("ready", "READY")
    payload = {
        **metadata_header(extra_config_paths=[policy_path]),
        "status": readiness,
        "policy_path": policy_path,
        "manual_review_log_path": log_path,
        "observation_trading_days": observation_days,
        "checks": checks,
        "not_ready_reasons": [item for item in checks if item["status"] in {"WARN", "FAIL"}],
        "manual_review_required": True,
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
    }
    if write_report:
        write_json(OUT_JSON, payload)
        _write_md(payload)
    return payload


def _write_md(payload: dict[str, Any]) -> None:
    lines = [
        "# observation readiness report",
        "",
        f"- status: {payload['status']}",
        f"- observation_trading_days: {payload['observation_trading_days']}",
        "- manual_review_required: true",
        "- auto_trading_approved: false",
        "- broker_integration_enabled: false",
        "- llm_decision_allowed: false",
        "",
        "## checks",
        "",
    ]
    for item in payload["checks"]:
        lines.append(f"- {item['status']} | {item['check_id']} | expected={item['expected']} | actual={item['actual']}")
    lines.extend(["", "## not ready reasons", ""])
    lines.extend([f"- {item['check_id']}: actual={item['actual']}" for item in payload["not_ready_reasons"]] or ["- none"])
    resolve_path(OUT_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate whether observation logs satisfy readiness policy.")
    parser.add_argument("--policy", default=POLICY_PATH)
    parser.add_argument("--no-write-report", action="store_true")
    args = parser.parse_args()
    evaluate_observation_readiness(policy_path=args.policy, write_report=not args.no_write_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
