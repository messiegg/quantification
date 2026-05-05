#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.report_metadata import metadata_header, write_json
from src.utils.config import resolve_path


METRICS_PATH = "reports/backtest/controls/control_baselines_metrics.csv"
OUT_JSON = "reports/backtest/controls/module_contribution_report.json"
OUT_MD = "reports/backtest/controls/module_contribution_report.md"

MODULES = {
    "high_dividend_supplement": ("v2_no_high_dividend_supplement", False),
    "trend_stop": ("v2_no_trend_stop", False),
    "market_state_filter": ("v2_no_market_state_filter", False),
    "industry_cap": ("v2_no_industry_cap", False),
    "account_constraints": ("v2_relaxed_account_constraints_research_only", True),
}


def _read_metrics(path_like: str | Path = METRICS_PATH) -> pd.DataFrame:
    path = resolve_path(path_like)
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _float(row: dict[str, Any], key: str) -> float | None:
    value = pd.to_numeric(row.get(key), errors="coerce")
    return None if pd.isna(value) else float(value)


def _delta(combined: dict[str, Any], ablation: dict[str, Any], key: str) -> float | None:
    left = _float(combined, key)
    right = _float(ablation, key)
    return None if left is None or right is None else left - right


def _classify(item: dict[str, Any]) -> str:
    annual = item.get("annual_return_delta")
    drawdown = item.get("max_drawdown_delta")
    sharpe = item.get("sharpe_delta")
    calmar = item.get("calmar_delta")
    if annual is None or drawdown is None or sharpe is None:
        return "INCONCLUSIVE"
    risk_improvement = drawdown > 0.01 or (calmar is not None and calmar > 0.1)
    risk_worse = drawdown < -0.005
    if annual > 0 and not risk_worse and sharpe >= 0:
        return "RETURN_ENHANCER"
    if annual < 0 and risk_improvement:
        return "RISK_REDUCER"
    if annual < 0 and drawdown > 0:
        return "COSTLY_RISK_REDUCER"
    if annual < 0 and not risk_improvement:
        return "POSSIBLE_DRAG"
    return "INCONCLUSIVE"


def build_module_contribution_report(write_report: bool = True) -> dict[str, Any]:
    metrics = _read_metrics()
    violations: list[dict[str, Any]] = []
    if metrics.empty or "control_id" not in metrics:
        payload = {
            **metadata_header(),
            "status": "FAIL",
            "violations": [{"code": "CONTROL_METRICS_MISSING", "path": METRICS_PATH}],
            "modules": [],
        }
        if write_report:
            write_json(OUT_JSON, payload)
            _write_md(payload)
        return payload
    by_id = {str(row["control_id"]): row for row in metrics.to_dict(orient="records")}
    combined = by_id.get("combined_v2_next_bar")
    if combined is None:
        violations.append({"code": "COMBINED_V2_METRICS_MISSING"})
    rows: list[dict[str, Any]] = []
    for module, (control_id, research_only) in MODULES.items():
        ablation = by_id.get(control_id)
        if combined is None or ablation is None:
            violations.append({"code": "MODULE_ABLATION_MISSING", "module": module, "control_id": control_id})
            continue
        item = {
            "module": module,
            "ablation_control_id": control_id,
            "research_only": research_only,
            "annual_return_delta": _delta(combined, ablation, "annual_return"),
            "cumulative_return_delta": _delta(combined, ablation, "cumulative_return"),
            "max_drawdown_delta": _delta(combined, ablation, "max_drawdown"),
            "sharpe_delta": _delta(combined, ablation, "sharpe"),
            "calmar_delta": _delta(combined, ablation, "calmar"),
            "turnover_delta": _delta(combined, ablation, "turnover"),
            "avg_exposure_delta": _delta(combined, ablation, "avg_daily_exposure"),
            "max_exposure_delta": _delta(combined, ablation, "max_daily_exposure"),
            "trade_count_delta": _delta(combined, ablation, "total_trades"),
            "worst_month_delta": None,
            "worst_20d_return_delta": None,
            "benchmark_excess_delta": _delta(combined, ablation, "excess_annual_return"),
        }
        item["classification"] = _classify(item)
        item["human_review_required"] = item["classification"] in {"POSSIBLE_DRAG", "INCONCLUSIVE"}
        rows.append(item)
    warning_classes = {"POSSIBLE_DRAG", "INCONCLUSIVE", "COSTLY_RISK_REDUCER"}
    warnings = [
        {"code": "MODULE_REQUIRES_HUMAN_REVIEW", "module": row["module"], "classification": row["classification"]}
        for row in rows
        if row["classification"] in warning_classes
    ]
    status = "FAIL" if violations else "WARN" if warnings else "PASS"
    payload = {
        **metadata_header(),
        "status": status,
        "source_metrics_path": METRICS_PATH,
        "delta_definition": "combined_v2_enabled_minus_ablation_disabled",
        "modules": rows,
        "warnings": warnings,
        "violations": violations,
    }
    if write_report:
        write_json(OUT_JSON, payload)
        _write_md(payload)
    return payload


def _pct(value: object) -> str:
    if value is None:
        return "missing"
    return f"{float(value) * 100:.2f}%"


def _write_md(payload: dict[str, Any]) -> None:
    lines = [
        "# module contribution report",
        "",
        f"- status: {payload['status']}",
        "- delta_definition: combined_v2_enabled_minus_ablation_disabled",
        "- 模块贡献报告只解释风险收益权衡，不自动删除或修改任何模块。",
        "",
        "## modules",
        "",
    ]
    for row in payload.get("modules", []):
        lines.append(
            f"- {row['module']}: classification={row['classification']} research_only={str(row['research_only']).lower()} "
            f"annual_delta={_pct(row['annual_return_delta'])} max_drawdown_delta={_pct(row['max_drawdown_delta'])} "
            f"sharpe_delta={row.get('sharpe_delta')} human_review_required={str(row['human_review_required']).lower()}"
        )
    lines.extend(["", "## warnings", ""])
    lines.extend([f"- {item['code']}: {item}" for item in payload.get("warnings", [])] or ["- none"])
    lines.extend(["", "## violations", ""])
    lines.extend([f"- {item['code']}: {item}" for item in payload.get("violations", [])] or ["- none"])
    resolve_path(OUT_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Classify module contribution from control ablations.")
    parser.add_argument("--no-write-report", action="store_true")
    args = parser.parse_args()
    payload = build_module_contribution_report(write_report=not args.no_write_report)
    return 1 if payload["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
