from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from src.strategy.universe import build_candidate_pool
from src.utils.config import resolve_path
from scripts.report_metadata import config_hash, data_hash, git_commit


DAILY_FUNNEL_COLUMNS = [
    "date",
    "benchmark_close",
    "market_regime",
    "max_total_exposure",
    "current_total_exposure",
    "current_cash",
    "effective_universe_size",
    "holdings_count",
    "decision_scope_size",
    "candidates_seen",
    "passed_base_filter_count",
    "passed_bucket_filter_count",
    "passed_valuation_filter_count",
    "passed_quality_filter_count",
    "passed_price_trigger_count",
    "raw_buy_signal_count",
    "raw_sell_signal_count",
    "blocked_by_universe_count",
    "blocked_by_market_regime_count",
    "blocked_by_cash_count",
    "blocked_by_position_limit_count",
    "blocked_by_single_name_limit_count",
    "blocked_by_min_trade_amount_count",
    "blocked_by_lot_size_count",
    "blocked_by_existing_position_count",
    "blocked_by_hard_add_ban_count",
    "executable_buy_count",
    "executable_sell_count",
    "executed_buy_count",
    "executed_sell_count",
]

BLOCKED_COLUMNS = [
    "date",
    "ts_code",
    "name",
    "bucket",
    "intended_action",
    "intended_signal_level",
    "intended_target_weight",
    "current_weight",
    "close",
    "stock_valuation_quantile",
    "stock_valuation_quantile_source_field",
    "industry_valuation_quantile",
    "industry_valuation_quantile_source_field",
    "valuation_fallback_used",
    "valuation_fallback_reason",
    "reason_code",
    "reason_detail",
]

TRADES_DETAILED_COLUMNS = [
    "date",
    "ts_code",
    "name",
    "bucket",
    "side",
    "action",
    "signal_level",
    "shares",
    "price",
    "amount",
    "fee",
    "tax",
    "slippage",
    "slippage_cost",
    "cash_before",
    "cash_after",
    "position_before",
    "position_after",
    "weight_before",
    "weight_after",
    "target_weight",
    "entry_reason",
    "exit_reason",
    "holding_days",
    "realized_pnl",
    "unrealized_pnl_after_trade",
    "market_regime",
    "execution_mode",
    "fill_price_field",
    "execution_adjustment",
    "execution_reason_code",
]

UNIVERSE_FUNNEL_COLUMNS = [
    "refresh_date",
    "raw_a_share_count",
    "after_non_st_count",
    "after_listed_days_count",
    "after_liquidity_count",
    "after_market_cap_count",
    "after_industry_available_count",
    "after_core_fields_count",
    "defensive_candidates_count",
    "cyclical_candidates_count",
    "candidate_pool_size",
    "effective_universe_size",
    "retained_count",
    "new_count",
    "dropped_count",
    "avg_final_score",
    "min_final_score",
    "max_final_score",
    "industry_count",
    "max_names_per_industry_observed",
]

CANDIDATE_SCORE_COLUMNS = [
    "date",
    "ts_code",
    "bucket",
    "final_score",
    "valuation_score",
    "quality_score",
    "leader_score",
    "dividend_score",
    "cycle_safety_score",
    "stock_valuation_quantile",
    "stock_valuation_quantile_source_field",
    "stock_valuation_metric",
    "industry_valuation_quantile",
    "industry_valuation_quantile_source_field",
    "industry_valuation_metric",
    "valuation_fallback_used",
    "valuation_fallback_reason",
    "pe_ttm",
    "pb",
    "dividend_yield_ttm",
    "roe",
    "cfo_ttm",
    "debt_to_assets",
    "market_cap",
    "avg_amount_60d",
    "industry",
    "industry_rank_by_market_cap",
    "retained_or_new",
]


def _empty_frame(columns: list[str]) -> pd.DataFrame:
    return pd.DataFrame(columns=columns)


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(numeric):
        return default
    return numeric


def build_universe_funnel(
    features: pd.DataFrame,
    history_dir: str | Path,
    universe_rules_cfg: dict,
    metric_map_cfg: dict,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    history_path = resolve_path(history_dir)
    if not history_path.exists():
        return _empty_frame(UNIVERSE_FUNNEL_COLUMNS), _empty_frame(CANDIDATE_SCORE_COLUMNS)
    feature_dates = set(features["date"].astype(str).unique()) if not features.empty else set()
    rows: list[dict] = []
    score_rows: list[dict] = []
    for path in sorted(history_path.glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        refresh_date = str(payload.get("effective_from") or payload.get("as_of_date") or path.stem)
        if refresh_date not in feature_dates:
            continue
        snapshot = features[features["date"].astype(str) == refresh_date].copy()
        if snapshot.empty:
            continue
        listed_min = float(universe_rules_cfg["bucket_filters"]["base"].get("listed_days_min", 0))
        liquidity_min = float(universe_rules_cfg["bucket_filters"]["base"].get("avg_amount_60d_million_min", 0))
        market_cap_min = float(universe_rules_cfg["bucket_filters"]["base"].get("market_cap_billion_min", 0))
        raw_a = snapshot[snapshot.get("is_a_share", pd.Series(True, index=snapshot.index)).astype(bool)]
        non_st = raw_a[~raw_a.get("is_st", pd.Series(False, index=raw_a.index)).astype(bool)]
        listed = non_st[pd.to_numeric(non_st.get("listed_days", pd.Series(0, index=non_st.index)), errors="coerce").fillna(0) >= listed_min]
        liquid = listed[pd.to_numeric(listed.get("avg_amount_60d_million", pd.Series(0, index=listed.index)), errors="coerce").fillna(0) >= liquidity_min]
        capped = liquid[pd.to_numeric(liquid.get("market_cap_billion", pd.Series(0, index=liquid.index)), errors="coerce").fillna(0) >= market_cap_min]
        industries = set(metric_map_cfg.get("industry_bucket_candidates", {}).keys()) | set(metric_map_cfg.get("industry_bucket_map", {}).keys())
        with_industry = capped[capped.get("industry", pd.Series(pd.NA, index=capped.index)).isin(industries)]
        core = with_industry[with_industry.get("core_fields_complete", pd.Series(True, index=with_industry.index)).fillna(False).astype(bool)]
        candidate_pool = build_candidate_pool(snapshot, universe_rules_cfg, metric_map_cfg, refresh_date)
        stocks = payload.get("stocks", []) or []
        stock_frame = pd.DataFrame(stocks)
        changes = payload.get("changes", []) or []
        changes_frame = pd.DataFrame(changes)
        if "bucket" in candidate_pool.columns:
            defensive_count = int((candidate_pool["bucket"] == "defensive_dividend").sum())
            cyclical_count = int((candidate_pool["bucket"] == "cyclical_rotation").sum())
        else:
            defensive_count = 0
            cyclical_count = 0
        rows.append(
            {
                "refresh_date": refresh_date,
                "raw_a_share_count": int(len(raw_a)),
                "after_non_st_count": int(len(non_st)),
                "after_listed_days_count": int(len(listed)),
                "after_liquidity_count": int(len(liquid)),
                "after_market_cap_count": int(len(capped)),
                "after_industry_available_count": int(len(with_industry)),
                "after_core_fields_count": int(len(core)),
                "defensive_candidates_count": defensive_count,
                "cyclical_candidates_count": cyclical_count,
                "candidate_pool_size": int(payload.get("candidate_pool_size", len(candidate_pool))),
                "effective_universe_size": int(payload.get("effective_universe_size", len(stocks))),
                "retained_count": int((stock_frame.get("selected_as", pd.Series(dtype=object)) == "retained").sum()) if not stock_frame.empty else 0,
                "new_count": int((stock_frame.get("selected_as", pd.Series(dtype=object)).isin(["new_entry", "floor_fill"])).sum()) if not stock_frame.empty else 0,
                "dropped_count": int((changes_frame.get("change_tag", pd.Series(dtype=object)).isin(["removed", "forced_exit", "demoted_to_frozen"])).sum()) if not changes_frame.empty else 0,
                "avg_final_score": float(pd.to_numeric(stock_frame.get("final_score", pd.Series(dtype=float)), errors="coerce").mean()) if not stock_frame.empty else None,
                "min_final_score": float(pd.to_numeric(stock_frame.get("final_score", pd.Series(dtype=float)), errors="coerce").min()) if not stock_frame.empty else None,
                "max_final_score": float(pd.to_numeric(stock_frame.get("final_score", pd.Series(dtype=float)), errors="coerce").max()) if not stock_frame.empty else None,
                "industry_count": int(stock_frame.get("industry_l1", pd.Series(dtype=object)).nunique()) if not stock_frame.empty else 0,
                "max_names_per_industry_observed": int(stock_frame.get("industry_l1", pd.Series(dtype=object)).value_counts().max()) if not stock_frame.empty else 0,
            }
        )
        for item in candidate_pool.to_dict(orient="records"):
            score_rows.append(
                {
                    "date": refresh_date,
                    "ts_code": item.get("symbol"),
                    "bucket": item.get("bucket"),
                    "final_score": item.get("final_score"),
                    "valuation_score": item.get("valuation_score"),
                    "quality_score": item.get("quality_score"),
                    "leader_score": item.get("leader_score"),
                    "dividend_score": item.get("dividend_score"),
                    "cycle_safety_score": item.get("cycle_safety_score"),
                    "stock_valuation_quantile": item.get("stock_valuation_quantile", item.get("stock_q_blended")),
                    "stock_valuation_quantile_source_field": item.get("stock_valuation_quantile_source_field"),
                    "stock_valuation_metric": item.get("stock_valuation_metric"),
                    "industry_valuation_quantile": item.get("industry_valuation_quantile", item.get("industry_q_blended")),
                    "industry_valuation_quantile_source_field": item.get("industry_valuation_quantile_source_field"),
                    "industry_valuation_metric": item.get("industry_valuation_metric"),
                    "valuation_fallback_used": item.get("valuation_fallback_used", False),
                    "valuation_fallback_reason": item.get("valuation_fallback_reason", ""),
                    "pe_ttm": item.get("pe_ttm"),
                    "pb": item.get("pb"),
                    "dividend_yield_ttm": item.get("dv_ttm"),
                    "roe": item.get("roe"),
                    "cfo_ttm": item.get("cfo_ttm"),
                    "debt_to_assets": item.get("debt_to_assets"),
                    "market_cap": item.get("market_cap_billion"),
                    "avg_amount_60d": item.get("avg_amount_60d_million"),
                    "industry": item.get("industry"),
                    "industry_rank_by_market_cap": item.get("industry_market_cap_rank"),
                    "retained_or_new": item.get("selected_as"),
                }
            )
    return pd.DataFrame(rows, columns=UNIVERSE_FUNNEL_COLUMNS), pd.DataFrame(score_rows, columns=CANDIDATE_SCORE_COLUMNS)


def _monthly_counts(daily: pd.DataFrame) -> pd.DataFrame:
    if daily.empty:
        return pd.DataFrame(columns=["month", "raw_buy_signal_count", "executable_buy_count", "executed_buy_count"])
    frame = daily.copy()
    frame["month"] = pd.to_datetime(frame["date"]).dt.strftime("%Y-%m")
    return frame.groupby("month", as_index=False)[["raw_buy_signal_count", "executable_buy_count", "executed_buy_count"]].sum()


def write_diagnostic_outputs(
    prefix: str,
    result,
    universe_funnel: pd.DataFrame,
    output_dir: str | Path = "reports/backtest",
    candidate_scores: pd.DataFrame | None = None,
) -> dict[str, Path]:
    out_dir = resolve_path(output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    daily = result.daily_diagnostics if result.daily_diagnostics is not None else _empty_frame(DAILY_FUNNEL_COLUMNS)
    blocked = result.blocked_signals if result.blocked_signals is not None else _empty_frame(BLOCKED_COLUMNS)
    detailed = result.trades_detailed if result.trades_detailed is not None else _empty_frame(TRADES_DETAILED_COLUMNS)
    daily = daily.reindex(columns=DAILY_FUNNEL_COLUMNS)
    blocked = blocked.reindex(columns=BLOCKED_COLUMNS)
    detailed = detailed.reindex(columns=TRADES_DETAILED_COLUMNS)
    universe = universe_funnel.reindex(columns=UNIVERSE_FUNNEL_COLUMNS)
    paths = {
        "signal_funnel": out_dir / f"{prefix}_signal_funnel.csv",
        "universe_funnel": out_dir / f"{prefix}_universe_funnel.csv",
        "blocked_signals": out_dir / f"{prefix}_blocked_signals.csv",
        "trades_detailed": out_dir / f"{prefix}_trades_detailed.csv",
        "diagnostic_report": out_dir / f"{prefix}_diagnostic_report.md",
    }
    daily.to_csv(paths["signal_funnel"], index=False)
    universe.to_csv(paths["universe_funnel"], index=False)
    blocked.to_csv(paths["blocked_signals"], index=False)
    detailed.to_csv(paths["trades_detailed"], index=False)
    if candidate_scores is not None:
        paths["candidate_scores"] = out_dir / f"{prefix}_candidate_scores.csv"
        candidate_scores.reindex(columns=CANDIDATE_SCORE_COLUMNS).to_csv(paths["candidate_scores"], index=False)
    paths["diagnostic_report"].write_text(_render_diagnostic_report(prefix, result.metrics, daily, universe, blocked, detailed), encoding="utf-8")
    return paths


def _render_diagnostic_report(
    prefix: str,
    metrics: dict,
    daily: pd.DataFrame,
    universe: pd.DataFrame,
    blocked: pd.DataFrame,
    detailed: pd.DataFrame,
) -> str:
    avg_exposure = metrics.get("avg_daily_exposure", 0.0)
    max_exposure = metrics.get("max_daily_exposure", 0.0)
    avg_positions = metrics.get("avg_positions", 0.0)
    blocked_counts = blocked["reason_code"].value_counts() if not blocked.empty and "reason_code" in blocked else pd.Series(dtype=int)
    monthly_universe = universe[["refresh_date", "effective_universe_size"]].to_dict(orient="records") if not universe.empty else []
    monthly_buy = _monthly_counts(daily)
    lines = [
        f"# {prefix} 回测诊断报告",
        "",
        "## 元数据",
        "",
        f"- git_commit: {git_commit()}",
        f"- config_hash: {config_hash()}",
        f"- data_hash: {data_hash()}",
        f"- manual_review_required: true",
        f"- auto_trading_approved: false",
        "",
        "## 三年绩效摘要",
        "",
        f"- 年化收益: {metrics.get('annual_return', metrics.get('cagr', 0.0)):.2%}",
        f"- 累计收益: {metrics.get('cumulative_return', 0.0):.2%}",
        f"- 最大回撤: {metrics.get('max_drawdown', 0.0):.2%}",
        f"- 夏普: {metrics.get('sharpe', 0.0):.2f}",
        f"- 胜率: {metrics.get('win_rate', 0.0):.2%}",
        f"- 成交笔数: {metrics.get('total_trades', 0)}，买入 {metrics.get('buy_trades', 0)}，卖出 {metrics.get('sell_trades', 0)}",
        "",
        "## 仓位与持仓",
        "",
        f"- 平均日仓位: {avg_exposure:.2%}",
        f"- 最大日仓位: {max_exposure:.2%}",
        f"- 平均持仓数量: {avg_positions:.2f}",
        f"- 最大持仓数量: {metrics.get('max_positions', 0)}",
        f"- 平均持有天数: {metrics.get('avg_holding_days', 0.0):.2f}",
        f"- 持有天数中位数: {metrics.get('median_holding_days', 0.0):.2f}",
        "",
        "## 为什么交易稀疏",
        "",
    ]
    if not daily.empty:
        totals = daily[["raw_buy_signal_count", "executable_buy_count", "executed_buy_count", "blocked_by_market_regime_count", "blocked_by_cash_count", "blocked_by_min_trade_amount_count", "blocked_by_lot_size_count", "blocked_by_position_limit_count"]].sum()
        lines.extend(
            [
                f"- 原始买入信号合计: {int(totals['raw_buy_signal_count'])}",
                f"- 可执行买入信号合计: {int(totals['executable_buy_count'])}",
                f"- 实际买入成交合计: {int(totals['executed_buy_count'])}",
                f"- 市场状态阻断: {int(totals['blocked_by_market_regime_count'])}",
                f"- 资金阻断: {int(totals['blocked_by_cash_count'])}",
                f"- 最小交易额阻断: {int(totals['blocked_by_min_trade_amount_count'])}",
                f"- 整手阻断: {int(totals['blocked_by_lot_size_count'])}",
                f"- 总仓位/每日数量限制阻断: {int(totals['blocked_by_position_limit_count'])}",
            ]
        )
        avg_universe = float(universe["effective_universe_size"].mean()) if not universe.empty else 0.0
        min_universe = int(universe["effective_universe_size"].min()) if not universe.empty else 0
        max_universe = int(universe["effective_universe_size"].max()) if not universe.empty else 0
        lines.extend(["", "## 诊断结论", ""])
        if int(totals["raw_buy_signal_count"]) <= max(10, int(metrics.get("buy_trades", 0)) + 2):
            lines.append(
                f"- 交易稀疏的首要原因是原始买入信号本身很少：三年只有 {int(totals['raw_buy_signal_count'])} 个 raw buy，实际成交 {int(totals['executed_buy_count'])} 个。"
            )
        else:
            lines.append(
                f"- 原始买入信号有 {int(totals['raw_buy_signal_count'])} 个，主要流失发生在执行层：可执行买入 {int(totals['executable_buy_count'])} 个。"
            )
        lines.append(f"- 历史 effective universe 平均 {avg_universe:.2f} 只，最小 {min_universe} 只，最大 {max_universe} 只。")
        if int(totals["blocked_by_min_trade_amount_count"]) or int(totals["blocked_by_lot_size_count"]):
            lines.append(
                f"- 执行约束中，最小交易额阻断 {int(totals['blocked_by_min_trade_amount_count'])} 次，整手阻断 {int(totals['blocked_by_lot_size_count'])} 次。"
            )
        if int(totals["blocked_by_position_limit_count"]):
            lines.append(f"- 仓位或每日数量限制阻断 {int(totals['blocked_by_position_limit_count'])} 次，说明信号密度已高于可执行容量。")
        if int(totals["blocked_by_market_regime_count"]):
            lines.append(
                f"- 市场状态阻断 {int(totals['blocked_by_market_regime_count'])} 次；这些是日常决策层阻断，并不等同于已形成 raw buy 后被拦截。"
            )
    else:
        lines.append("- 未生成每日漏斗。")
    lines.extend(["", "## 每月 effective universe size", ""])
    if monthly_universe:
        for row in monthly_universe:
            lines.append(f"- {row['refresh_date']}: {row['effective_universe_size']}")
    else:
        lines.append("- 无股票池漏斗记录。")
    lines.extend(["", "## 每月买入漏斗", ""])
    if not monthly_buy.empty:
        for row in monthly_buy.to_dict(orient="records"):
            lines.append(
                f"- {row['month']}: raw_buy={int(row['raw_buy_signal_count'])}, executable_buy={int(row['executable_buy_count'])}, executed_buy={int(row['executed_buy_count'])}"
            )
    else:
        lines.append("- 无买入信号记录。")
    lines.extend(["", "## 拦截原因排序", ""])
    if not blocked_counts.empty:
        for reason, count in blocked_counts.items():
            lines.append(f"- {reason}: {int(count)}")
    else:
        lines.append("- 无被拦截交易意图。")
    lines.extend(["", "## 重点个股逐笔解释", ""])
    focus = detailed[detailed["ts_code"].isin(["002705.sz", "002271.sz", "000012.sz"])] if not detailed.empty else pd.DataFrame()
    if not focus.empty:
        for row in focus.to_dict(orient="records"):
            reason = row.get("entry_reason") if row.get("side") == "BUY" else row.get("exit_reason")
            lines.append(
                f"- {row['date']} {row['ts_code']} {row['action']} {row['shares']:.0f} 股，价格 {row['price']:.4f}，持有天数 {row['holding_days']}，原因：{reason}"
            )
    else:
        lines.append("- 三只重点股票在本次输出中无成交明细。")
    if prefix == "combined_v2" and metrics.get("max_drawdown", 0.0) < -0.18:
        lines.extend(["", "## 风险提示", "", f"- **最大回撤 {metrics.get('max_drawdown', 0.0):.2%} 超过 -18%，需要按交易明细进一步拆分来源。**"])
    lines.append("")
    return "\n".join(lines)
