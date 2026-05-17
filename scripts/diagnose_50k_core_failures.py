#!/usr/bin/env python3
from __future__ import annotations

import argparse
import ast
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_common import DEFAULT_END_DATE, DEFAULT_START_DATE, load_feature_window
from scripts.run_50k_core_experiments import DEFAULT_EVALUATION, _pct, _safe_float, _safe_int
from src.utils.config import resolve_path


INPUT_DIR = "reports/backtest/50k_core"
OUT_DIR = "reports/backtest/50k_core/diagnostics"

HARD_CONDITIONS = [
    "annual_return",
    "sharpe",
    "max_drawdown",
    "total_trades",
    "executable_account_actionable_ratio",
    "avg_cash_ratio_in_risk_on",
    "largest_single_stock_pnl_contribution",
    "largest_industry_pnl_contribution",
    "realized_pnl",
    "cyclical_rotation_pnl",
    "neighborhood_robustness",
]

REQUIRED_DIAGNOSTIC_OUTPUTS = [
    "failure_condition_summary.csv",
    "failure_condition_summary.md",
    "hard_condition_pareto.csv",
    "top_variant_deep_dive.md",
    "risk_on_cash_drag_report.csv",
    "risk_on_cash_drag_report.md",
    "trade_density_report.csv",
    "trade_density_report.md",
    "drawdown_source_report.csv",
    "drawdown_source_report.md",
    "replacement_effectiveness_report.csv",
    "replacement_effectiveness_report.md",
    "bucket_effectiveness_report.csv",
    "bucket_effectiveness_report.md",
    "exit_rule_effectiveness_report.csv",
    "module_disable_interpretation.md",
    "diagnosis_recommendations.md",
]


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_yaml(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def _parse_mapping(value: object) -> dict[str, float]:
    if isinstance(value, dict):
        return {str(k): _safe_float(v) for k, v in value.items()}
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return {}
    text = str(value)
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        try:
            parsed = ast.literal_eval(text)
        except (ValueError, SyntaxError):
            return {}
    if not isinstance(parsed, dict):
        return {}
    return {str(k): _safe_float(v) for k, v in parsed.items()}


def _top_variant(metrics: pd.DataFrame) -> dict[str, Any]:
    if metrics.empty:
        return {}
    if "selection_score" in metrics.columns:
        frame = metrics.sort_values(["selection_score", "annual_return", "max_drawdown"], ascending=[False, False, False])
    else:
        frame = metrics.sort_values(["annual_return", "max_drawdown"], ascending=[False, False])
    return frame.iloc[0].to_dict()


def _condition_gap(row: dict[str, Any], name: str, evaluation: dict[str, Any]) -> tuple[bool, float]:
    if name == "annual_return":
        threshold = _safe_float(evaluation["annual_return_min_absolute"])
        gap = threshold - _safe_float(row.get("annual_return"))
        return gap > 1e-12, gap
    if name == "sharpe":
        threshold = _safe_float(evaluation["sharpe_min"])
        gap = threshold - _safe_float(row.get("sharpe"))
        return gap > 1e-12, gap
    if name == "max_drawdown":
        threshold = _safe_float(evaluation["max_drawdown_floor"])
        gap = threshold - _safe_float(row.get("max_drawdown"))
        return gap > 1e-12, gap
    if name == "total_trades":
        trades = _safe_int(row.get("total_trades"))
        low = _safe_int(evaluation["total_trades_min"])
        high = _safe_int(evaluation["total_trades_max"])
        gap = low - trades if trades < low else trades - high if trades > high else 0.0
        return gap > 0, float(gap)
    if name == "executable_account_actionable_ratio":
        threshold = _safe_float(evaluation["executable_account_actionable_min"])
        ratio = row.get("executable_account_actionable_ratio")
        if ratio is None or (isinstance(ratio, float) and pd.isna(ratio)):
            ratio = 0.0
        gap = threshold - _safe_float(ratio)
        return gap > 1e-12, gap
    if name == "avg_cash_ratio_in_risk_on":
        threshold = _safe_float(evaluation["avg_cash_ratio_max_in_risk_on"])
        gap = _safe_float(row.get("avg_cash_ratio_in_risk_on"), 1.0) - threshold
        return gap > 1e-12, gap
    if name == "largest_single_stock_pnl_contribution":
        threshold = _safe_float(evaluation["largest_single_stock_pnl_contribution_max"])
        gap = _safe_float(row.get("largest_single_stock_pnl_contribution")) - threshold
        return gap > 1e-12, gap
    if name == "largest_industry_pnl_contribution":
        threshold = _safe_float(evaluation["largest_industry_pnl_contribution_max"])
        gap = _safe_float(row.get("largest_industry_pnl_contribution")) - threshold
        return gap > 1e-12, gap
    if name == "realized_pnl":
        gap = 1e-9 - _safe_float(row.get("realized_pnl"))
        return gap > 0, gap
    if name == "cyclical_rotation_pnl":
        if _safe_int(row.get("cyclical_max_positions")) <= 0:
            return False, 0.0
        gap = -_safe_float(row.get("cyclical_rotation_pnl"))
        return gap > 1e-12, gap
    if name == "neighborhood_robustness":
        return True, 3.0
    return False, 0.0


def build_failure_condition_summary(metrics: pd.DataFrame, evaluation: dict[str, Any]) -> pd.DataFrame:
    rows = []
    total = max(len(metrics), 1)
    for name in HARD_CONDITIONS:
        gaps: list[float] = []
        failing: list[float] = []
        for row in metrics.to_dict(orient="records"):
            failed, gap = _condition_gap(row, name, evaluation)
            gaps.append(float(gap))
            if failed:
                failing.append(max(0.0, float(gap)))
        fail_count = len(failing) if name != "neighborhood_robustness" else total
        positive_gaps = failing or [0.0]
        close_tolerance = 0.02 if name not in {"total_trades", "realized_pnl", "cyclical_rotation_pnl", "neighborhood_robustness"} else 3.0
        rows.append(
            {
                "condition_name": name,
                "fail_count": fail_count,
                "fail_ratio": fail_count / total,
                "median_gap_to_pass": float(pd.Series(positive_gaps).median()),
                "best_gap_to_pass": float(min(positive_gaps)),
                "worst_gap_to_pass": float(max(positive_gaps)),
                "variants_close_to_pass_count": int(sum(0 <= gap <= close_tolerance for gap in gaps)),
                "interpretation": _condition_interpretation(name, fail_count, positive_gaps),
            }
        )
    return pd.DataFrame(rows)


def _condition_interpretation(name: str, fail_count: int, gaps: list[float]) -> str:
    if fail_count <= 0:
        return "passed in sampled variants"
    if name in {"annual_return", "realized_pnl"}:
        return "收益能力不足" if fail_count else "收益能力达标"
    if name in {"sharpe", "max_drawdown", "largest_single_stock_pnl_contribution", "largest_industry_pnl_contribution"}:
        return "组合质量不足"
    if name in {"total_trades", "avg_cash_ratio_in_risk_on", "executable_account_actionable_ratio"}:
        return "执行与资金利用不足"
    if name == "cyclical_rotation_pnl":
        return "周期 bucket 负贡献"
    return "邻域鲁棒性不足"


def build_pareto(summary: pd.DataFrame) -> pd.DataFrame:
    frame = summary.sort_values(["fail_count", "median_gap_to_pass"], ascending=[False, False]).reset_index(drop=True)
    labels = []
    for idx, row in enumerate(frame.to_dict(orient="records")):
        if row["fail_count"] <= 0:
            labels.append("MINOR_BLOCKER")
        elif idx < 3:
            labels.append("PRIMARY_BLOCKER")
        elif idx < 6:
            labels.append("SECONDARY_BLOCKER")
        else:
            labels.append("MINOR_BLOCKER")
    frame["blocker_rank"] = labels
    return frame


def _top_reason_from_warnings(warnings: dict[str, Any]) -> str:
    reasons = warnings.get("watch_only_reasons") or {}
    if not reasons:
        return ""
    return max(reasons.items(), key=lambda item: _safe_float(item[1]))[0]


def _cash_reason(row: dict[str, Any], *, max_positions: int) -> str:
    raw = _safe_int(row.get("raw_buy_signal_count"))
    actionable = _safe_int(row.get("account_actionable_buy_count"))
    executable = _safe_int(row.get("executable_buy_count"))
    watch = _safe_int(row.get("watch_only_count"))
    holdings = _safe_int(row.get("positions_count", row.get("holdings_count")))
    cyc = _safe_int(row.get("cyclical_candidates"))
    if raw <= 0:
        return "NO_RAW_SIGNAL"
    if executable <= 0 and actionable > 0:
        return "LOT_FIT_BLOCK"
    if actionable <= 0 and holdings >= max_positions:
        return "PORTFOLIO_FULL"
    if actionable <= 0 and cyc > 0:
        return "CYCLICAL_DISABLED_OR_BLOCKED"
    if actionable <= 0 and watch > 0:
        return "SIGNAL_NOT_ACCOUNT_ACTIONABLE"
    if _safe_int(row.get("replacement_candidate_count")) > 0 and _safe_int(row.get("replacement_executed_count")) <= 0:
        return "REPLACEMENT_NOT_TRIGGERED"
    if actionable <= 0:
        return "UNKNOWN"
    return "UNKNOWN"


def build_risk_on_cash_drag(
    funnel: pd.DataFrame,
    top: dict[str, Any],
    warnings: dict[str, Any],
    evaluation: dict[str, Any],
) -> pd.DataFrame:
    if funnel.empty or not top:
        return pd.DataFrame()
    variant = str(top["variant"])
    frame = funnel[funnel["variant"].astype(str) == variant].copy()
    frame = frame[frame["market_regime"].astype(str) == "risk_on"].copy()
    threshold = _safe_float(evaluation["avg_cash_ratio_max_in_risk_on"])
    frame = frame[frame["cash_ratio"].astype(float) > threshold].copy()
    frame["max_positions"] = _safe_int(top.get("max_positions"))
    frame["positions_count"] = frame.get("holdings_count", pd.Series(dtype=int))
    frame["top_watch_only_reason"] = _top_reason_from_warnings(warnings)
    frame["replacement_candidate_count"] = 0
    frame["replacement_executed_count"] = frame.get("replacement_count", 0)
    frame["reason_cash_not_deployed"] = [
        _cash_reason(row, max_positions=_safe_int(top.get("max_positions"))) for row in frame.to_dict(orient="records")
    ]
    keep = [
        "date",
        "market_regime",
        "cash_ratio",
        "exposure",
        "positions_count",
        "max_positions",
        "executable_buy_count",
        "account_actionable_buy_count",
        "watch_only_count",
        "top_watch_only_reason",
        "raw_buy_signal_count",
        "replacement_candidate_count",
        "replacement_executed_count",
        "reason_cash_not_deployed",
    ]
    return frame[keep].reset_index(drop=True)


def build_trade_density(funnel: pd.DataFrame, top: dict[str, Any], replacement: pd.DataFrame) -> pd.DataFrame:
    if funnel.empty or not top:
        return pd.DataFrame()
    variant = str(top["variant"])
    frame = funnel[funnel["variant"].astype(str) == variant].copy()
    frame["month"] = frame["date"].astype(str).str.slice(0, 7)
    rows = []
    replacement_frame = replacement[replacement.get("variant", pd.Series(dtype=str)).astype(str) == variant] if not replacement.empty and "variant" in replacement else pd.DataFrame()
    for month, group in frame.groupby("month", sort=True):
        regimes = Counter(group["market_regime"].astype(str).tolist())
        rows.append(
            {
                "month": month,
                "market_regime_dominant": regimes.most_common(1)[0][0] if regimes else "",
                "raw_buy_count": int(group["raw_buy_signal_count"].sum()),
                "account_actionable_buy_count": int(group["account_actionable_buy_count"].sum()),
                "executable_buy_count": int(group["executable_buy_count"].sum()),
                "executed_buy_count": int(group["executable_buy_count"].sum()),
                "sell_count": 0,
                "replacement_count": int((replacement_frame["date"].astype(str).str.slice(0, 7) == month).sum()) if not replacement_frame.empty else 0,
                "watch_only_count": int(group["watch_only_count"].sum()),
                "top_block_reason": "",
                "positions_count_start": int(group.iloc[0].get("holdings_count", 0)),
                "positions_count_end": int(group.iloc[-1].get("holdings_count", 0)),
                "exposure_start": float(group.iloc[0].get("exposure", 0.0)),
                "exposure_end": float(group.iloc[-1].get("exposure", 0.0)),
                "cash_ratio_start": float(group.iloc[0].get("cash_ratio", 0.0)),
                "cash_ratio_end": float(group.iloc[-1].get("cash_ratio", 0.0)),
            }
        )
    return pd.DataFrame(rows)


def build_drawdown_source(funnel: pd.DataFrame, top: dict[str, Any], attribution: dict[str, float], replacement: pd.DataFrame) -> pd.DataFrame:
    if funnel.empty or not top:
        return pd.DataFrame()
    variant = str(top["variant"])
    frame = funnel[funnel["variant"].astype(str) == variant].copy()
    if frame.empty or "nav" not in frame:
        return pd.DataFrame()
    nav = pd.to_numeric(frame["nav"], errors="coerce")
    running_max = nav.cummax()
    drawdown = nav / running_max - 1.0
    trough_idx = int(drawdown.idxmin())
    peak_nav = running_max.loc[trough_idx]
    start_candidates = frame.loc[:trough_idx][nav.loc[:trough_idx] == peak_nav]
    start_idx = int(start_candidates.index[-1]) if not start_candidates.empty else int(frame.index[0])
    recovery = frame.loc[trough_idx:][nav.loc[trough_idx:] >= peak_nav]
    recovery_date = str(recovery.iloc[0]["date"]) if not recovery.empty else ""
    period_replacements = replacement[
        (replacement.get("variant", pd.Series(dtype=str)).astype(str) == variant)
        & (replacement.get("date", pd.Series(dtype=str)).astype(str) >= str(frame.loc[start_idx, "date"]))
        & (replacement.get("date", pd.Series(dtype=str)).astype(str) <= str(frame.loc[trough_idx, "date"]))
    ] if not replacement.empty else pd.DataFrame()
    losses = {k: v for k, v in attribution.items() if v < 0}
    return pd.DataFrame(
        [
            {
                "drawdown_id": 1,
                "start_date": frame.loc[start_idx, "date"],
                "trough_date": frame.loc[trough_idx, "date"],
                "recovery_date": recovery_date,
                "max_drawdown": float(drawdown.loc[trough_idx]),
                "regime_at_start": frame.loc[start_idx, "market_regime"],
                "regime_at_trough": frame.loc[trough_idx, "market_regime"],
                "exposure_at_start": frame.loc[start_idx, "exposure"],
                "exposure_at_trough": frame.loc[trough_idx, "exposure"],
                "cash_ratio_at_start": frame.loc[start_idx, "cash_ratio"],
                "cash_ratio_at_trough": frame.loc[trough_idx, "cash_ratio"],
                "top_loss_symbols": json.dumps(dict(sorted(losses.items(), key=lambda item: item[1])[:10]), ensure_ascii=False),
                "top_loss_industries": "",
                "bucket_loss_breakdown": "",
                "exit_signals_triggered": "missing_trade_detail",
                "replacement_signals_triggered": int(len(period_replacements)),
                "missed_exit_candidates": "requires_daily_position_pnl",
            }
        ]
    )


def _future_return(features: pd.DataFrame, symbol: str, date: str, horizon: int) -> float | None:
    if features.empty or not symbol:
        return None
    frame = features[features["symbol"].astype(str) == str(symbol)].sort_values("date").reset_index(drop=True)
    idxs = frame.index[frame["date"].astype(str) >= str(date)].tolist()
    if not idxs:
        return None
    idx = idxs[0]
    future_idx = min(idx + horizon, len(frame) - 1)
    start = _safe_float(frame.loc[idx, "close"])
    end = _safe_float(frame.loc[future_idx, "close"])
    if start <= 0 or end <= 0 or future_idx == idx:
        return None
    return end / start - 1.0


def build_replacement_effectiveness(replacements: pd.DataFrame, features: pd.DataFrame | None = None) -> pd.DataFrame:
    features = features if features is not None else pd.DataFrame()
    rows = []
    for row in replacements.to_dict(orient="records"):
        cand20 = _future_return(features, str(row.get("buy_symbol", "")), str(row.get("date", "")), 20)
        weak20 = _future_return(features, str(row.get("sell_symbol", "")), str(row.get("date", "")), 20)
        cand60 = _future_return(features, str(row.get("buy_symbol", "")), str(row.get("date", "")), 60)
        weak60 = _future_return(features, str(row.get("sell_symbol", "")), str(row.get("date", "")), 60)
        rows.append(
            {
                "date": row.get("date", ""),
                "portfolio_full": True,
                "candidate_symbol": row.get("buy_symbol", ""),
                "candidate_score": row.get("candidate_score", row.get("candidate_score", 0.0)),
                "weakest_holding_symbol": row.get("sell_symbol", ""),
                "weakest_holding_score": row.get("weakest_holding_score", 0.0),
                "score_gap": row.get("score_gap", 0.0),
                "replacement_triggered": True,
                "reason_not_triggered": "",
                "candidate_future_return_20d": cand20,
                "weakest_holding_future_return_20d": weak20,
                "opportunity_cost_20d": (cand20 - weak20) if cand20 is not None and weak20 is not None else None,
                "candidate_future_return_60d": cand60,
                "weakest_holding_future_return_60d": weak60,
                "opportunity_cost_60d": (cand60 - weak60) if cand60 is not None and weak60 is not None else None,
                "diagnostic_only": True,
                "not_for_live_signal": True,
                "variant": row.get("variant", ""),
            }
        )
    frame = pd.DataFrame(rows)
    if not frame.empty:
        frame["diagnostic_only"] = frame["diagnostic_only"].astype(object)
        frame["not_for_live_signal"] = frame["not_for_live_signal"].astype(object)
    return frame


def _write_md_table(path: Path, title: str, frame: pd.DataFrame, max_rows: int = 20) -> None:
    lines = [f"# {title}", ""]
    if frame.empty:
        lines.append("No rows available.")
    else:
        lines.append(frame.head(max_rows).to_markdown(index=False))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _load_optional_features() -> pd.DataFrame:
    try:
        return load_feature_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    except Exception:
        return pd.DataFrame()


def run_diagnostics(input_dir: str | Path = INPUT_DIR, output_dir: str | Path = OUT_DIR) -> dict[str, Any]:
    input_dir = resolve_path(input_dir)
    output_dir = resolve_path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    metrics = _read_csv(input_dir / "core_experiment_metrics.csv")
    funnel = _read_csv(input_dir / "core_execution_funnel.csv")
    attribution_frame = _read_csv(input_dir / "core_attribution_summary.csv")
    replacement = _read_csv(input_dir / "core_replacement_report.csv")
    warnings = _read_json(input_dir / "core_warnings.json")
    config = _read_yaml(input_dir / "core_effective_config.yml")
    evaluation = {**DEFAULT_EVALUATION, **(config.get("evaluation") or {})}
    top = _top_variant(metrics)
    top_variant = str(top.get("variant", ""))

    failure = build_failure_condition_summary(metrics, evaluation)
    failure.to_csv(output_dir / "failure_condition_summary.csv", index=False)
    _write_failure_md(output_dir / "failure_condition_summary.md", failure)
    pareto = build_pareto(failure)
    pareto.to_csv(output_dir / "hard_condition_pareto.csv", index=False)

    attr_row = attribution_frame[attribution_frame.get("variant", pd.Series(dtype=str)).astype(str) == top_variant].iloc[0].to_dict() if not attribution_frame.empty and top_variant in set(attribution_frame.get("variant", pd.Series(dtype=str)).astype(str)) else {}
    symbol_pnl = _parse_mapping(attr_row.get("symbol_pnl"))
    industry_pnl = _parse_mapping(attr_row.get("industry_pnl"))
    bucket_pnl = _parse_mapping(attr_row.get("bucket_pnl"))

    cash_drag = build_risk_on_cash_drag(funnel, top, warnings, evaluation)
    cash_drag.to_csv(output_dir / "risk_on_cash_drag_report.csv", index=False)
    _write_cash_drag_md(output_dir / "risk_on_cash_drag_report.md", cash_drag)
    trade_density = build_trade_density(funnel, top, replacement)
    trade_density.to_csv(output_dir / "trade_density_report.csv", index=False)
    _write_trade_density_md(output_dir / "trade_density_report.md", trade_density)
    drawdown = build_drawdown_source(funnel, top, symbol_pnl, replacement)
    drawdown.to_csv(output_dir / "drawdown_source_report.csv", index=False)
    _write_drawdown_md(output_dir / "drawdown_source_report.md", drawdown, symbol_pnl, industry_pnl, bucket_pnl)
    features = _load_optional_features()
    replacement_eff = build_replacement_effectiveness(replacement, features)
    replacement_eff.to_csv(output_dir / "replacement_effectiveness_report.csv", index=False)
    _write_replacement_md(output_dir / "replacement_effectiveness_report.md", replacement_eff)
    bucket_eff = _bucket_effectiveness(metrics, top, bucket_pnl)
    bucket_eff.to_csv(output_dir / "bucket_effectiveness_report.csv", index=False)
    _write_bucket_md(output_dir / "bucket_effectiveness_report.md", bucket_eff, metrics)
    exit_eff = _exit_rule_effectiveness(metrics, top, drawdown)
    exit_eff.to_csv(output_dir / "exit_rule_effectiveness_report.csv", index=False)
    _write_top_deep_dive(output_dir / "top_variant_deep_dive.md", top, symbol_pnl, industry_pnl, bucket_pnl, drawdown, trade_density, cash_drag)
    _write_module_interpretation(output_dir / "module_disable_interpretation.md", metrics)
    _write_recommendations(output_dir / "diagnosis_recommendations.md", pareto, cash_drag, trade_density, drawdown, metrics)
    missing = [name for name in REQUIRED_DIAGNOSTIC_OUTPUTS if not (output_dir / name).exists()]
    if missing:
        raise RuntimeError(f"missing diagnostics outputs: {missing}")
    return {"top_variant": top_variant, "primary_blockers": pareto.head(3)["condition_name"].tolist()}


def _write_failure_md(path: Path, failure: pd.DataFrame) -> None:
    pareto = build_pareto(failure)
    lines = ["# 50k core hard condition failure summary", "", "## Primary blockers", ""]
    for row in pareto[pareto["blocker_rank"] == "PRIMARY_BLOCKER"].to_dict(orient="records"):
        lines.append(f"- {row['condition_name']}: fail_count={row['fail_count']}, median_gap={row['median_gap_to_pass']:.4f}, {row['interpretation']}")
    lines.extend(["", "## Full table", "", failure.to_markdown(index=False)])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_cash_drag_md(path: Path, frame: pd.DataFrame) -> None:
    reason_counts = Counter(frame.get("reason_cash_not_deployed", pd.Series(dtype=str)).dropna().astype(str).tolist())
    lines = [
        "# risk-on cash drag report",
        "",
        f"- high_cash_risk_on_days: {len(frame)}",
        f"- top_reason: {reason_counts.most_common(1)[0][0] if reason_counts else 'none'}",
        "",
        "结论：risk-on 现金高主要看 `reason_cash_not_deployed` 分布。若不是 `NO_RAW_SIGNAL`，说明不是没有信号，而是信号未转成可执行。现金替代 sleeve 仍应保持后续研究接口，当前先修股票执行机制。",
        "",
        frame.head(20).to_markdown(index=False) if not frame.empty else "No high-cash risk-on days.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_trade_density_md(path: Path, frame: pd.DataFrame) -> None:
    no_trade_months = int((frame.get("executed_buy_count", pd.Series(dtype=float)) <= 0).sum()) if not frame.empty else 0
    lines = [
        "# trade density report",
        "",
        f"- months: {len(frame)}",
        f"- no_executed_buy_months: {no_trade_months}",
        "- sell_count warning: current stage1 files do not contain monthly sell detail; sell_count is not used for strategy logic.",
        "",
        frame.head(36).to_markdown(index=False) if not frame.empty else "No rows.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_drawdown_md(path: Path, frame: pd.DataFrame, symbol_pnl: dict[str, float], industry_pnl: dict[str, float], bucket_pnl: dict[str, float]) -> None:
    losses = dict(sorted({k: v for k, v in symbol_pnl.items() if v < 0}.items(), key=lambda item: item[1])[:10])
    lines = [
        "# drawdown source report",
        "",
        frame.to_markdown(index=False) if not frame.empty else "No drawdown rows.",
        "",
        "## Attribution available",
        "",
        f"- top_loss_symbols_global: {losses}",
        f"- industry_pnl_global: {industry_pnl}",
        f"- bucket_pnl_global: {bucket_pnl}",
        "",
        "缺失字段警告：stage1 没有逐日持仓 PnL 和逐笔 exit signal 明细，因此 drawdown 期间股票/bucket 贡献只能用全局 attribution 辅助判断，不能伪造成逐日归因。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_replacement_md(path: Path, frame: pd.DataFrame) -> None:
    triggered = int(frame.get("replacement_triggered", pd.Series(dtype=bool)).fillna(False).sum()) if not frame.empty else 0
    opp20 = pd.to_numeric(frame.get("opportunity_cost_20d", pd.Series(dtype=float)), errors="coerce")
    lines = [
        "# replacement effectiveness report",
        "",
        "- diagnostic_only: true",
        "- not_for_live_signal: true",
        f"- replacement_triggered_rows: {triggered}",
        f"- median_opportunity_cost_20d: {opp20.median() if not opp20.dropna().empty else 'missing'}",
        "",
        "future_return 字段只用于离线诊断，不得进入实时策略决策。",
        "",
        frame.head(20).to_markdown(index=False) if not frame.empty else "No replacement rows.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _bucket_effectiveness(metrics: pd.DataFrame, top: dict[str, Any], bucket_pnl: dict[str, float]) -> pd.DataFrame:
    rows = []
    for bucket in ["defensive_dividend", "cyclical_rotation"]:
        pnl = bucket_pnl.get(bucket, _safe_float(top.get(f"{bucket}_pnl")))
        rows.append(
            {
                "bucket": bucket,
                "pnl": pnl,
                "trades": "",
                "win_rate": "",
                "drawdown_contribution": "",
                "avg_holding_days": "",
                "realized_unrealized": f"realized={_safe_float(top.get('realized_pnl')):.2f}; unrealized={_safe_float(top.get('unrealized_pnl')):.2f}",
            }
        )
    return pd.DataFrame(rows)


def _write_bucket_md(path: Path, frame: pd.DataFrame, metrics: pd.DataFrame) -> None:
    cy0 = metrics[metrics.get("cyclical_max_positions", pd.Series(dtype=int)).fillna(0).astype(int) == 0] if not metrics.empty else pd.DataFrame()
    cypos = metrics[metrics.get("cyclical_max_positions", pd.Series(dtype=int)).fillna(0).astype(int) > 0] if not metrics.empty else pd.DataFrame()
    lines = [
        "# bucket effectiveness report",
        "",
        frame.to_markdown(index=False) if not frame.empty else "No rows.",
        "",
        f"- cyclical_max_positions_0_best_annual: {cy0['annual_return'].max() if not cy0.empty else 'missing'}",
        f"- cyclical_enabled_best_annual: {cypos['annual_return'].max() if not cypos.empty else 'missing'}",
        "- 结论需要结合 cyclical_rotation_pnl 与回撤，而不是只看最高年化。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _exit_rule_effectiveness(metrics: pd.DataFrame, top: dict[str, Any], drawdown: pd.DataFrame) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "variant": top.get("variant", ""),
                "trend_stop_disabled": "disable_trend_stop" in str(top.get("module_control", "")) or str(top.get("module_control")) == "disable_both",
                "max_drawdown": top.get("max_drawdown", 0.0),
                "drawdown_start": drawdown.iloc[0]["start_date"] if not drawdown.empty else "",
                "drawdown_trough": drawdown.iloc[0]["trough_date"] if not drawdown.empty else "",
                "missing_exit_signal_detail": True,
                "interpretation": "需要 partial de-risk 研究；当前 stage1 不能证明 exit signal 日内是否滞后。",
            }
        ]
    )


def _write_top_deep_dive(path: Path, top: dict[str, Any], symbol_pnl: dict[str, float], industry_pnl: dict[str, float], bucket_pnl: dict[str, float], drawdown: pd.DataFrame, trade_density: pd.DataFrame, cash_drag: pd.DataFrame) -> None:
    positives = dict(sorted({k: v for k, v in symbol_pnl.items() if v > 0}.items(), key=lambda item: item[1], reverse=True)[:10])
    negatives = dict(sorted({k: v for k, v in symbol_pnl.items() if v < 0}.items(), key=lambda item: item[1])[:10])
    lines = [
        "# top attempted variant deep dive",
        "",
        f"- variant: {top.get('variant', '')}",
        f"- annual_return: {_pct(top.get('annual_return', 0.0))}",
        f"- cumulative_return: {_pct(top.get('cumulative_return', 0.0))}",
        f"- max_drawdown: {_pct(top.get('max_drawdown', 0.0))}",
        f"- sharpe: {_safe_float(top.get('sharpe')):.4f}",
        f"- total_trades: {_safe_int(top.get('total_trades'))}",
        f"- average_exposure: {_pct(top.get('average_exposure', 0.0))}",
        f"- avg_cash_ratio_in_risk_on: {_pct(top.get('avg_cash_ratio_in_risk_on', 0.0))}",
        f"- realized_pnl: {_safe_float(top.get('realized_pnl')):.2f}",
        f"- unrealized_pnl: {_safe_float(top.get('unrealized_pnl')):.2f}",
        f"- largest_single_stock_pnl_contribution: {_pct(top.get('largest_single_stock_pnl_contribution', 0.0))}",
        f"- largest_industry_pnl_contribution: {_pct(top.get('largest_industry_pnl_contribution', 0.0))}",
        "",
        "## 收益来源",
        "",
        f"- top_10_positive_positions: {positives}",
        f"- top_10_negative_positions: {negatives}",
        f"- bucket_contribution: {bucket_pnl}",
        f"- industry_contribution: {industry_pnl}",
        f"- realized_vs_unrealized: realized={_safe_float(top.get('realized_pnl')):.2f}, unrealized={_safe_float(top.get('unrealized_pnl')):.2f}",
        "",
        "## 回撤来源",
        "",
        drawdown.to_markdown(index=False) if not drawdown.empty else "No drawdown interval available.",
        "",
        "## Sharpe 偏低原因",
        "",
        "- 当前可见证据显示收益集中在少数股票/阶段，且最大回撤与低交易密度拉低风险调整收益。",
        "- 缺失字段警告：没有逐日持仓 PnL 和逐笔交易明细，不能静默伪造日收益波动归因。",
        "",
        "## 交易数不足原因",
        "",
        trade_density.head(24).to_markdown(index=False) if not trade_density.empty else "No monthly rows.",
        "",
        "## risk-on cash drag",
        "",
        cash_drag["reason_cash_not_deployed"].value_counts().to_markdown() if not cash_drag.empty else "No high-cash risk-on rows.",
        "",
        "## 结论",
        "",
        "- 该变体年化高但不通过，主要是收益分布质量问题：Sharpe 不足、回撤过深、交易数偏少，而不是单纯 alpha 不存在。",
        "- 可作为机制修复 base variant，但必须修复 partial de-risk、交易密度与现金部署机制。",
        "- 值得保留：5 持仓、18% 单票上限、risk-on 85% 目标暴露、cyclical watch-only 对照。",
        "- 需要修复：退出滞后、monthly review、replacement 触发效率。",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_module_interpretation(path: Path, metrics: pd.DataFrame) -> None:
    lines = ["# module disable interpretation", ""]
    if metrics.empty:
        lines.append("No metrics available.")
    else:
        cols = ["variant", "module_control", "annual_return", "max_drawdown", "sharpe", "total_trades", "replacement_count", "fail_reasons"]
        lines.append(metrics[[col for col in cols if col in metrics.columns]].head(20).to_markdown(index=False))
        lines.extend(
            [
                "",
                "## Interpretation",
                "",
                "- disable_both 排名靠前不等于两个模块都应删除；它同时牺牲了回撤和交易密度，需要 repair 对照。",
                "- disable_trend_stop 若提高收益但扩大回撤，说明原止损可能压收益，但完全关闭会暴露尾部风险。",
                "- high_dividend_supplement 是否拖累，需要看其关闭后错误买入、回撤和交易数的共同变化。",
                "- replacement 在 stage1 中触发次数少，不能证明足够有效；下一阶段测试更低 score gap 和更短持有日。",
                "- cyclical disabled 对 50k 可能更稳，周期 sleeve 应先 watch-only 或限制为 1。",
            ]
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _write_recommendations(path: Path, pareto: pd.DataFrame, cash_drag: pd.DataFrame, trade_density: pd.DataFrame, drawdown: pd.DataFrame, metrics: pd.DataFrame) -> None:
    primary = pareto.head(3)["condition_name"].tolist() if not pareto.empty else []
    cash_reasons = Counter(cash_drag.get("reason_cash_not_deployed", pd.Series(dtype=str)).dropna().astype(str).tolist())
    lines = [
        "# diagnosis recommendations",
        "",
        f"- primary_blockers: {primary}",
        f"- risk_on_cash_drag_top_reasons: {dict(cash_reasons.most_common(5))}",
        "",
        "## Repair experiment candidates",
        "",
        "- A. monthly rebalance review: only when risk_on and cash_ratio is above target; keep lot, position, industry and single-name constraints.",
        "- B. replacement repair: test score_gap 6/8/10, min_holding_days 20/40, max_replacements_per_month 1/2; keep thesis-still-valid and RS-positive protection.",
        "- C. partial de-risk: reduce one round lot or sell all single-lot holdings only when loss plus trend/RS weakness is confirmed.",
        "- D. cyclical sleeve: keep cyclical as watch-only unless risk_on, close >= ma60 and ma20 slope non-negative.",
        "- E. module repair: do not delete high dividend or trend stop; test partial de-risk replacing hard trend stop.",
        "",
        "These are research-only repair ideas, not release changes.",
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Diagnose combined_v2_50k_core hard-condition failures.")
    parser.add_argument("--input-dir", default=INPUT_DIR)
    parser.add_argument("--output-dir", default=OUT_DIR)
    args = parser.parse_args()
    summary = run_diagnostics(args.input_dir, args.output_dir)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
