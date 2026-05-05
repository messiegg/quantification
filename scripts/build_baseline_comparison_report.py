#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_common import ensure_parent, pct
from scripts.report_metadata import metadata_header, write_json
from src.utils.config import load_yaml_optional, resolve_path


METRICS_PATH = "reports/backtest/controls/control_baselines_metrics.csv"
OUT_JSON = "reports/backtest/controls/baseline_comparison.json"
OUT_MD = "reports/backtest/controls/baseline_comparison.md"

LABEL_MAP = {
    "baseline_combined_next_bar": "base_dianjinshu_like",
    "combined_v2_next_bar": "combined_v2",
    "v2_no_high_dividend_supplement": "no_high_dividend_supplement",
    "v2_no_trend_stop": "no_trend_stop",
    "v2_no_market_state_filter": "no_market_state_filter",
    "v2_no_industry_cap": "no_industry_cap",
    "v2_relaxed_account_constraints_research_only": "relaxed_account_constraints_research_only",
}


def _safe_float(row: dict[str, Any], key: str) -> float | None:
    value = pd.to_numeric(row.get(key), errors="coerce")
    return None if pd.isna(value) else float(value)


def build_report() -> dict[str, Any]:
    metrics_path = resolve_path(METRICS_PATH)
    violations: list[dict[str, Any]] = []
    if not metrics_path.exists():
        payload = {
            **metadata_header(extra_config_paths=["config/baselines/dianjinshu_like.yml"]),
            "status": "FAIL",
            "baseline_source": "documented_dianjinshu_like_baseline",
            "strict_external_original_reproduction": False,
            "violations": [{"code": "BASELINE_METRICS_MISSING", "path": METRICS_PATH}],
            "missing_required_baseline_params": [],
            "missing_comparisons": sorted(LABEL_MAP.values()),
            "comparisons": [],
        }
        return payload

    metrics = pd.read_csv(metrics_path)
    by_id = {str(row.get("control_id")): row for row in metrics.to_dict(orient="records")}
    combined = by_id.get("combined_v2_next_bar", {})
    combined_annual = _safe_float(combined, "annual_return")
    comparison_rows = []
    for control_id, label in LABEL_MAP.items():
        row = by_id.get(control_id)
        if row is None:
            violations.append({"code": "BASELINE_COMPARISON_MISSING", "comparison_id": label, "source_control_id": control_id})
            continue
        comparison = dict(row)
        comparison["comparison_id"] = label
        comparison["research_only"] = label in {
            "no_market_state_filter",
            "no_industry_cap",
            "relaxed_account_constraints_research_only",
        }
        comparison["baseline_note"] = (
            "仓库配置中定义的点金术风格基线，不是对外部作者原文的严格复刻。"
            if label == "base_dianjinshu_like"
            else ""
        )
        annual = _safe_float(comparison, "annual_return")
        comparison["module_flag"] = (
            "MODULE_MAY_BE_DRAG"
            if label.startswith("no_") and annual is not None and combined_annual is not None and annual > combined_annual
            else ""
        )
        comparison_rows.append(comparison)

    baseline_cfg = load_yaml_optional("config/baselines/dianjinshu_like.yml")
    missing_required = [
        key
        for key, value in (baseline_cfg.get("required_params", {}) or {}).items()
        if value is None and key not in {"market_cap_rank"}
    ]
    for key in missing_required:
        violations.append({"code": "MISSING_REQUIRED_BASELINE_PARAM", "param": key})
    module_warn = any(row.get("module_flag") for row in comparison_rows)
    status = "FAIL" if violations else "WARN" if module_warn else "PASS"
    return {
        **metadata_header(extra_config_paths=["config/baselines/dianjinshu_like.yml"]),
        "status": status,
        "baseline_source": "documented_dianjinshu_like_baseline",
        "strict_external_original_reproduction": False,
        "source_metrics_path": str(metrics_path),
        "violations": violations,
        "missing_required_baseline_params": missing_required,
        "missing_comparisons": [item["comparison_id"] for item in violations if item["code"] == "BASELINE_COMPARISON_MISSING"],
        "comparisons": comparison_rows,
    }


def write_report(payload: dict[str, Any]) -> None:
    write_json(OUT_JSON, payload)
    lines = [
        "# baseline comparison",
        "",
        f"- status: {payload['status']}",
        "- base_dianjinshu_like: 仓库配置中定义的点金术风格基线，不是对外部作者原文的严格复刻。",
        "- combined_v2: 当前主研究候选。",
        "- no_* 和 relaxed_account_constraints 仅用于解释模块贡献，不自动修改主策略。",
        "",
    ]
    if payload.get("violations"):
        lines.extend(["## violations", ""])
        for item in payload["violations"]:
            lines.append(f"- {item.get('code')}: {item}")
        lines.append("")
    lines.extend(["## metrics", ""])
    for row in payload.get("comparisons", []):
        flag = f" | {row['module_flag']}" if row.get("module_flag") else ""
        raw = row.get("raw_signal_count")
        executable = row.get("executable_signal_count")
        lines.append(
            f"- {row['comparison_id']}: 年化 {pct(row.get('annual_return', 0.0))}，累计 {pct(row.get('cumulative_return', 0.0))}，回撤 {pct(row.get('max_drawdown', 0.0))}，Sharpe {float(row.get('sharpe', 0.0)):.2f}，Calmar {float(row.get('calmar', 0.0)):.2f}，turnover {float(row.get('turnover', 0.0)):.2f}，平均仓位 {pct(row.get('avg_daily_exposure', 0.0))}，成交 {int(row.get('total_trades', 0))}，raw/executable {raw} / {executable}，超额 {pct(row.get('excess_annual_return', 0.0))}{flag}"
        )
    ensure_parent(OUT_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    payload = build_report()
    write_report(payload)
    return 1 if payload["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
