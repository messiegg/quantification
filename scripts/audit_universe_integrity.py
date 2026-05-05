#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.report_metadata import metadata_header, status_from_children, write_json
from src.utils.config import load_yaml, resolve_path


JSON_PATH = "reports/audit/universe_integrity.json"
MD_PATH = "reports/audit/universe_integrity.md"


def _safe_float(value: object) -> float | None:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return None
    if pd.isna(numeric):
        return None
    return numeric


def _date_value(payload: dict[str, Any]) -> str:
    return str(payload.get("as_of_date") or payload.get("effective_from") or payload.get("generated_at") or "")


def _hard_filter_thresholds(rules: dict[str, Any], bucket: str) -> dict[str, Any]:
    filters = rules.get("bucket_filters", {}) if isinstance(rules.get("bucket_filters"), dict) else {}
    base = filters.get("base", {}) if isinstance(filters.get("base"), dict) else {}
    bucket_cfg = filters.get(bucket, {}) if isinstance(filters.get(bucket), dict) else {}
    return {**base, **bucket_cfg}


def _check_required(item: dict[str, Any], required_fields: list[str]) -> list[str]:
    missing = []
    aliases = {
        "industry": ("industry", "industry_l1"),
        "market_cap_billion": ("market_cap_billion",),
        "avg_amount_60d_million": ("avg_amount_60d_million",),
        "pb": ("pb",),
        "stock_pb_q_blended": ("stock_pb_q_blended", "stock_q_blended"),
        "industry_pb_q_blended": ("industry_pb_q_blended", "industry_q_blended"),
    }
    for field in required_fields:
        names = aliases.get(field, (field,))
        if all(item.get(name) in {None, ""} or pd.isna(item.get(name)) for name in names):
            missing.append(field)
    return missing


def _filter_failures(item: dict[str, Any], rules: dict[str, Any]) -> list[str]:
    bucket = str(item.get("bucket") or "")
    thresholds = _hard_filter_thresholds(rules, bucket)
    failures: list[str] = []
    checks = [
        ("market_cap_billion", "market_cap_billion_min", ">="),
        ("avg_amount_60d_million", "avg_amount_60d_million_min", ">="),
        ("roe", "roe_min", ">="),
        ("dv_ttm", "dv_ttm_min", ">="),
        ("pe_ttm", "pe_ttm_max_when_primary_metric", "<="),
        ("pb", "pb_q_blended_max", "<="),
        ("pb", "pb_min_exclusive", ">"),
        ("latest_net_profit", "latest_net_profit_min_exclusive", ">"),
        ("debt_to_assets", "debt_to_assets_max", "<="),
    ]
    for field, threshold_name, op in checks:
        if threshold_name not in thresholds:
            continue
        threshold = _safe_float(thresholds.get(threshold_name))
        value = _safe_float(item.get(field))
        if threshold is None:
            continue
        if value is None:
            failures.append(f"missing_{field}")
            continue
        if op == ">=" and value < threshold:
            failures.append(f"{field}_below_{threshold_name}")
        elif op == ">" and value <= threshold:
            failures.append(f"{field}_not_above_{threshold_name}")
        elif op == "<=" and value > threshold:
            failures.append(f"{field}_above_{threshold_name}")
    if thresholds.get("require_industry") and not (item.get("industry_l1") or item.get("industry")):
        failures.append("missing_industry")
    return failures


def _override_config(rules: dict[str, Any]) -> dict[str, dict[str, Any]]:
    overrides = rules.get("manual_overrides") or rules.get("retained_overrides") or []
    if isinstance(overrides, dict):
        return {str(key): value for key, value in overrides.items() if isinstance(value, dict)}
    result: dict[str, dict[str, Any]] = {}
    if isinstance(overrides, list):
        for item in overrides:
            if isinstance(item, dict) and item.get("symbol"):
                result[str(item["symbol"])] = item
    return result


def _selected_reason(item: dict[str, Any]) -> str:
    return str(item.get("selected_reason") or item.get("selected_as") or item.get("change_tag") or "")


def build_universe_integrity_report(
    *,
    universe_file: str = "config/universe.yml",
    rules_file: str = "config/universe_rules_v2.yml",
    mode: str = "strict",
    write_report: bool = True,
    universe_payload: dict[str, Any] | None = None,
    rules_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    universe = universe_payload if universe_payload is not None else load_yaml(universe_file)
    rules = rules_payload if rules_payload is not None else load_yaml(rules_file)
    stocks = universe.get("stocks", []) or []
    target_size = int(rules.get("target_size", rules.get("target_universe_size", 0)) or 0)
    floor_size = int(rules.get("floor_size", rules.get("target_universe_floor", 0)) or 0)
    ceiling_size = int(rules.get("ceiling_size", rules.get("target_universe_ceiling", 10**9)) or 10**9)
    max_per_industry = int(rules.get("max_per_industry", rules.get("max_names_per_industry", 10**9)) or 10**9)
    base_filters = (rules.get("bucket_filters", {}) or {}).get("base", {}) or {}
    overrides = _override_config(rules)
    allow_research_underfill = bool(rules.get("allow_underfilled_universe_for_research", False))
    violations: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []
    constituents: list[dict[str, Any]] = []

    selected_count = len(stocks)
    if floor_size and selected_count < floor_size:
        severity = "WARN" if mode == "research" and allow_research_underfill else "FAIL"
        target = warnings if severity == "WARN" else violations
        target.append(
            {
                "code": "UNIVERSE_UNDER_FLOOR",
                "message": "selected universe count is below configured floor",
                "expected": f">={floor_size}",
                "actual": selected_count,
                "source": f"{universe_file};{rules_file}",
            }
        )
    if selected_count > ceiling_size:
        violations.append(
            {
                "code": "UNIVERSE_ABOVE_CEILING",
                "message": "selected universe count is above configured ceiling",
                "expected": f"<={ceiling_size}",
                "actual": selected_count,
                "source": f"{universe_file};{rules_file}",
            }
        )

    industry_counts = Counter(str(item.get("industry_l1") or item.get("industry") or "UNKNOWN") for item in stocks)
    for industry, count in sorted(industry_counts.items()):
        if count > max_per_industry:
            violations.append(
                {
                    "code": "INDUSTRY_CAP_EXCEEDED",
                    "message": "selected universe exceeds max_per_industry",
                    "expected": max_per_industry,
                    "actual": count,
                    "industry": industry,
                    "source": rules_file,
                }
            )

    required_fields = list(rules.get("core_required_fields") or base_filters.get("core_required_fields") or [])
    for item in stocks:
        symbol = str(item.get("symbol") or item.get("code") or "")
        retained = str(item.get("selected_as", "")).lower() == "retained"
        manual_override = str(item.get("selected_as", "")).lower() in {"manual_override", "override"} or symbol in overrides
        failed_filters = _filter_failures(item, rules)
        missing = _check_required(item, required_fields)
        override = overrides.get(symbol, {})
        override_has_basis = bool(override.get("reason") and (override.get("effective_date") or override.get("as_of_date")))
        if missing:
            violations.append(
                {
                    "code": "MISSING_KEY_FIELDS",
                    "symbol": symbol,
                    "message": "selected constituent misses required fields",
                    "fields": missing,
                    "source": universe_file,
                }
            )
        if failed_filters:
            if manual_override and override_has_basis:
                warnings.append(
                    {
                        "code": "HARD_FILTER_OVERRIDE_USED",
                        "symbol": symbol,
                        "message": "hard filter violation allowed by explicit override",
                        "failed_filters": failed_filters,
                        "override_reason": override.get("reason"),
                        "override_effective_date": override.get("effective_date") or override.get("as_of_date"),
                        "source": rules_file,
                    }
                )
            else:
                violations.append(
                    {
                        "code": "HARD_FILTER_VIOLATION",
                        "symbol": symbol,
                        "message": "selected constituent violates hard filters without explicit override basis",
                        "failed_filters": failed_filters,
                        "selected_as": item.get("selected_as"),
                        "source": universe_file,
                    }
                )
        if manual_override and not override_has_basis:
            violations.append(
                {
                    "code": "MANUAL_OVERRIDE_WITHOUT_BASIS",
                    "symbol": symbol,
                    "message": "manual override/retained override lacks reason and effective date",
                    "selected_as": item.get("selected_as"),
                    "source": rules_file,
                }
            )
        constituents.append(
            {
                "symbol": symbol,
                "code": symbol,
                "name": item.get("name"),
                "industry": item.get("industry_l1") or item.get("industry"),
                "bucket": item.get("bucket"),
                "market_cap_billion": item.get("market_cap_billion"),
                "pe": item.get("pe_ttm"),
                "pb": item.get("pb"),
                "dividend_yield": item.get("dv_ttm"),
                "selected_reason": _selected_reason(item),
                "retained": retained,
                "manual_override": manual_override,
                "override_reason": override.get("reason") if override else None,
                "override_effective_date": override.get("effective_date") or override.get("as_of_date") if override else None,
                "failed_filters": failed_filters,
                "missing_fields": missing,
                "data_source": universe_file,
                "data_path": universe_file,
                "data_asof": universe.get("as_of_date"),
                "effective_date": universe.get("effective_from"),
            }
        )

    status = status_from_children(["FAIL" if violations else "WARN" if warnings else "PASS"])
    payload = {
        **metadata_header(
            requested_date=str(universe.get("as_of_date", "")),
            target_trade_date=str(universe.get("as_of_date", "")),
            extra_config_paths=[universe_file, rules_file],
        ),
        "status": status,
        "checked_at": metadata_header()["generated_at"],
        "git_commit": metadata_header()["git_commit"],
        "universe_file": universe_file,
        "rules_file": rules_file,
        "active_date": _date_value(universe),
        "target_trade_date": str(universe.get("as_of_date", "")),
        "selected_count": selected_count,
        "target_size": target_size,
        "floor": floor_size,
        "ceiling": ceiling_size,
        "max_per_industry": max_per_industry,
        "market_cap_billion_min": base_filters.get("market_cap_billion_min"),
        "hard_filter_thresholds": rules.get("bucket_filters", {}),
        "retained_rules": {
            "retained_min_score": rules.get("retained_min_score"),
            "retained_industry_rank": rules.get("retained_industry_rank"),
            "retained_any_rank_score": rules.get("retained_any_rank_score"),
        },
        "violations": violations,
        "warnings": warnings,
        "constituents": constituents,
    }
    if write_report:
        write_json(JSON_PATH, payload)
        _write_md(payload, MD_PATH)
    return payload


def _write_md(payload: dict[str, Any], path_like: str | Path) -> None:
    path = resolve_path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# universe integrity audit",
        "",
        f"- status: {payload['status']}",
        f"- checked_at: {payload['checked_at']}",
        f"- git_commit: {payload['git_commit']}",
        f"- config_hash: {payload['config_hash']}",
        f"- universe_file: {payload['universe_file']}",
        f"- rules_file: {payload['rules_file']}",
        f"- active_date: {payload['active_date']}",
        f"- selected_count: {payload['selected_count']}",
        f"- target/floor/ceiling: {payload['target_size']} / {payload['floor']} / {payload['ceiling']}",
        f"- max_per_industry: {payload['max_per_industry']}",
        f"- market_cap_billion_min: {payload['market_cap_billion_min']}",
        "",
        "## FAIL",
        "",
    ]
    lines.extend(
        [
            f"- {item['code']}: {item.get('symbol', item.get('industry', ''))} {item['message']} actual={item.get('actual', item.get('failed_filters', item.get('fields', '')))}"
            for item in payload.get("violations", [])
        ]
        or ["- 无"]
    )
    lines.extend(["", "## WARN", ""])
    lines.extend(
        [
            f"- {item['code']}: {item.get('symbol', '')} {item['message']} actual={item.get('actual', item.get('failed_filters', ''))}"
            for item in payload.get("warnings", [])
        ]
        or ["- 无"]
    )
    lines.extend(["", "## Constituents", ""])
    for item in payload.get("constituents", []):
        failed = ",".join(item.get("failed_filters") or []) or "none"
        lines.append(
            f"- {item['symbol']} {item.get('name') or ''} | {item.get('industry') or ''} | {item.get('bucket') or ''} | market_cap_billion={item.get('market_cap_billion')} | selected_reason={item.get('selected_reason')} | failed_filters={failed}"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Audit active effective universe integrity.")
    parser.add_argument("--universe-file", default="config/universe.yml")
    parser.add_argument("--rules-file", default="config/universe_rules_v2.yml")
    parser.add_argument("--mode", choices=["strict", "research"], default="strict")
    parser.add_argument("--no-write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_universe_integrity_report(
        universe_file=args.universe_file,
        rules_file=args.rules_file,
        mode=args.mode,
        write_report=not args.no_write_report,
    )
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
