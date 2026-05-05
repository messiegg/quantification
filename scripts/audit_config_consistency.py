#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.report_metadata import ACTIVE_RUNTIME_CONFIG_PATHS, metadata_header, status_from_children, write_json
from src.utils.config import load_yaml, load_yaml_optional, resolve_path


JSON_PATH = "reports/audit/config_consistency.json"
MD_PATH = "reports/audit/config_consistency.md"


def _float_or_none(value: object) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    return numeric


def _nested(mapping: dict[str, Any], path: tuple[str, ...], default: object = None) -> object:
    current: object = mapping
    for key in path:
        if not isinstance(current, dict) or key not in current:
            return default
        current = current[key]
    return current


def _same_number(left: object, right: object, tolerance: float = 1e-12) -> bool:
    a = _float_or_none(left)
    b = _float_or_none(right)
    if a is None or b is None:
        return str(left) == str(right)
    return abs(a - b) <= tolerance


def _add_issue(issues: list[dict[str, Any]], severity: str, code: str, message: str, expected: object, actual: object, source: str) -> None:
    issues.append(
        {
            "severity": severity,
            "code": code,
            "message": message,
            "expected": expected,
            "actual": actual,
            "source": source,
        }
    )


def _active_values(
    strategy: dict[str, Any],
    account: dict[str, Any],
    universe_rules: dict[str, Any],
    data_sources: dict[str, Any],
) -> dict[str, Any]:
    execution = account.get("execution", {}) if isinstance(account.get("execution"), dict) else {}
    sizing = account.get("position_sizing", {}) if isinstance(account.get("position_sizing"), dict) else {}
    strategy_execution = strategy.get("execution", {}) if isinstance(strategy.get("execution"), dict) else {}
    market_regime = strategy.get("market_regime", {}) if isinstance(strategy.get("market_regime"), dict) else {}
    defaults = data_sources.get("defaults", {}) if isinstance(data_sources.get("defaults"), dict) else {}
    return {
        "active_strategy_config_path": "config/strategy_v2.yml",
        "active_account_config_path": "config/account.yml",
        "active_universe_rules_path": "config/universe_rules_v2.yml",
        "active_cost_model": "account.execution overrides strategy.execution defaults",
        "commission": execution.get("commission_rate", strategy_execution.get("fee_rate")),
        "stamp_tax": execution.get("stamp_duty_rate_sell", strategy_execution.get("stamp_tax_rate")),
        "slippage": execution.get("slippage_bps", strategy_execution.get("slippage_rate")),
        "min_trade_amount": sizing.get("min_trade_value"),
        "lot_size": execution.get("round_lot"),
        "max_single_stock_weight": sizing.get("max_single_stock_weight"),
        "max_positions": strategy_execution.get("max_positions"),
        "max_total_position": market_regime.get("max_total_position"),
        "industry_cap": universe_rules.get("max_per_industry", universe_rules.get("max_names_per_industry")),
        "universe_target": universe_rules.get("target_size", universe_rules.get("target_universe_size")),
        "universe_floor": universe_rules.get("floor_size", universe_rules.get("target_universe_floor")),
        "universe_ceiling": universe_rules.get("ceiling_size", universe_rules.get("target_universe_ceiling")),
        "strategy_version": strategy.get("profile") or strategy.get("strategy_profile") or strategy.get("strategy_name"),
        "benchmark": _nested(strategy, ("market_regime", "benchmark_index")),
        "data_provider": {
            "price_source_order": defaults.get("price_source_order"),
            "valuation_source_order": defaults.get("valuation_source_order"),
            "financial_source_order": defaults.get("financial_source_order"),
            "market_cap_source_order": defaults.get("market_cap_source_order"),
        },
    }


def _check_runtime_conflicts(strategy: dict[str, Any], account: dict[str, Any], universe_rules: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    pairs = [
        ("commission", _nested(account, ("execution", "commission_rate")), _nested(strategy, ("execution", "fee_rate"))),
        ("stamp_tax", _nested(account, ("execution", "stamp_duty_rate_sell")), _nested(strategy, ("execution", "stamp_tax_rate"))),
        ("slippage", _nested(account, ("execution", "slippage_bps")), None),
    ]
    for name, account_value, strategy_value in pairs:
        if strategy_value is None or account_value is None:
            continue
        if not _same_number(account_value, strategy_value):
            _add_issue(
                issues,
                "FAIL",
                f"RUNTIME_CONFLICT_{name.upper()}",
                f"{name} differs between active account and strategy configs",
                strategy_value,
                account_value,
                "config/account.yml;config/strategy_v2.yml",
            )
    aliases = [
        ("target_size", universe_rules.get("target_size"), universe_rules.get("target_universe_size")),
        ("floor_size", universe_rules.get("floor_size"), universe_rules.get("target_universe_floor")),
        ("ceiling_size", universe_rules.get("ceiling_size"), universe_rules.get("target_universe_ceiling")),
        ("max_per_industry", universe_rules.get("max_per_industry"), universe_rules.get("max_names_per_industry")),
    ]
    for name, left, right in aliases:
        if left is not None and right is not None and not _same_number(left, right):
            _add_issue(
                issues,
                "FAIL",
                f"RUNTIME_CONFLICT_{name.upper()}",
                f"{name} alias values differ inside active universe rules",
                right,
                left,
                "config/universe_rules_v2.yml",
            )


def _check_manifest_conflicts(active: dict[str, Any], issues: list[dict[str, Any]]) -> None:
    path = resolve_path("reports/backtest/release/combined_v2_rc_manifest.json")
    if not path.exists():
        _add_issue(issues, "WARN", "MANIFEST_MISSING", "release manifest is missing", "manifest exists", "missing", str(path))
        return
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        _add_issue(issues, "FAIL", "MANIFEST_INVALID_JSON", "release manifest cannot be parsed", "valid json", str(exc), str(path))
        return
    checks = [
        ("commission", "fee"),
        ("stamp_tax", "tax"),
        ("slippage", "slippage"),
        ("min_trade_amount", "min_trade_amount"),
        ("lot_size", "lot_size"),
        ("strategy_version", "profile"),
    ]
    for active_key, manifest_key in checks:
        manifest_value = manifest.get(manifest_key)
        if manifest_value is None:
            continue
        if not _same_number(active.get(active_key), manifest_value):
            _add_issue(
                issues,
                "FAIL",
                f"REPORT_HEADER_CONFLICT_{active_key.upper()}",
                f"release manifest {manifest_key} conflicts with active runtime config",
                active.get(active_key),
                manifest_value,
                "reports/backtest/release/combined_v2_rc_manifest.json",
            )


def _read_text(path_like: str | Path) -> str:
    path = resolve_path(path_like)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _check_readme(active: dict[str, Any], issues: list[dict[str, Any]], readme_text: str | None = None) -> None:
    text = readme_text if readme_text is not None else _read_text("README.md")
    if not text:
        return
    checks = [
        ("DOC_MISMATCH_STAMP_TAX", "stamp_tax", [r"stamp[_ ]?tax[^\n0-9]*(0\.\d+)", r"印花税[^\n0-9]*(0\.\d+)"]),
        ("DOC_MISMATCH_INDUSTRY_CAP", "industry_cap", [r"行业上限[^\n0-9]*([0-9]+)", r"每个行业最多[^\n0-9]*([0-9]+)\s*只"]),
        ("DOC_MISMATCH_UNIVERSE_TARGET", "universe_target", [r"target[_ ]?size[^\n0-9]*([0-9]+)", r"目标[^\n0-9]*([0-9]+)\s*只"]),
    ]
    for code, key, patterns in checks:
        for pattern in patterns:
            match = re.search(pattern, text, flags=re.IGNORECASE)
            if not match:
                continue
            documented = match.group(1)
            if not _same_number(documented, active.get(key)):
                _add_issue(
                    issues,
                    "WARN",
                    code,
                    f"README mentions {key} value that differs from runtime config",
                    active.get(key),
                    documented,
                    "README.md",
                )
            break
    forbidden = [
        "自动下单",
        "接券商",
    ]
    if all(phrase not in text for phrase in forbidden):
        _add_issue(
            issues,
            "WARN",
            "DOC_MISSING_MANUAL_ONLY_BOUNDARY",
            "README should explicitly state manual-only/no broker boundary",
            "manual-only boundary text",
            "missing",
            "README.md",
        )


def build_config_consistency_report(
    *,
    write_report: bool = True,
    readme_text: str | None = None,
    strategy: dict[str, Any] | None = None,
    account: dict[str, Any] | None = None,
    universe_rules: dict[str, Any] | None = None,
    data_sources: dict[str, Any] | None = None,
) -> dict[str, Any]:
    strategy_cfg = strategy if strategy is not None else load_yaml("config/strategy_v2.yml")
    account_cfg = account if account is not None else load_yaml_optional("config/account.yml")
    universe_cfg = universe_rules if universe_rules is not None else load_yaml("config/universe_rules_v2.yml")
    data_cfg = data_sources if data_sources is not None else load_yaml_optional("config/data_sources.yml")
    active = _active_values(strategy_cfg, account_cfg, universe_cfg, data_cfg)
    issues: list[dict[str, Any]] = []
    _check_runtime_conflicts(strategy_cfg, account_cfg, universe_cfg, issues)
    _check_manifest_conflicts(active, issues)
    _check_readme(active, issues, readme_text=readme_text)
    status = status_from_children(issue["severity"] for issue in issues)
    payload = {
        **metadata_header(extra_config_paths=ACTIVE_RUNTIME_CONFIG_PATHS),
        "status": status,
        "active_values": active,
        "violations": [issue for issue in issues if issue["severity"] == "FAIL"],
        "warnings": [issue for issue in issues if issue["severity"] == "WARN"],
    }
    if write_report:
        write_json(JSON_PATH, payload)
        _write_md(payload, MD_PATH)
    return payload


def _write_md(payload: dict[str, Any], path_like: str | Path) -> None:
    path = resolve_path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    active = payload["active_values"]
    lines = [
        "# 配置一致性审计",
        "",
        f"- status: {payload['status']}",
        f"- checked_at: {payload['generated_at']}",
        f"- git_commit: {payload['git_commit']}",
        f"- config_hash: {payload['config_hash']}",
        f"- active_strategy_config_path: {active['active_strategy_config_path']}",
        f"- active_account_config_path: {active['active_account_config_path']}",
        f"- active_universe_rules_path: {active['active_universe_rules_path']}",
        f"- active_cost_model: {active['active_cost_model']}",
        f"- commission: {active['commission']}",
        f"- stamp_tax: {active['stamp_tax']}",
        f"- slippage: {active['slippage']}",
        f"- min_trade_amount: {active['min_trade_amount']}",
        f"- lot_size: {active['lot_size']}",
        f"- max_single_stock_weight: {active['max_single_stock_weight']}",
        f"- max_positions: {active['max_positions']}",
        f"- industry_cap: {active['industry_cap']}",
        f"- universe target/floor/ceiling: {active['universe_target']} / {active['universe_floor']} / {active['universe_ceiling']}",
        f"- strategy_version: {active['strategy_version']}",
        f"- benchmark: {active['benchmark']}",
        "",
        "## FAIL",
        "",
    ]
    failures = payload.get("violations", [])
    lines.extend([f"- {item['code']}: {item['message']} expected={item['expected']} actual={item['actual']}" for item in failures] or ["- 无"])
    lines.extend(["", "## WARN", ""])
    warnings = payload.get("warnings", [])
    lines.extend([f"- {item['code']}: {item['message']} expected={item['expected']} actual={item['actual']}" for item in warnings] or ["- 无"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit active runtime config consistency.")
    parser.add_argument("--no-write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_config_consistency_report(write_report=not args.no_write_report)
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
