#!/usr/bin/env python3
from __future__ import annotations

import copy
import argparse
import json
import math
import random
import sys
import time
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_common import (
    DEFAULT_END_DATE,
    DEFAULT_FEATURES_FILE,
    DEFAULT_START_DATE,
    V2_HISTORY_DIR,
    ensure_parent,
    load_audit_configs,
    load_benchmark_window,
    load_feature_window,
    metrics_row,
    pct,
    prepare_v2_history,
    run_profile,
)
from scripts.run_backtest_compare import _benchmark_metrics, _generate_v2_history, _history_generation_start
from scripts.report_metadata import metadata_header, write_json
from src.strategy.backtest_engine import BacktestEngine, BacktestResult
from src.strategy.backtest_reports import build_universe_funnel
from src.strategy.regime import determine_market_regime
from src.utils.config import load_yaml_optional, resolve_path


@dataclass
class SimpleResult:
    metrics: dict
    nav: pd.DataFrame
    trades_detailed: pd.DataFrame
    final_positions: pd.DataFrame


@dataclass
class MonthlyMarketData:
    dates: list[str]
    by_date: dict[str, pd.DataFrame]


CONTROL_IDS = [
    "baseline_combined_next_bar",
    "combined_v2_next_bar",
    "v2_universe_equal_weight_monthly",
    "v2_top_score_monthly",
    "v2_defensive_only",
    "v2_cyclical_only",
    "v2_no_high_dividend_supplement",
    "v2_no_grid",
    "v2_no_trend_stop",
    "v2_risk_off_no_new_buy",
    "v2_no_market_state_filter",
    "v2_no_industry_cap",
    "v2_relaxed_account_constraints_research_only",
]


def _history_dir_has_json(path_like: str | Path) -> bool:
    path = Path(resolve_path(path_like))
    return path.exists() and any(path.glob("*.json"))


def _load_existing_metrics(path: Path, refresh_all: bool) -> pd.DataFrame:
    if refresh_all or not path.exists():
        return pd.DataFrame()
    try:
        frame = pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()
    if "control_id" not in frame.columns:
        return pd.DataFrame()
    return frame


def _load_existing_trades(path: Path, refresh_all: bool) -> pd.DataFrame:
    if refresh_all or not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _run_step(control_id: str, fn):
    started = time.monotonic()
    print(f"[controls] start {control_id}", flush=True)
    result = fn()
    print(f"[controls] done {control_id} elapsed={time.monotonic() - started:.1f}s", flush=True)
    return result


def _build_monthly_market_data(features: pd.DataFrame) -> MonthlyMarketData:
    return MonthlyMarketData(
        dates=sorted(features["date"].astype(str).unique()),
        by_date={date: frame.set_index("symbol") for date, frame in features.groupby("date", sort=True)},
    )


def _round_down_lot(shares: float, lot: int) -> float:
    return float(int(max(0.0, shares)) // max(1, lot) * max(1, lot))


def _simple_metrics(nav: pd.DataFrame, trades: pd.DataFrame, initial_capital: float, final_positions: pd.DataFrame) -> dict:
    if nav.empty:
        return {}
    returns = nav["nav"].astype(float).pct_change().dropna()
    years = max(len(nav) / 252, 1 / 252)
    annual = (float(nav["nav"].iloc[-1]) / initial_capital) ** (1 / years) - 1.0
    cumulative = float(nav["nav"].iloc[-1]) / initial_capital - 1.0
    drawdown = nav["nav"].astype(float) / nav["nav"].astype(float).cummax() - 1.0
    sell_trades = trades[trades["side"] == "SELL"] if not trades.empty else pd.DataFrame()
    realized = float(trades["realized_pnl"].sum()) if not trades.empty else 0.0
    unrealized = float(final_positions["unrealized_pnl"].sum()) if not final_positions.empty and "unrealized_pnl" in final_positions else 0.0
    wins_sum = float(sell_trades.loc[sell_trades["realized_pnl"] > 0, "realized_pnl"].sum()) if not sell_trades.empty else 0.0
    losses_sum = abs(float(sell_trades.loc[sell_trades["realized_pnl"] < 0, "realized_pnl"].sum())) if not sell_trades.empty else 0.0
    exposure = nav["exposure"].astype(float)
    holdings = nav["holdings_count"].astype(float)
    return {
        "annual_return": annual,
        "cumulative_return": cumulative,
        "max_drawdown": float(drawdown.min()),
        "sharpe": float(returns.mean() / returns.std(ddof=0) * math.sqrt(252)) if not returns.empty and returns.std(ddof=0) > 0 else 0.0,
        "calmar": float(annual / abs(drawdown.min())) if drawdown.min() < 0 else 0.0,
        "volatility": float(returns.std(ddof=0) * math.sqrt(252)) if not returns.empty else 0.0,
        "total_trades": int(len(trades)),
        "buy_trades": int((trades["side"] == "BUY").sum()) if not trades.empty else 0,
        "sell_trades": int((trades["side"] == "SELL").sum()) if not trades.empty else 0,
        "avg_daily_exposure": float(exposure.mean()) if not exposure.empty else 0.0,
        "max_daily_exposure": float(exposure.max()) if not exposure.empty else 0.0,
        "exposure_active_days_ratio": float((exposure > 0.001).mean()) if not exposure.empty else 0.0,
        "avg_positions": float(holdings.mean()) if not holdings.empty else 0.0,
        "max_positions": int(holdings.max()) if not holdings.empty else 0,
        "turnover": float(trades["amount"].abs().sum() / initial_capital) if not trades.empty else 0.0,
        "total_fees": float(trades["fee"].sum()) if not trades.empty else 0.0,
        "total_tax": float(trades["tax"].sum()) if not trades.empty else 0.0,
        "total_slippage": float(trades["slippage_cost"].sum()) if not trades.empty else 0.0,
        "realized_pnl": realized,
        "unrealized_pnl": unrealized,
        "profit_factor": float(wins_sum / losses_sum) if losses_sum > 0 else (math.inf if wins_sum > 0 else 0.0),
    }


def _portfolio_value(cash: float, positions: dict[str, dict], price_frame: pd.DataFrame) -> float:
    value = cash
    for symbol, position in positions.items():
        if symbol in price_frame.index:
            value += float(position["shares"]) * float(price_frame.loc[symbol, "close"])
    return value


def _final_positions(positions: dict[str, dict], price_frame: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for symbol, position in positions.items():
        close = float(price_frame.loc[symbol, "close"]) if symbol in price_frame.index else 0.0
        rows.append(
            {
                "symbol": symbol,
                "bucket": position.get("bucket", ""),
                "industry": position.get("industry", ""),
                "shares": float(position["shares"]),
                "avg_cost": float(position["avg_cost"]),
                "latest_close": close,
                "market_value": float(position["shares"]) * close,
                "unrealized_pnl": float(position["shares"]) * (close - float(position["avg_cost"])),
            }
        )
    return pd.DataFrame(rows)


def _monthly_rebalance_backtest(
    control_id: str,
    features: pd.DataFrame,
    benchmark: pd.DataFrame,
    selections: dict[str, list[dict]],
    configs: dict,
    target_count_by_date: dict[str, int] | None = None,
    market_data: MonthlyMarketData | None = None,
) -> SimpleResult:
    account = configs["account"]
    strategy = configs["v2_strategy"]
    initial_capital = float(account["account"]["initial_capital"])
    fee_rate = float(account["execution"]["commission_rate"])
    tax_rate = float(account["execution"]["stamp_duty_rate_sell"])
    slippage_rate = float(account["execution"]["slippage_bps"]) / 10_000.0
    lot = int(account["execution"]["round_lot"])
    min_trade = float(account["position_sizing"]["min_trade_value"])
    market_data = market_data or _build_monthly_market_data(features)
    dates = market_data.dates
    by_date = market_data.by_date
    cash = initial_capital
    positions: dict[str, dict] = {}
    trades: list[dict] = []
    nav_rows: list[dict] = []
    rebal_dates = set(selections)
    for index in range(len(dates) - 1):
        signal_date = dates[index]
        fill_date = dates[index + 1]
        signal_frame = by_date[signal_date]
        fill_frame = by_date[fill_date]
        if signal_date in rebal_dates:
            equity = _portfolio_value(cash, positions, signal_frame)
            regime = determine_market_regime(benchmark[benchmark["date"] <= signal_date], strategy)
            selected = list(selections.get(signal_date, []))
            if target_count_by_date is not None:
                selected = selected[: max(1, int(target_count_by_date.get(signal_date, len(selected) or 1)))]
            selected = [item for item in selected if str(item["symbol"]) in fill_frame.index]
            selected_symbols = {str(item["symbol"]) for item in selected}
            max_total = float(regime["max_total_position"])
            target_weights: dict[str, float] = {}
            if selected:
                for item in selected:
                    symbol = str(item["symbol"])
                    bucket = str(item.get("bucket", ""))
                    bucket_limit = float(strategy["buckets"].get(bucket, {}).get("max_single_name_weight", account["position_sizing"]["max_single_stock_weight"]))
                    target_weights[symbol] = min(max_total / len(selected), bucket_limit)
            for symbol in list(positions):
                position_before_record = dict(positions[symbol])
                fill_open = float(fill_frame.loc[symbol, "open"]) if symbol in fill_frame.index and pd.notna(fill_frame.loc[symbol, "open"]) else float(fill_frame.loc[symbol, "close"]) if symbol in fill_frame.index else 0.0
                if fill_open <= 0:
                    continue
                target_weight = target_weights.get(symbol, 0.0)
                target_shares = _round_down_lot((target_weight * equity) / (fill_open * (1 - slippage_rate)), lot) if target_weight > 0 else 0.0
                current_shares = float(positions[symbol]["shares"])
                if target_shares >= current_shares:
                    continue
                shares = _round_down_lot(current_shares - target_shares, lot)
                if shares <= 0:
                    continue
                price = fill_open * (1 - slippage_rate)
                amount = shares * price
                if amount < min_trade and target_shares > 0:
                    continue
                fee = amount * fee_rate
                tax = amount * tax_rate
                cash_before = cash
                cash += amount - fee - tax
                realized = amount - float(positions[symbol]["avg_cost"]) * shares - fee - tax
                positions[symbol]["shares"] = current_shares - shares
                if positions[symbol]["shares"] <= 1e-9:
                    positions.pop(symbol, None)
                trades.append(_trade_row(control_id, fill_date, symbol, position_before_record, "SELL", "REBALANCE_SELL", shares, price, amount, fee, tax, fill_open, cash_before, cash, realized))
            for item in selected:
                symbol = str(item["symbol"])
                fill_open = float(fill_frame.loc[symbol, "open"]) if pd.notna(fill_frame.loc[symbol, "open"]) else float(fill_frame.loc[symbol, "close"])
                if fill_open <= 0:
                    continue
                target_weight = target_weights.get(symbol, 0.0)
                target_shares = _round_down_lot((target_weight * equity) / (fill_open * (1 + slippage_rate)), lot)
                current = positions.get(symbol)
                current_shares = float(current["shares"]) if current else 0.0
                if target_shares <= current_shares:
                    continue
                shares = _round_down_lot(target_shares - current_shares, lot)
                if shares <= 0:
                    continue
                price = fill_open * (1 + slippage_rate)
                amount = shares * price
                if amount < min_trade:
                    continue
                max_affordable = _round_down_lot(cash / max(price * (1 + fee_rate), 1e-9), lot)
                shares = min(shares, max_affordable)
                amount = shares * price
                if shares <= 0 or amount < min_trade:
                    continue
                fee = amount * fee_rate
                cash_before = cash
                cash -= amount + fee
                if current:
                    total_cost = float(current["avg_cost"]) * current_shares + amount
                    current["shares"] = current_shares + shares
                    current["avg_cost"] = total_cost / max(current["shares"], 1e-9)
                    current["bucket"] = item.get("bucket", current.get("bucket", ""))
                    current["industry"] = item.get("industry", current.get("industry", ""))
                    positions[symbol] = current
                else:
                    positions[symbol] = {"shares": shares, "avg_cost": price, "bucket": item.get("bucket", ""), "industry": item.get("industry", "")}
                trades.append(_trade_row(control_id, fill_date, symbol, positions.get(symbol), "BUY", "REBALANCE_BUY", shares, price, amount, fee, 0.0, fill_open, cash_before, cash, 0.0))
        nav = _portfolio_value(cash, positions, fill_frame)
        invested = max(0.0, nav - cash)
        nav_rows.append({"date": fill_date, "nav": nav, "cash": cash, "exposure": invested / max(nav, 1e-9), "holdings_count": len(positions)})
    nav_frame = pd.DataFrame(nav_rows)
    final = _final_positions(positions, by_date[dates[-1]])
    trade_frame = pd.DataFrame(trades)
    metrics = _simple_metrics(nav_frame, trade_frame, initial_capital, final)
    return SimpleResult(metrics=metrics, nav=nav_frame, trades_detailed=trade_frame, final_positions=final)


def _trade_row(control_id: str, date: str, symbol: str, position: dict | None, side: str, action: str, shares: float, price: float, amount: float, fee: float, tax: float, raw_price: float, cash_before: float, cash_after: float, realized: float) -> dict:
    return {
        "control_id": control_id,
        "date": date,
        "ts_code": symbol,
        "bucket": (position or {}).get("bucket", ""),
        "industry": (position or {}).get("industry", ""),
        "side": side,
        "action": action,
        "shares": shares,
        "price": price,
        "amount": amount,
        "fee": fee,
        "tax": tax,
        "slippage": abs(price - raw_price),
        "slippage_cost": abs(price - raw_price) * shares,
        "cash_before": cash_before,
        "cash_after": cash_after,
        "realized_pnl": realized,
    }


def _history_selections(history_dir: str | Path) -> dict[str, list[dict]]:
    rows: dict[str, list[dict]] = {}
    for path in sorted(resolve_path(history_dir).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        date = str(payload.get("effective_from") or path.stem)
        stocks = []
        for item in payload.get("stocks", []) or []:
            stocks.append(
                {
                    "symbol": str(item.get("symbol")),
                    "bucket": item.get("bucket"),
                    "industry": item.get("industry_l1", item.get("industry")),
                    "final_score": float(item.get("final_score", 0.0) or 0.0),
                }
            )
        rows[date] = stocks
    return rows


def _candidate_score_selections(features: pd.DataFrame, configs: dict) -> dict[str, list[dict]]:
    _, scores = build_universe_funnel(features, V2_HISTORY_DIR, configs["v2_universe"], configs["metric_map"])
    selections: dict[str, list[dict]] = {}
    if scores.empty:
        return selections
    for date, group in scores.groupby("date", sort=True):
        top = group.sort_values("final_score", ascending=False).head(min(20, len(group)))
        selections[str(date)] = [
            {
                "symbol": str(row["ts_code"]),
                "bucket": row.get("bucket", ""),
                "industry": row.get("industry", ""),
                "final_score": float(row.get("final_score", 0.0) or 0.0),
            }
            for row in top.to_dict(orient="records")
        ]
    return selections


def _random_selections(candidates: dict[str, list[dict]], seed: int, counts: dict[str, int]) -> dict[str, list[dict]]:
    rng = random.Random(seed)
    output: dict[str, list[dict]] = {}
    for date, items in candidates.items():
        pool = list(items)
        rng.shuffle(pool)
        output[date] = pool[: max(1, min(int(counts.get(date, 1)), len(pool)))]
    return output


def _row_from_result(control_id: str, profile: str, result, benchmark: pd.DataFrame, benchmark_metrics: dict) -> dict:
    if isinstance(result, BacktestResult):
        row = metrics_row(profile, "next_bar", result, benchmark)
    else:
        row = dict(result.metrics)
        row["profile"] = profile
        row["execution_mode"] = "next_bar"
        row["benchmark_annual_return"] = benchmark_metrics["benchmark_annual_return"]
        row["excess_annual_return"] = row.get("annual_return", 0.0) - benchmark_metrics["benchmark_annual_return"]
        detailed = result.trades_detailed if result.trades_detailed is not None else pd.DataFrame()
        final = result.final_positions if result.final_positions is not None else pd.DataFrame()
        row["defensive_pnl"] = _bucket_total_pnl("defensive_dividend", detailed, final)
        row["cyclical_pnl"] = _bucket_total_pnl("cyclical_rotation", detailed, final)
    row["control_id"] = control_id
    row["profile"] = profile
    row["execution_mode"] = "next_bar"
    diagnostics = result.daily_diagnostics if isinstance(result, BacktestResult) and result.daily_diagnostics is not None else pd.DataFrame()
    if diagnostics.empty:
        row["raw_signal_count"] = None
        row["executable_signal_count"] = None
    else:
        row["raw_signal_count"] = int(
            pd.to_numeric(diagnostics.get("raw_buy_signal_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
            + pd.to_numeric(diagnostics.get("raw_sell_signal_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
        )
        row["executable_signal_count"] = int(
            pd.to_numeric(diagnostics.get("executable_buy_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
            + pd.to_numeric(diagnostics.get("executable_sell_count", pd.Series(dtype=float)), errors="coerce").fillna(0).sum()
        )
    return row


def _bucket_total_pnl(bucket: str, trades: pd.DataFrame, final_positions: pd.DataFrame) -> float:
    realized = float(trades.loc[trades.get("bucket", pd.Series(dtype=object)) == bucket, "realized_pnl"].sum()) if not trades.empty else 0.0
    unrealized = float(final_positions.loc[final_positions.get("bucket", pd.Series(dtype=object)) == bucket, "unrealized_pnl"].sum()) if not final_positions.empty else 0.0
    return realized + unrealized


def _run_v2_variant(configs: dict, features: pd.DataFrame, benchmark: pd.DataFrame, control_id: str, overrides: dict | None = None, bucket: str = "combined") -> BacktestResult:
    strategy = copy.deepcopy(configs["v2_strategy"])
    if overrides:
        strategy.setdefault("control_overrides", {}).update(overrides)
    engine = BacktestEngine(
        strategy,
        universe_rules_cfg=copy.deepcopy(configs["v2_universe"]),
        account_cfg=copy.deepcopy(configs["account"]),
        historical_universe_dir=V2_HISTORY_DIR,
        execution_mode="next_bar",
    )
    return engine.run(features=features.copy(), benchmark=benchmark.copy(), bucket=bucket)


def _run_v2_custom(
    configs: dict,
    features: pd.DataFrame,
    benchmark: pd.DataFrame,
    *,
    strategy: dict | None = None,
    universe: dict | None = None,
    account: dict | None = None,
    history_dir: str | Path = V2_HISTORY_DIR,
) -> BacktestResult:
    engine = BacktestEngine(
        copy.deepcopy(strategy or configs["v2_strategy"]),
        universe_rules_cfg=copy.deepcopy(universe or configs["v2_universe"]),
        account_cfg=copy.deepcopy(account or configs["account"]),
        historical_universe_dir=history_dir,
        execution_mode="next_bar",
    )
    return engine.run(features=features.copy(), benchmark=benchmark.copy(), bucket="combined")


def _percentile(values: list[float], observed: float) -> float:
    if not values:
        return 0.0
    return sum(1 for value in values if value <= observed) / len(values) * 100.0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run combined_v2 control baselines and module ablations.")
    parser.add_argument("--refresh-all", action="store_true", help="Recompute every control result instead of reusing existing true results.")
    parser.add_argument("--refresh-placebo", action="store_true", help="Recompute random placebo metrics.")
    parser.add_argument("--placebo-seeds", type=int, default=100, help="Number of random placebo seeds when placebo is recomputed.")
    args = parser.parse_args(argv)

    configs = load_audit_configs()
    before_strategy = copy.deepcopy(configs["v2_strategy"])
    if args.refresh_all or not _history_dir_has_json(V2_HISTORY_DIR):
        prepare_v2_history(configs)
    features = load_feature_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    benchmark = load_benchmark_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    bm = _benchmark_metrics(benchmark)
    output_dir = ensure_parent("reports/backtest/controls/control_baselines_metrics.csv").parent
    metrics_path = output_dir / "control_baselines_metrics.csv"
    trades_path = output_dir / "control_baselines_trades.csv"
    existing_metrics = _load_existing_metrics(metrics_path, args.refresh_all)
    existing_ids = set(existing_metrics["control_id"].astype(str)) if not existing_metrics.empty else set()
    needed_ids = set(CONTROL_IDS) - existing_ids
    if args.refresh_all or existing_metrics.empty:
        needed_ids = set(CONTROL_IDS)
    print(f"[controls] needed={sorted(needed_ids) if needed_ids else 'none'}", flush=True)

    results: dict[str, object] = {}
    if "baseline_combined_next_bar" in needed_ids:
        results["baseline_combined_next_bar"] = _run_step(
            "baseline_combined_next_bar",
            lambda: run_profile("baseline", features, benchmark, configs, execution_mode="next_bar"),
        )
    if "combined_v2_next_bar" in needed_ids:
        results["combined_v2_next_bar"] = _run_step(
            "combined_v2_next_bar",
            lambda: run_profile("combined_v2", features, benchmark, configs, execution_mode="next_bar"),
        )

    needs_monthly = bool(
        needed_ids
        & {
            "v2_universe_equal_weight_monthly",
            "v2_top_score_monthly",
        }
    )
    needs_candidates = bool(needed_ids & {"v2_top_score_monthly"}) or args.refresh_placebo
    needs_history = needs_monthly or args.refresh_placebo
    market_data = _build_monthly_market_data(features) if needs_monthly or args.refresh_placebo else None
    history = _history_selections(V2_HISTORY_DIR) if needs_history else {}
    candidates = _candidate_score_selections(features, configs) if needs_candidates else {}
    top_score = {date: items[: min(20, len(items))] for date, items in candidates.items()}
    holdings_counts = {}
    if needs_monthly or args.refresh_placebo:
        if "combined_v2_next_bar" in results:
            v2_nav = results["combined_v2_next_bar"].nav
            avg_positions = max(1, int(round(float(results["combined_v2_next_bar"].metrics.get("avg_positions", 1)))))
        else:
            existing_v2 = existing_metrics[existing_metrics["control_id"].astype(str) == "combined_v2_next_bar"]
            avg_positions = max(1, int(round(float(existing_v2["avg_positions"].iloc[0])))) if not existing_v2.empty else 1
            v2_nav = pd.DataFrame()
        for date in history:
            future_nav = v2_nav[v2_nav["date"] >= date] if not v2_nav.empty else pd.DataFrame()
            holdings_counts[date] = int(future_nav["holdings_count"].iloc[0]) if not future_nav.empty else avg_positions
    if "v2_universe_equal_weight_monthly" in needed_ids:
        results["v2_universe_equal_weight_monthly"] = _run_step(
            "v2_universe_equal_weight_monthly",
            lambda: _monthly_rebalance_backtest("v2_universe_equal_weight_monthly", features, benchmark, history, configs, market_data=market_data),
        )
    if "v2_top_score_monthly" in needed_ids:
        results["v2_top_score_monthly"] = _run_step(
            "v2_top_score_monthly",
            lambda: _monthly_rebalance_backtest("v2_top_score_monthly", features, benchmark, top_score or history, configs, market_data=market_data),
        )
    if "v2_defensive_only" in needed_ids:
        results["v2_defensive_only"] = _run_step("v2_defensive_only", lambda: _run_v2_variant(configs, features, benchmark, "v2_defensive_only", bucket="defensive_dividend"))
    if "v2_cyclical_only" in needed_ids:
        results["v2_cyclical_only"] = _run_step("v2_cyclical_only", lambda: _run_v2_variant(configs, features, benchmark, "v2_cyclical_only", bucket="cyclical_rotation"))
    if "v2_no_high_dividend_supplement" in needed_ids:
        results["v2_no_high_dividend_supplement"] = _run_step("v2_no_high_dividend_supplement", lambda: _run_v2_variant(configs, features, benchmark, "v2_no_high_dividend_supplement", {"disable_high_dividend_supplement": True}))
    if "v2_no_grid" in needed_ids:
        results["v2_no_grid"] = _run_step("v2_no_grid", lambda: _run_v2_variant(configs, features, benchmark, "v2_no_grid", {"disable_grid": True}))
    if "v2_no_trend_stop" in needed_ids:
        results["v2_no_trend_stop"] = _run_step("v2_no_trend_stop", lambda: _run_v2_variant(configs, features, benchmark, "v2_no_trend_stop", {"disable_trend_stop": True}))
    if "v2_risk_off_no_new_buy" in needed_ids:
        results["v2_risk_off_no_new_buy"] = _run_step("v2_risk_off_no_new_buy", lambda: _run_v2_variant(configs, features, benchmark, "v2_risk_off_no_new_buy", {"risk_off_no_new_buy": True}))
    if "v2_no_market_state_filter" in needed_ids:
        no_market_strategy = copy.deepcopy(configs["v2_strategy"])
        no_market_strategy.setdefault("control_overrides", {})["research_only_no_market_state_filter"] = True
        no_market_strategy["market_regime"]["max_total_position"] = {"risk_on": 0.95, "neutral": 0.95, "risk_off": 0.95}
        no_market_strategy["market_regime"]["block_new_in_risk_off"] = False
        results["v2_no_market_state_filter"] = _run_step(
            "v2_no_market_state_filter",
            lambda: _run_v2_custom(configs, features, benchmark, strategy=no_market_strategy),
        )

    if "v2_relaxed_account_constraints_research_only" in needed_ids:
        relaxed_account = copy.deepcopy(configs["account"])
        relaxed_account.setdefault("position_sizing", {})["min_trade_value"] = 0
        relaxed_account.setdefault("execution", {})["round_lot"] = 1
        relaxed_strategy = copy.deepcopy(configs["v2_strategy"])
        relaxed_strategy.setdefault("control_overrides", {})["research_only_relaxed_account_constraints"] = True
        relaxed_strategy.setdefault("execution", {})["max_positions"] = 999
        relaxed_strategy.setdefault("execution", {})["max_new_positions_per_day"] = 999
        relaxed_strategy.setdefault("execution", {})["max_adds_per_day"] = 999
        results["v2_relaxed_account_constraints_research_only"] = _run_step(
            "v2_relaxed_account_constraints_research_only",
            lambda: _run_v2_custom(
                configs,
                features,
                benchmark,
                strategy=relaxed_strategy,
                account=relaxed_account,
            ),
        )

    if "v2_no_industry_cap" in needed_ids:
        no_industry_universe = copy.deepcopy(configs["v2_universe"])
        no_industry_universe["max_per_industry"] = 999
        no_industry_universe["max_names_per_industry"] = 999
        no_industry_history = "reports/backtest/controls/no_industry_cap_universe_history"
        generation_start = _history_generation_start("data/curated/universe_history", DEFAULT_START_DATE, DEFAULT_END_DATE)
        generation_features = load_feature_window(generation_start, DEFAULT_END_DATE, DEFAULT_FEATURES_FILE)
        results["v2_no_industry_cap"] = _run_step(
            "v2_no_industry_cap",
            lambda: (
                _generate_v2_history(generation_features, "data/curated/universe_history", no_industry_history, no_industry_universe, configs["metric_map"]),
                _run_v2_custom(
                    configs,
                    features,
                    benchmark,
                    universe=no_industry_universe,
                    history_dir=no_industry_history,
                ),
            )[1],
        )

    rows = existing_metrics[~existing_metrics["control_id"].astype(str).isin(results)] .to_dict(orient="records") if not existing_metrics.empty else []
    trades_frames = []
    existing_trades = _load_existing_trades(trades_path, args.refresh_all)
    if not existing_trades.empty and "control_id" in existing_trades.columns:
        trades_frames.append(existing_trades[~existing_trades["control_id"].astype(str).isin(results)].copy())
    for control_id, result in results.items():
        profile = "baseline" if control_id == "baseline_combined_next_bar" else "combined_v2"
        row = _row_from_result(control_id, profile, result, benchmark, bm)
        rows.append(row)
        detailed = result.trades_detailed.copy() if result.trades_detailed is not None else pd.DataFrame()
        if not detailed.empty:
            if "control_id" in detailed.columns:
                detailed["control_id"] = control_id
            else:
                detailed.insert(0, "control_id", control_id)
            trades_frames.append(detailed)
    columns = [
        "control_id",
        "profile",
        "execution_mode",
        "annual_return",
        "cumulative_return",
        "max_drawdown",
        "sharpe",
        "calmar",
        "volatility",
        "total_trades",
        "buy_trades",
        "sell_trades",
        "avg_daily_exposure",
        "max_daily_exposure",
        "avg_positions",
        "max_positions",
        "turnover",
        "raw_signal_count",
        "executable_signal_count",
        "total_fees",
        "total_tax",
        "total_slippage",
        "realized_pnl",
        "unrealized_pnl",
        "benchmark_annual_return",
        "excess_annual_return",
        "defensive_pnl",
        "cyclical_pnl",
    ]
    metrics = pd.DataFrame(rows).reindex(columns=columns)
    metrics.to_csv(output_dir / "control_baselines_metrics.csv", index=False)
    if trades_frames:
        pd.concat(trades_frames, ignore_index=True).to_csv(output_dir / "control_baselines_trades.csv", index=False)
    else:
        pd.DataFrame().to_csv(output_dir / "control_baselines_trades.csv", index=False)

    random_path = output_dir / "random_placebo_metrics.csv"
    if random_path.exists() and not args.refresh_placebo and not args.refresh_all:
        random_output = pd.read_csv(random_path)
        random_frame = random_output[random_output.get("row_type", pd.Series(dtype=str)).astype(str) == "seed"].copy()
        summary_stats = random_output[random_output.get("row_type", pd.Series(dtype=str)).astype(str) == "summary"].to_dict(orient="records")
    else:
        random_rows = []
        if not history:
            history = _history_selections(V2_HISTORY_DIR)
        if not candidates:
            candidates = _candidate_score_selections(features, configs)
        if market_data is None:
            market_data = _build_monthly_market_data(features)
        random_source = candidates or history
        seeds = list(range(args.placebo_seeds))
        for seed in seeds:
            selection = _random_selections(random_source, seed, holdings_counts)
            random_result = _monthly_rebalance_backtest(f"random_placebo_seed_{seed}", features, benchmark, selection, configs, holdings_counts, market_data=market_data)
            row = _row_from_result(f"random_placebo_seed_{seed}", "random_placebo_from_v2_candidate_pool", random_result, benchmark, bm)
            row["seed"] = seed
            row["row_type"] = "seed"
            random_rows.append(row)
        random_frame = pd.DataFrame(random_rows)
        summary_stats = []
        for stat, func in (
            ("mean", lambda s: s.mean()),
            ("median", lambda s: s.median()),
            ("p5", lambda s: s.quantile(0.05)),
            ("p25", lambda s: s.quantile(0.25)),
            ("p75", lambda s: s.quantile(0.75)),
            ("p95", lambda s: s.quantile(0.95)),
        ):
            item = {"row_type": "summary", "seed": stat, "control_id": f"random_placebo_{stat}", "profile": "random_placebo_from_v2_candidate_pool", "execution_mode": "next_bar"}
            for column in ["annual_return", "max_drawdown", "sharpe", "cumulative_return", "total_trades", "avg_daily_exposure", "avg_positions"]:
                item[column] = float(func(random_frame[column]))
            summary_stats.append(item)
        random_output = pd.concat([random_frame, pd.DataFrame(summary_stats)], ignore_index=True, sort=False)
        random_output.to_csv(random_path, index=False)

    assert configs["v2_strategy"] == before_strategy
    v2 = metrics[metrics["control_id"] == "combined_v2_next_bar"].iloc[0]
    placebo_percentile = _percentile(random_frame["annual_return"].astype(float).tolist(), float(v2["annual_return"]))
    universe = metrics[metrics["control_id"] == "v2_universe_equal_weight_monthly"].iloc[0]
    top = metrics[metrics["control_id"] == "v2_top_score_monthly"].iloc[0]
    defensive = metrics[metrics["control_id"] == "v2_defensive_only"].iloc[0]
    cyclical = metrics[metrics["control_id"] == "v2_cyclical_only"].iloc[0]
    no_div = metrics[metrics["control_id"] == "v2_no_high_dividend_supplement"].iloc[0]
    no_grid = metrics[metrics["control_id"] == "v2_no_grid"].iloc[0]
    no_stop = metrics[metrics["control_id"] == "v2_no_trend_stop"].iloc[0]
    no_risk_buy = metrics[metrics["control_id"] == "v2_risk_off_no_new_buy"].iloc[0]
    no_market = metrics[metrics["control_id"] == "v2_no_market_state_filter"].iloc[0]
    no_industry = metrics[metrics["control_id"] == "v2_no_industry_cap"].iloc[0]
    relaxed_account_metrics = metrics[metrics["control_id"] == "v2_relaxed_account_constraints_research_only"].iloc[0]
    baseline = metrics[metrics["control_id"] == "baseline_combined_next_bar"].iloc[0]
    comparison_rows = []
    label_map = {
        "baseline_combined_next_bar": "base_dianjinshu_like",
        "combined_v2_next_bar": "combined_v2",
        "v2_no_high_dividend_supplement": "no_high_dividend_supplement",
        "v2_no_trend_stop": "no_trend_stop",
        "v2_no_market_state_filter": "no_market_state_filter",
        "v2_no_industry_cap": "no_industry_cap",
        "v2_relaxed_account_constraints_research_only": "relaxed_account_constraints_research_only",
    }
    for row in metrics.to_dict(orient="records"):
        if row["control_id"] not in label_map:
            continue
        comparison = dict(row)
        comparison["comparison_id"] = label_map[row["control_id"]]
        comparison["research_only"] = comparison["comparison_id"] in {
            "no_market_state_filter",
            "no_industry_cap",
            "relaxed_account_constraints_research_only",
        }
        comparison["baseline_note"] = (
            "仓库配置中定义的点金术风格基线，不是对外部作者原文的严格复刻。"
            if comparison["comparison_id"] == "base_dianjinshu_like"
            else ""
        )
        comparison["module_flag"] = (
            "MODULE_MAY_BE_DRAG"
            if comparison["comparison_id"].startswith("no_")
            and float(comparison.get("annual_return", 0.0)) > float(v2["annual_return"])
            else ""
        )
        comparison_rows.append(comparison)
    baseline_cfg = load_yaml_optional("config/baselines/dianjinshu_like.yml")
    missing_required = [
        key
        for key, value in (baseline_cfg.get("required_params", {}) or {}).items()
        if value is None and key not in {"market_cap_rank"}
    ]
    baseline_status = "FAIL" if missing_required else "WARN" if any(row.get("module_flag") for row in comparison_rows) else "PASS"
    write_json(
        output_dir / "baseline_comparison.json",
        {
            **metadata_header(extra_config_paths=["config/baselines/dianjinshu_like.yml"]),
            "status": baseline_status,
            "baseline_source": "documented_dianjinshu_like_baseline",
            "strict_external_original_reproduction": False,
            "missing_required_baseline_params": missing_required,
            "comparisons": comparison_rows,
        },
    )
    lines = [
        "# control baselines 报告",
        "",
        "- 口径: 2023-04-03 到 2026-04-03，next_bar，统一账户、费用、印花税、滑点、整手和最小成交额。",
        "- 本脚本只使用配置副本，不写回 `config/strategy_v2.yml` 或 `config/universe_rules_v2.yml`。",
        "",
        "## 关键结论",
        "",
        f"- combined_v2 是否显著优于原 baseline next_bar: {'是' if float(v2['annual_return']) > float(baseline['annual_return']) else '否'}；v2 年化 {pct(v2['annual_return'])}，baseline 年化 {pct(baseline['annual_return'])}。",
        f"- combined_v2 是否优于 v2_universe_equal_weight_monthly: {'是' if float(v2['annual_return']) > float(universe['annual_return']) else '否'}；equal weight 年化 {pct(universe['annual_return'])}。",
        f"- combined_v2 是否优于 v2_top_score_monthly: {'是' if float(v2['annual_return']) > float(top['annual_return']) else '否'}；top score 年化 {pct(top['annual_return'])}。",
        f"- 收益主要来自股票池本身还是交易信号: {'交易信号贡献更明显' if float(v2['annual_return']) > max(float(universe['annual_return']), float(top['annual_return'])) else '股票池/排序本身解释力较强，需要谨慎'}。",
        f"- defensive_only vs cyclical_only: defensive 年化 {pct(defensive['annual_return'])}、回撤 {pct(defensive['max_drawdown'])}；cyclical 年化 {pct(cyclical['annual_return'])}、回撤 {pct(cyclical['max_drawdown'])}。",
        f"- 高股息补充触发是否贡献主要收益: 禁用后年化 {pct(no_div['annual_return'])}，相对 v2 变化 {pct(float(no_div['annual_return']) - float(v2['annual_return']))}。",
        f"- 网格是否有实际贡献: 禁用后年化 {pct(no_grid['annual_return'])}，成交 {int(no_grid['total_trades'])}；若与 v2 接近，说明当前 GRID_ADD/GRID_TRIM 贡献有限。",
        f"- trend_stop 是保护还是拖累: 禁用后年化 {pct(no_stop['annual_return'])}、回撤 {pct(no_stop['max_drawdown'])}；该项只作风险解释，不能作为主策略。",
        f"- risk_off 新买入是否值得保留: risk_off 禁新买后年化 {pct(no_risk_buy['annual_return'])}、回撤 {pct(no_risk_buy['max_drawdown'])}。",
        f"- no_market_state_filter 仅研究用途: 年化 {pct(no_market['annual_return'])}、回撤 {pct(no_market['max_drawdown'])}，不能作为实盘口径。",
        f"- no_industry_cap 仅研究用途: 年化 {pct(no_industry['annual_return'])}、回撤 {pct(no_industry['max_drawdown'])}，不能作为实盘口径。",
        f"- relaxed_account_constraints 仅研究用途: 年化 {pct(relaxed_account_metrics['annual_return'])}、回撤 {pct(relaxed_account_metrics['max_drawdown'])}，不能作为实盘口径。",
        f"- combined_v2 在 random placebo 年化分布中的 percentile: {placebo_percentile:.1f}%。",
        "",
        "## 指标明细",
        "",
    ]
    for row in metrics.to_dict(orient="records"):
        lines.append(
            f"- {row['control_id']}: 年化 {pct(row['annual_return'])}，累计 {pct(row['cumulative_return'])}，回撤 {pct(row['max_drawdown'])}，夏普 {row['sharpe']:.2f}，成交 {int(row['total_trades'])}，平均仓位 {pct(row['avg_daily_exposure'])}"
        )
    lines.extend(["", "## random placebo 分布", ""])
    for row in summary_stats:
        lines.append(f"- {row['seed']}: 年化 {pct(row['annual_return'])}，最大回撤 {pct(row['max_drawdown'])}，夏普 {row['sharpe']:.2f}")
    (output_dir / "control_baselines_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    comparison_lines = [
        "# baseline comparison",
        "",
        f"- status: {baseline_status}",
        "- base_dianjinshu_like: 仓库配置中定义的点金术风格基线，不是对外部作者原文的严格复刻。",
        "- combined_v2: 当前主研究候选。",
        "- 所有 no_* 和 relaxed_account_constraints 仅用于解释模块贡献，不自动修改主策略。",
        "",
        "## metrics",
        "",
    ]
    for row in comparison_rows:
        flag = f" | {row['module_flag']}" if row.get("module_flag") else ""
        comparison_lines.append(
            f"- {row['comparison_id']}: 年化 {pct(row['annual_return'])}，累计 {pct(row['cumulative_return'])}，回撤 {pct(row['max_drawdown'])}，Sharpe {row['sharpe']:.2f}，Calmar {row['calmar']:.2f}，turnover {row['turnover']:.2f}，平均仓位 {pct(row['avg_daily_exposure'])}，成交 {int(row['total_trades'])}，raw/executable {row.get('raw_signal_count')} / {row.get('executable_signal_count')}，超额 {pct(row['excess_annual_return'])}{flag}"
        )
    if missing_required:
        comparison_lines.extend(["", "## missing_required_baseline_params", ""])
        comparison_lines.extend([f"- {item}" for item in missing_required])
    (output_dir / "baseline_comparison.md").write_text("\n".join(comparison_lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
