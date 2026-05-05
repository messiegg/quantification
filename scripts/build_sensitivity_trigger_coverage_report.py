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
from src.utils.config import resolve_path


OUT_JSON = "reports/backtest/robustness/sensitivity_trigger_coverage.json"
OUT_MD = "reports/backtest/robustness/sensitivity_trigger_coverage.md"
SENSITIVITY_JSON = "reports/backtest/robustness/sensitivity_report.json"
SENSITIVITY_CSV = "reports/backtest/robustness/sensitivity_metrics.csv"

TOKEN_MAP = {
    "universe_size": ["target_size", "floor_size", "ceiling_size", "target_universe_size"],
    "defensive_valuation_threshold": ["defensive_dividend", "stock_q_blended_max", "industry_q_blended_max"],
    "cyclical_pb_threshold": ["cyclical_rotation", "stock_q_blended_max", "industry_q_blended_max"],
    "grid_step": ["grid_execution", "atr_multiplier", "min_step", "max_step"],
}


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = resolve_path(path_like)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path_like: str | Path) -> pd.DataFrame:
    path = resolve_path(path_like)
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _code_read_locations(variant_group: str) -> list[dict[str, Any]]:
    tokens = TOKEN_MAP.get(variant_group, [variant_group])
    roots = [resolve_path("src"), resolve_path("scripts"), resolve_path("config")]
    locations: list[dict[str, Any]] = []
    for root in roots:
        for path in root.rglob("*"):
            if path.is_dir() or path.suffix not in {".py", ".yml", ".yaml"}:
                continue
            try:
                rel = str(path.relative_to(ROOT))
            except ValueError:
                rel = str(path)
            if rel.startswith("reports/"):
                continue
            try:
                lines = path.read_text(encoding="utf-8").splitlines()
            except UnicodeDecodeError:
                continue
            for line_no, line in enumerate(lines, start=1):
                if all(token in line for token in tokens[:2]) or any(token in line for token in tokens):
                    locations.append({"path": rel, "line": line_no, "text": line.strip()[:180]})
                    break
            if len(locations) >= 20:
                return locations
    return locations


def _param_values(row: dict[str, Any]) -> tuple[Any, Any]:
    changed = str(row.get("changed_parameter", ""))
    if "=" in changed:
        return "configured_base", changed
    return "configured_base", changed or None


def _classification(row: dict[str, Any], code_locations: list[dict[str, Any]], mode: str) -> str:
    binding = str(row.get("parameter_binding_status", "")).upper()
    reason = str(row.get("non_binding_reason", "")).upper()
    if binding == "FAIL" and reason == "PARAM_NOT_WIRED":
        return "PARAM_NOT_WIRED"
    if binding == "ERROR":
        return "UNKNOWN"
    if binding == "NON_BINDING":
        if not code_locations:
            return "PARAM_NOT_WIRED"
        if reason in {"NO_SIGNAL_COVERAGE", "BLOCKED_BY_ACCOUNT_CONSTRAINT", "DOMINATED_BY_HIGHER_PRIORITY_RULE"}:
            return reason
        if mode == "ci" and int(row.get("changed_action_days_count", 0) or 0) == 0:
            return "CI_WINDOW_TOO_SHORT"
        return "UNKNOWN"
    return "BOUND" if binding == "BINDING" else binding or "UNKNOWN"


def build_sensitivity_trigger_coverage_report(
    *,
    sensitivity_json: str = SENSITIVITY_JSON,
    sensitivity_csv: str = SENSITIVITY_CSV,
    write_report: bool = True,
) -> dict[str, Any]:
    sensitivity = _read_json(sensitivity_json)
    metrics = _read_csv(sensitivity_csv)
    rows = metrics.to_dict(orient="records") if not metrics.empty else sensitivity.get("variants", [])
    mode = str(sensitivity.get("mode", "") or "unknown")
    funnel = _read_csv("reports/backtest/combined_v2_signal_funnel.csv")
    total_window_days = 0
    if not funnel.empty and "date" in funnel:
        dates = pd.to_datetime(funnel["date"], errors="coerce")
        start = pd.to_datetime(sensitivity.get("start_date"), errors="coerce")
        end = pd.to_datetime(sensitivity.get("end_date"), errors="coerce")
        mask = dates.notna()
        if not pd.isna(start):
            mask &= dates >= start
        if not pd.isna(end):
            mask &= dates <= end
        total_window_days = int(dates[mask].dt.strftime("%Y-%m-%d").nunique())
    base = next((row for row in rows if row.get("variant_id") == "current_v2"), {})
    items: list[dict[str, Any]] = []
    for row in rows:
        if row.get("variant_id") == "current_v2":
            continue
        binding = str(row.get("parameter_binding_status", "")).upper()
        if binding not in {"NON_BINDING", "FAIL", "ERROR"}:
            continue
        group = str(row.get("variant_group", ""))
        locations = _code_read_locations(group)
        base_value, variant_value = _param_values(row)
        classification = _classification(row, locations, mode)
        trigger_base = int((base.get("raw_buy_signal_count") or 0) + (base.get("raw_sell_signal_count") or 0))
        trigger_variant = int((row.get("raw_buy_signal_count") or 0) + (row.get("raw_sell_signal_count") or 0))
        items.append(
            {
                "param_path": group,
                "variant_id": row.get("variant_id"),
                "base_value": base_value,
                "variant_value": variant_value,
                "variant_config_hash": row.get("variant_config_hash"),
                "code_read_locations": locations,
                "rule_name": group,
                "trigger_condition": row.get("changed_parameter"),
                "trigger_count_base": trigger_base,
                "trigger_count_variant": trigger_variant,
                "blocked_by_account_constraints_count": int(row.get("blocked_signal_count") or 0),
                "dominated_by_higher_priority_rule_count": 0,
                "no_signal_coverage_days": total_window_days if int(row.get("changed_action_days_count") or 0) == 0 else 0,
                "action_path_changed": int(row.get("changed_action_days_count") or 0) > 0,
                "position_path_changed": int(row.get("changed_position_days_count") or 0) > 0,
                "classification": classification,
                "parameter_binding_status": binding,
                "non_binding_reason": row.get("non_binding_reason"),
            }
        )
    classifications = {item["classification"] for item in items}
    violations = []
    warnings = []
    if "PARAM_NOT_WIRED" in classifications:
        violations.append({"code": "PARAM_NOT_WIRED", "params": [item["param_path"] for item in items if item["classification"] == "PARAM_NOT_WIRED"]})
    if "UNKNOWN" in classifications:
        warnings.append({"code": "UNKNOWN_NON_BINDING_CLASSIFICATION", "params": [item["param_path"] for item in items if item["classification"] == "UNKNOWN"]})
    if any(item["classification"] in {"NO_SIGNAL_COVERAGE", "CI_WINDOW_TOO_SHORT", "BLOCKED_BY_ACCOUNT_CONSTRAINT"} for item in items):
        warnings.append({"code": "NON_BINDING_PARAMETERS_REQUIRE_OBSERVATION", "count": len(items)})
    status = "FAIL" if violations else "WARN" if warnings else "PASS"
    payload = {
        **metadata_header(),
        "status": status,
        "mode": mode,
        "source_sensitivity_report": sensitivity_json,
        "non_binding_parameter_count": len(items),
        "classifications": items,
        "warnings": warnings,
        "violations": violations,
        "coverage_limitations": [
            "CI mode uses a bounded date window and does not prove behavior in all regimes.",
            "Rule trigger counts use exported sensitivity diagnostics; rule-internal borderline counts are unavailable unless the engine exports them.",
        ],
    }
    if write_report:
        write_json(OUT_JSON, payload)
        _write_md(payload)
    return payload


def _write_md(payload: dict[str, Any]) -> None:
    lines = [
        "# sensitivity trigger coverage",
        "",
        f"- status: {payload['status']}",
        f"- mode: {payload['mode']}",
        f"- non_binding_parameter_count: {payload['non_binding_parameter_count']}",
        "",
        "## classifications",
        "",
    ]
    for item in payload["classifications"]:
        lines.append(
            f"- {item['param_path']} ({item['variant_id']}): classification={item['classification']} "
            f"binding={item['parameter_binding_status']} reason={item.get('non_binding_reason')} "
            f"trigger_base={item['trigger_count_base']} trigger_variant={item['trigger_count_variant']}"
        )
    lines.extend(["", "## warnings", ""])
    lines.extend([f"- {item['code']}: {item}" for item in payload["warnings"]] or ["- none"])
    lines.extend(["", "## violations", ""])
    lines.extend([f"- {item['code']}: {item}" for item in payload["violations"]] or ["- none"])
    resolve_path(OUT_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify NON_BINDING sensitivity parameters by trigger coverage.")
    parser.add_argument("--no-write-report", action="store_true")
    args = parser.parse_args()
    payload = build_sensitivity_trigger_coverage_report(write_report=not args.no_write_report)
    return 1 if payload["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
