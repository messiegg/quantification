#!/usr/bin/env python3
from __future__ import annotations

import math
import sys
from collections import defaultdict
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_common import (
    DEFAULT_END_DATE,
    DEFAULT_START_DATE,
    ensure_parent,
    load_audit_configs,
    load_benchmark_window,
    load_feature_window,
    metrics_row,
    pct,
    prepare_v2_history,
    run_profile,
)
from src.strategy.regime import determine_market_regime


def _holding_bucket(days: float) -> str:
    if days <= 20:
        return "0-20"
    if days <= 60:
        return "21-60"
    if days <= 120:
        return "61-120"
    return "120+"


def _safe_div(num: float, den: float) -> float:
    return float(num) / float(den) if abs(float(den)) > 1e-12 else 0.0


def _profit_factor(values: list[float]) -> float:
    wins = sum(value for value in values if value > 0)
    losses = abs(sum(value for value in values if value < 0))
    if losses > 0:
        return wins / losses
    return math.inf if wins > 0 else 0.0


def _trade_dates(features: pd.DataFrame) -> list[str]:
    return sorted(features["date"].astype(str).unique())


def _days_between(calendar: list[str], start_date: str, end_date: str) -> int:
    if not start_date or not end_date:
        return 0
    return int(sum(1 for date in calendar if start_date <= date <= end_date))


def build_monthly_returns(nav: pd.DataFrame, initial_capital: float) -> tuple[pd.DataFrame, pd.DataFrame]:
    frame = nav.copy()
    frame["date"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["month"] = frame["date"].dt.strftime("%Y-%m")
    grouped = (
        frame.groupby("month", as_index=False)
        .agg(
            period_end_date=("date", "max"),
            month_end_nav=("nav", "last"),
            avg_exposure=("exposure", "mean"),
            max_exposure=("exposure", "max"),
            avg_holdings_count=("holdings_count", "mean"),
        )
        .sort_values("period_end_date")
    )
    prev_navs = [float(initial_capital)] + grouped["month_end_nav"].astype(float).iloc[:-1].tolist()
    grouped["prev_month_end_nav"] = prev_navs
    grouped["monthly_return"] = grouped["month_end_nav"].astype(float) / grouped["prev_month_end_nav"].astype(float) - 1.0
    grouped["cumulative_return_from_monthly_chain"] = (1.0 + grouped["monthly_return"]).cumprod() - 1.0
    grouped["cumulative_return_from_nav"] = grouped["month_end_nav"].astype(float) / float(initial_capital) - 1.0
    grouped["diff"] = grouped["cumulative_return_from_monthly_chain"] - grouped["cumulative_return_from_nav"]
    grouped["period_end_date"] = grouped["period_end_date"].dt.strftime("%Y-%m-%d")
    monthly = grouped[
        [
            "month",
            "period_end_date",
            "prev_month_end_nav",
            "month_end_nav",
            "monthly_return",
            "avg_exposure",
            "max_exposure",
            "avg_holdings_count",
            "cumulative_return_from_monthly_chain",
            "cumulative_return_from_nav",
            "diff",
        ]
    ].copy()
    return monthly, monthly.copy()


def _price_lookup(features: pd.DataFrame) -> dict[tuple[str, str], dict]:
    columns = ["date", "symbol", "close", "industry", "bucket", "name"]
    available = [column for column in columns if column in features.columns]
    return {
        (str(row["date"]), str(row["symbol"])): row
        for row in features[available].to_dict(orient="records")
    }


def _daily_position_values(result, features: pd.DataFrame) -> pd.DataFrame:
    trades = result.trades_detailed.copy() if result.trades_detailed is not None else pd.DataFrame()
    nav = result.nav.copy()
    if nav.empty:
        return pd.DataFrame()
    prices = _price_lookup(features)
    trades_by_date = {date: group.copy() for date, group in trades.groupby("date")} if not trades.empty else {}
    positions: dict[str, dict] = {}
    rows: list[dict] = []
    nav_by_date = nav.set_index("date")["nav"].astype(float).to_dict()
    for date in nav["date"].astype(str).tolist():
        if date in trades_by_date:
            for trade in trades_by_date[date].to_dict(orient="records"):
                symbol = str(trade["ts_code"])
                shares = float(trade.get("position_after", 0.0))
                if shares <= 1e-9:
                    positions.pop(symbol, None)
                else:
                    positions[symbol] = {
                        "shares": shares,
                        "bucket": trade.get("bucket", ""),
                        "industry": trade.get("industry", ""),
                        "name": trade.get("name", symbol),
                    }
        nav_value = max(float(nav_by_date.get(date, 0.0)), 1e-9)
        for symbol, position in positions.items():
            price_row = prices.get((date, symbol), {})
            close = float(price_row.get("close", 0.0) or 0.0)
            market_value = float(position["shares"]) * close
            rows.append(
                {
                    "date": date,
                    "symbol": symbol,
                    "bucket": position.get("bucket") or price_row.get("bucket", ""),
                    "industry": position.get("industry") or price_row.get("industry", ""),
                    "name": position.get("name") or price_row.get("name", symbol),
                    "shares": float(position["shares"]),
                    "close": close,
                    "market_value": market_value,
                    "weight": market_value / nav_value,
                }
            )
    return pd.DataFrame(rows)


def build_position_attribution(
    trades: pd.DataFrame,
    final_positions: pd.DataFrame,
    features: pd.DataFrame,
    calendar: list[str],
) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    final_symbols = set(final_positions["symbol"].astype(str)) if final_positions is not None and not final_positions.empty else set()
    price_rows = _price_lookup(features)
    rows: list[dict] = []
    total_pnl = 0.0
    for symbol, group in trades.sort_values(["date"]).groupby("ts_code", sort=True):
        symbol = str(symbol)
        buys = group[group["side"] == "BUY"]
        sells = group[group["side"] == "SELL"]
        final = final_positions[final_positions["symbol"].astype(str) == symbol] if final_positions is not None and not final_positions.empty else pd.DataFrame()
        realized = float(pd.to_numeric(group["realized_pnl"], errors="coerce").fillna(0.0).sum())
        unrealized = float(final["unrealized_pnl"].sum()) if not final.empty and "unrealized_pnl" in final else 0.0
        total = realized + unrealized
        total_pnl += total
        intervals: list[tuple[str, str, bool]] = []
        open_start = ""
        last_position_after = 0.0
        for trade in group.to_dict(orient="records"):
            date = str(trade["date"])
            before = float(trade.get("position_before", 0.0) or 0.0)
            after = float(trade.get("position_after", 0.0) or 0.0)
            if before <= 1e-9 and after > 1e-9:
                open_start = date
            if before > 1e-9 and after <= 1e-9 and open_start:
                intervals.append((open_start, date, False))
                open_start = ""
            last_position_after = after
        is_open = symbol in final_symbols or last_position_after > 1e-9
        if is_open and open_start:
            intervals.append((open_start, DEFAULT_END_DATE, True))
        realized_days = sum(_days_between(calendar, start, end) for start, end, is_open_interval in intervals if not is_open_interval)
        open_days = sum(_days_between(calendar, start, end) for start, end, is_open_interval in intervals if is_open_interval)
        total_days = realized_days + open_days
        first_buy = str(buys["date"].min()) if not buys.empty else ""
        last_sell = str(sells["date"].max()) if not sells.empty else ""
        latest_price = price_rows.get((DEFAULT_END_DATE, symbol), {})
        avg_cost = float(final["avg_cost"].iloc[0]) if not final.empty else float(pd.to_numeric(buys["price"], errors="coerce").mean()) if not buys.empty else 0.0
        max_drawdown = _max_drawdown_while_held(features, symbol, intervals, avg_cost)
        rows.append(
            {
                "ts_code": symbol,
                "name": group["name"].dropna().iloc[-1] if group["name"].notna().any() else latest_price.get("name", symbol),
                "bucket": group["bucket"].dropna().iloc[-1] if group["bucket"].notna().any() else latest_price.get("bucket", ""),
                "industry": group["industry"].dropna().iloc[-1] if group["industry"].notna().any() else latest_price.get("industry", ""),
                "total_trades": int(len(group)),
                "buy_count": int((group["side"] == "BUY").sum()),
                "sell_count": int((group["side"] == "SELL").sum()),
                "first_buy_date": first_buy,
                "last_sell_date": last_sell,
                "is_open_position": bool(is_open),
                "open_position_days": int(open_days),
                "realized_holding_days": int(realized_days),
                "total_holding_days_to_end": int(total_days),
                "holding_days_total": int(total_days),
                "realized_pnl": realized,
                "unrealized_pnl": unrealized,
                "total_pnl": total,
                "contribution_pct_of_total_pnl": 0.0,
                "max_single_position_weight": float(pd.to_numeric(group["weight_after"], errors="coerce").max()),
                "max_drawdown_while_held": max_drawdown,
            }
        )
    frame = pd.DataFrame(rows)
    if not frame.empty and abs(total_pnl) > 1e-9:
        frame["contribution_pct_of_total_pnl"] = frame["total_pnl"] / total_pnl
    return frame


def _max_drawdown_while_held(features: pd.DataFrame, symbol: str, intervals: list[tuple[str, str, bool]], avg_cost: float) -> float:
    if avg_cost <= 0 or not intervals:
        return 0.0
    pieces = []
    for start, end, _ in intervals:
        subset = features[(features["symbol"].astype(str) == symbol) & (features["date"] >= start) & (features["date"] <= end)]
        if not subset.empty:
            pieces.append(subset[["date", "close"]])
    if not pieces:
        return 0.0
    close = pd.concat(pieces)["close"].astype(float)
    return float(close.min() / avg_cost - 1.0)


def _lot_events(trades: pd.DataFrame, final_positions: pd.DataFrame, calendar: list[str]) -> list[dict]:
    events: list[dict] = []
    if trades.empty:
        return events
    final_map = (
        final_positions.set_index("symbol").to_dict(orient="index")
        if final_positions is not None and not final_positions.empty and "symbol" in final_positions
        else {}
    )
    for symbol, group in trades.sort_values("date").groupby("ts_code", sort=True):
        lots: list[dict] = []
        for trade in group.to_dict(orient="records"):
            if trade["side"] == "BUY":
                lots.append(
                    {
                        "entry_signal_level": str(trade.get("signal_level") or trade.get("action") or "BUY"),
                        "entry_date": str(trade["date"]),
                        "shares": float(trade["shares"]),
                        "entry_price": float(trade["price"]),
                    }
                )
                continue
            sell_shares = max(float(trade.get("shares", 0.0) or 0.0), 1e-9)
            remaining = sell_shares
            for lot in lots:
                if remaining <= 1e-9:
                    break
                used = min(float(lot["shares"]), remaining)
                if used <= 1e-9:
                    continue
                lot["shares"] = float(lot["shares"]) - used
                remaining -= used
                portion = used / sell_shares
                pnl = float(trade.get("realized_pnl", 0.0) or 0.0) * portion
                events.append(
                    {
                        "ts_code": symbol,
                        "bucket": trade.get("bucket", ""),
                        "industry": trade.get("industry", ""),
                        "entry_signal_level": lot["entry_signal_level"],
                        "exit_action": trade.get("action", ""),
                        "exit_reason": trade.get("exit_reason", ""),
                        "realized_pnl": pnl,
                        "unrealized_pnl": 0.0,
                        "total_pnl": pnl,
                        "holding_days": _days_between(calendar, lot["entry_date"], str(trade["date"])),
                        "is_open": False,
                    }
                )
        open_lots = [lot for lot in lots if float(lot["shares"]) > 1e-9]
        final = final_map.get(str(symbol), {})
        total_open_shares = sum(float(lot["shares"]) for lot in open_lots)
        total_unrealized = float(final.get("unrealized_pnl", 0.0) or 0.0)
        for lot in open_lots:
            share = _safe_div(float(lot["shares"]), total_open_shares)
            pnl = total_unrealized * share
            events.append(
                {
                    "ts_code": symbol,
                    "bucket": final.get("bucket", group["bucket"].dropna().iloc[-1] if group["bucket"].notna().any() else ""),
                    "industry": final.get("industry", group["industry"].dropna().iloc[-1] if group["industry"].notna().any() else ""),
                    "entry_signal_level": lot["entry_signal_level"],
                    "exit_action": "OPEN",
                    "exit_reason": "open_position",
                    "realized_pnl": 0.0,
                    "unrealized_pnl": pnl,
                    "total_pnl": pnl,
                    "holding_days": _days_between(calendar, lot["entry_date"], DEFAULT_END_DATE),
                    "is_open": True,
                }
            )
    return events


def _aggregate_signal_events(events: list[dict], group_cols: list[str], attribution_type: str) -> pd.DataFrame:
    if not events:
        return pd.DataFrame()
    frame = pd.DataFrame(events)
    rows = []
    for keys, group in frame.groupby(group_cols, dropna=False):
        if not isinstance(keys, tuple):
            keys = (keys,)
        values = group["total_pnl"].astype(float).tolist()
        row = {column: key for column, key in zip(group_cols, keys, strict=True)}
        row.update(
            {
                "attribution_type": attribution_type,
                "trade_count": int(len(group)),
                "realized_pnl": float(group["realized_pnl"].sum()),
                "unrealized_pnl": float(group["unrealized_pnl"].sum()),
                "total_pnl": float(group["total_pnl"].sum()),
                "avg_holding_days": float(group["holding_days"].mean()) if not group.empty else 0.0,
                "win_rate": float((group["total_pnl"] > 0).mean()) if not group.empty else 0.0,
                "avg_win": float(group.loc[group["total_pnl"] > 0, "total_pnl"].mean()) if (group["total_pnl"] > 0).any() else 0.0,
                "avg_loss": float(group.loc[group["total_pnl"] < 0, "total_pnl"].mean()) if (group["total_pnl"] < 0).any() else 0.0,
                "profit_factor": _profit_factor(values),
            }
        )
        rows.append(row)
    return pd.DataFrame(rows)


def build_signal_attribution(trades: pd.DataFrame, final_positions: pd.DataFrame, calendar: list[str]) -> pd.DataFrame:
    events = _lot_events(trades, final_positions, calendar)
    frames = [
        _aggregate_signal_events(events, ["entry_signal_level"], "entry_signal"),
        _aggregate_signal_events([event for event in events if not event["is_open"]], ["exit_action", "exit_reason"], "exit_signal"),
        _aggregate_signal_events(events, ["entry_signal_level", "exit_action", "exit_reason"], "entry_exit_pair"),
    ]
    frame = pd.concat([item for item in frames if not item.empty], ignore_index=True) if any(not item.empty for item in frames) else pd.DataFrame()
    columns = [
        "attribution_type",
        "entry_signal_level",
        "exit_action",
        "exit_reason",
        "trade_count",
        "realized_pnl",
        "unrealized_pnl",
        "total_pnl",
        "avg_holding_days",
        "win_rate",
        "avg_win",
        "avg_loss",
        "profit_factor",
    ]
    for column in columns:
        if column not in frame.columns:
            frame[column] = ""
    return frame[columns]


def build_daily_regime_attribution(
    result,
    features: pd.DataFrame,
    benchmark: pd.DataFrame,
    strategy_cfg: dict,
    initial_capital: float,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    nav = result.nav.copy()
    trades = result.trades_detailed.copy() if result.trades_detailed is not None else pd.DataFrame()
    daily_positions = _daily_position_values(result, features)
    if nav.empty:
        return pd.DataFrame(), pd.DataFrame()
    trades_by_date = {date: group.copy() for date, group in trades.groupby("date")} if not trades.empty else {}
    bucket_value = (
        daily_positions.groupby(["date", "bucket"], as_index=False)["market_value"].sum()
        if not daily_positions.empty
        else pd.DataFrame(columns=["date", "bucket", "market_value"])
    )
    rows: list[dict] = []
    prev_nav = initial_capital
    for item in nav.to_dict(orient="records"):
        date = str(item["date"])
        after = float(item["nav"])
        daily_pnl = after - prev_nav
        daily_return = _safe_div(daily_pnl, prev_nav)
        benchmark_until_today = benchmark[benchmark["date"] <= date]
        market_regime = determine_market_regime(benchmark_until_today, strategy_cfg)["regime"] if not benchmark_until_today.empty else ""
        day_trades = trades_by_date.get(date, pd.DataFrame())
        realized = float(day_trades["realized_pnl"].sum()) if not day_trades.empty else 0.0
        fees = float(day_trades["fee"].sum()) if not day_trades.empty else 0.0
        tax = float(day_trades["tax"].sum()) if not day_trades.empty else 0.0
        slippage = float(day_trades["slippage_cost"].sum()) if not day_trades.empty else 0.0
        values_today = bucket_value[bucket_value["date"] == date]
        invested = float(values_today["market_value"].sum()) if not values_today.empty else 0.0
        defensive_weight = _safe_div(float(values_today.loc[values_today["bucket"] == "defensive_dividend", "market_value"].sum()), invested)
        cyclical_weight = _safe_div(float(values_today.loc[values_today["bucket"] == "cyclical_rotation", "market_value"].sum()), invested)
        rows.append(
            {
                "date": date,
                "market_regime": market_regime,
                "nav_before": prev_nav,
                "nav_after": after,
                "daily_pnl": daily_pnl,
                "daily_return": daily_return,
                "exposure": float(item.get("exposure", 0.0)),
                "holdings_count": int(item.get("holdings_count", 0)),
                "defensive_daily_pnl": daily_pnl * defensive_weight,
                "cyclical_daily_pnl": daily_pnl * cyclical_weight,
                "realized_pnl_today": realized,
                "unrealized_pnl_today": daily_pnl - realized,
                "fees_today": fees,
                "tax_today": tax,
                "slippage_today": slippage,
                "trade_count": int(len(day_trades)),
                "buy_count": int((day_trades["side"] == "BUY").sum()) if not day_trades.empty else 0,
                "sell_count": int((day_trades["side"] == "SELL").sum()) if not day_trades.empty else 0,
            }
        )
        prev_nav = after
    daily = pd.DataFrame(rows)
    summary_rows = []
    for regime, group in daily.groupby("market_regime", sort=True):
        returns = group["daily_return"].astype(float)
        curve = (1.0 + returns).cumprod()
        drawdown = curve / curve.cummax() - 1.0
        annualized = (float(curve.iloc[-1]) ** (252 / max(len(group), 1)) - 1.0) if len(group) else 0.0
        summary_rows.append(
            {
                "market_regime": regime,
                "trading_days": int(len(group)),
                "avg_exposure": float(group["exposure"].mean()),
                "total_daily_pnl": float(group["daily_pnl"].sum()),
                "total_realized_pnl": float(group["realized_pnl_today"].sum()),
                "total_unrealized_pnl": float(group["unrealized_pnl_today"].sum()),
                "avg_daily_return": float(returns.mean()) if len(group) else 0.0,
                "annualized_return_in_regime": annualized,
                "max_drawdown_in_regime": float(drawdown.min()) if len(group) else 0.0,
                "trade_count": int(group["trade_count"].sum()),
                "buy_count": int(group["buy_count"].sum()),
                "sell_count": int(group["sell_count"].sum()),
            }
        )
    return daily, pd.DataFrame(summary_rows)


def _bucket_or_industry_attribution(
    key: str,
    trades: pd.DataFrame,
    position_attr: pd.DataFrame,
    daily_positions: pd.DataFrame,
) -> pd.DataFrame:
    if trades.empty:
        return pd.DataFrame()
    sell_trades = trades[trades["side"] == "SELL"].copy()
    trade_group = trades.groupby(key, dropna=False)
    realized_group = sell_trades.groupby(key, dropna=False) if not sell_trades.empty else None
    pos_group = position_attr.groupby(key, dropna=False) if not position_attr.empty else None
    daily_exposure = pd.DataFrame()
    if not daily_positions.empty:
        daily_exposure = daily_positions.groupby(["date", key], as_index=False)["weight"].sum()
    total_pnl_all = float(position_attr["total_pnl"].sum()) if not position_attr.empty else float(trades["realized_pnl"].sum())
    rows = []
    for name, group in trade_group:
        sells = realized_group.get_group(name) if realized_group is not None and name in realized_group.groups else pd.DataFrame()
        positions = pos_group.get_group(name) if pos_group is not None and name in pos_group.groups else pd.DataFrame()
        exposure = daily_exposure[daily_exposure[key] == name] if not daily_exposure.empty else pd.DataFrame()
        realized_values = sells["realized_pnl"].astype(float).tolist() if not sells.empty else []
        realized = float(sells["realized_pnl"].sum()) if not sells.empty else 0.0
        unrealized = float(positions["unrealized_pnl"].sum()) if not positions.empty else 0.0
        total = realized + unrealized
        realized_days = pd.to_numeric(positions["realized_holding_days"], errors="coerce") if not positions.empty else pd.Series(dtype=float)
        realized_days = realized_days[realized_days > 0]
        rows.append(
            {
                key: name,
                "trade_count": int(len(group)),
                "buy_count": int((group["side"] == "BUY").sum()),
                "sell_count": int((group["side"] == "SELL").sum()),
                "realized_pnl": realized,
                "unrealized_pnl": unrealized,
                "total_pnl": total,
                "contribution_pct_of_total_pnl": _safe_div(total, total_pnl_all),
                "avg_exposure": float(exposure["weight"].mean()) if not exposure.empty else 0.0,
                "max_exposure": float(exposure["weight"].max()) if not exposure.empty else 0.0,
                "avg_holding_days_including_open": float(positions["holding_days_total"].mean()) if not positions.empty else 0.0,
                "avg_holding_days_realized_only": float(realized_days.mean()) if not realized_days.empty else 0.0,
                "win_rate_realized": float((sells["realized_pnl"] > 0).mean()) if not sells.empty else 0.0,
                "profit_factor_realized": _profit_factor(realized_values),
                "max_drawdown_while_held": float(positions["max_drawdown_while_held"].min()) if not positions.empty else 0.0,
            }
        )
    return pd.DataFrame(rows).sort_values("total_pnl", ascending=False)


def main() -> int:
    configs = load_audit_configs()
    prepare_v2_history(configs)
    features = load_feature_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    benchmark = load_benchmark_window(DEFAULT_START_DATE, DEFAULT_END_DATE)
    result = run_profile("combined_v2", features, benchmark, configs, execution_mode="next_bar")
    same_close = run_profile("combined_v2", features, benchmark, configs, execution_mode="same_close")
    trades = result.trades_detailed.copy() if result.trades_detailed is not None else pd.DataFrame()
    final_positions = result.final_positions.copy() if result.final_positions is not None else pd.DataFrame()
    initial_capital = float(configs["account"]["account"]["initial_capital"])
    calendar = _trade_dates(features)
    if not trades.empty:
        trades["holding_period_bucket"] = trades["holding_days"].fillna(0).map(_holding_bucket)
        total_pnl_base = max(abs(float(result.nav["nav"].iloc[-1] - initial_capital)), 1e-9) if not result.nav.empty else 1e-9
        trades["trade_contribution_pct_of_total_pnl"] = pd.to_numeric(trades["realized_pnl"], errors="coerce").fillna(0.0) / total_pnl_base
    trades.to_csv(ensure_parent("reports/backtest/attribution/combined_v2_trade_attribution.csv"), index=False)

    monthly, monthly_check = build_monthly_returns(result.nav, initial_capital)
    monthly.to_csv(ensure_parent("reports/backtest/attribution/combined_v2_monthly_returns.csv"), index=False)
    monthly_check.to_csv(ensure_parent("reports/backtest/attribution/combined_v2_monthly_returns_check.csv"), index=False)

    position_attr = build_position_attribution(trades, final_positions, features, calendar)
    position_attr.to_csv(ensure_parent("reports/backtest/attribution/combined_v2_position_attribution.csv"), index=False)

    signal_attr = build_signal_attribution(trades, final_positions, calendar)
    signal_attr.to_csv(ensure_parent("reports/backtest/attribution/combined_v2_signal_attribution.csv"), index=False)

    daily_positions = _daily_position_values(result, features)
    bucket_attr = _bucket_or_industry_attribution("bucket", trades, position_attr, daily_positions)
    industry_attr = _bucket_or_industry_attribution("industry", trades, position_attr, daily_positions)
    bucket_attr.to_csv(ensure_parent("reports/backtest/attribution/combined_v2_bucket_attribution.csv"), index=False)
    industry_attr.to_csv(ensure_parent("reports/backtest/attribution/combined_v2_industry_attribution.csv"), index=False)

    daily_regime, regime_attr = build_daily_regime_attribution(result, features, benchmark, configs["v2_strategy"], initial_capital)
    daily_regime.to_csv(ensure_parent("reports/backtest/attribution/combined_v2_daily_regime_attribution.csv"), index=False)
    regime_attr.to_csv(ensure_parent("reports/backtest/attribution/combined_v2_regime_attribution.csv"), index=False)

    drawdown = result.nav[["date", "nav", "cash", "exposure", "holdings_count"]].copy()
    drawdown["running_peak"] = drawdown["nav"].cummax()
    drawdown["drawdown"] = drawdown["nav"] / drawdown["running_peak"] - 1.0
    drawdown.to_csv(ensure_parent("reports/backtest/attribution/combined_v2_drawdown_series.csv"), index=False)

    next_row = metrics_row("combined_v2", "next_bar", result, benchmark)
    same_row = metrics_row("combined_v2", "same_close", same_close, benchmark)
    max_stock_pct = float(position_attr["contribution_pct_of_total_pnl"].max()) if not position_attr.empty else 0.0
    max_industry_pct = float(industry_attr["contribution_pct_of_total_pnl"].max()) if not industry_attr.empty else 0.0
    realized_total = float(pd.to_numeric(trades["realized_pnl"], errors="coerce").fillna(0.0).sum()) if not trades.empty else 0.0
    unrealized_total = float(pd.to_numeric(position_attr["unrealized_pnl"], errors="coerce").fillna(0.0).sum()) if not position_attr.empty else 0.0
    total_pnl = realized_total + unrealized_total
    last_month = monthly_check.iloc[-1] if not monthly_check.empty else {}
    monthly_diff = abs(float(last_month.get("diff", 0.0))) if len(monthly_check) else 0.0
    buy1 = signal_attr[(signal_attr["attribution_type"] == "entry_signal") & (signal_attr["entry_signal_level"] == "BUY_1")]
    buy2 = signal_attr[(signal_attr["attribution_type"] == "entry_signal") & (signal_attr["entry_signal_level"] == "BUY_2")]
    buy3 = signal_attr[(signal_attr["attribution_type"] == "entry_signal") & (signal_attr["entry_signal_level"] == "BUY_3")]
    grid_add = signal_attr[(signal_attr["attribution_type"] == "entry_signal") & (signal_attr["entry_signal_level"] == "GRID_ADD")]
    trend_stop = signal_attr[(signal_attr["attribution_type"] == "exit_signal") & (signal_attr["exit_reason"] == "trend_stop")]
    valuation_exit = signal_attr[(signal_attr["attribution_type"] == "exit_signal") & (signal_attr["exit_reason"] == "valuation_reversion_exit")]
    soft_trim = signal_attr[(signal_attr["attribution_type"] == "exit_signal") & (signal_attr["exit_reason"] == "soft_trim")]
    risk_on_daily = regime_attr[regime_attr["market_regime"] == "risk_on"]
    risk_on_realized = float(risk_on_daily["total_realized_pnl"].iloc[0]) if not risk_on_daily.empty else 0.0
    risk_on_mtm = float(risk_on_daily["total_daily_pnl"].iloc[0]) if not risk_on_daily.empty else 0.0
    risk_off = regime_attr[regime_attr["market_regime"] == "risk_off"]
    risk_off_mtm = float(risk_off["total_daily_pnl"].iloc[0]) if not risk_off.empty else 0.0
    risk_off_realized = float(risk_off["total_realized_pnl"].iloc[0]) if not risk_off.empty else 0.0
    trade_regime = (
        trades[trades["side"] == "SELL"]
        .groupby("market_regime", as_index=False)
        .agg(
            realized_pnl=("realized_pnl", "sum"),
            sell_count=("side", "count"),
            avg_holding_days=("holding_days", "mean"),
        )
        .sort_values("realized_pnl", ascending=False)
        if not trades.empty
        else pd.DataFrame(columns=["market_regime", "realized_pnl", "sell_count", "avg_holding_days"])
    )
    holding_attr = (
        trades[trades["side"] == "SELL"]
        .groupby("holding_period_bucket", as_index=False)
        .agg(realized_pnl=("realized_pnl", "sum"), sell_count=("side", "count"), avg_holding_days=("holding_days", "mean"))
        if not trades.empty
        else pd.DataFrame(columns=["holding_period_bucket", "realized_pnl", "sell_count", "avg_holding_days"])
    )
    entry_rows = signal_attr[signal_attr["attribution_type"] == "entry_signal"].sort_values("entry_signal_level")
    exit_rows = signal_attr[signal_attr["attribution_type"] == "exit_signal"].sort_values("realized_pnl", ascending=False)
    pair_rows = signal_attr[signal_attr["attribution_type"] == "entry_exit_pair"].sort_values("total_pnl", ascending=False)
    winners = position_attr.sort_values("total_pnl", ascending=False).head(10) if not position_attr.empty else pd.DataFrame()
    losers = position_attr.sort_values("total_pnl", ascending=True).head(10) if not position_attr.empty else pd.DataFrame()

    lines = [
        "# combined_v2 收益归因报告",
        "",
        "## 主口径摘要",
        "",
        "- 主口径: combined_v2 PIT next_bar。",
        f"- next_bar 年化 {pct(next_row['annual_return'])}，累计 {pct(next_row['cumulative_return'])}，最大回撤 {pct(next_row['max_drawdown'])}，成交 {int(next_row['total_trades'])} 笔。",
        f"- same_close 对照年化 {pct(same_row['annual_return'])}，累计 {pct(same_row['cumulative_return'])}，成交 {int(same_row['total_trades'])} 笔。",
        f"- 月度收益已经改为连续 NAV 链；最后一行复合累计与 final NAV 累计差异 {monthly_diff:.12f}。",
        "- 持仓期已经按实际持仓区间交易日去重；未平仓持仓统计到回测结束日。",
        "- signal attribution 已拆分为 entry_signal、exit_signal、entry_exit_pair；当前无 lot 级成本账本，已用 FIFO lot 近似分摊 realized/unrealized PnL。",
        "- regime attribution 同时保留 trade_realization_regime 与 daily_mtm_regime；后者按每日 NAV 变化盯市。",
        f"- 组合 total_pnl {total_pnl:.2f}，已实现 {realized_total:.2f}，未实现 {unrealized_total:.2f}。",
        f"- 最大单只股票贡献占总收益比例: {max_stock_pct:.2%}",
        f"- 最大单个行业贡献占总收益比例: {max_industry_pct:.2%}",
        "",
        "## bucket attribution",
        "",
    ]
    for row in bucket_attr.to_dict(orient="records"):
        lines.append(
            f"- {row['bucket']}: total_pnl {row['total_pnl']:.2f}，已实现 {row['realized_pnl']:.2f}，未实现 {row['unrealized_pnl']:.2f}，成交 {int(row['trade_count'])}，平均仓位 {row['avg_exposure']:.2%}"
        )
    lines.extend(["", "## industry attribution", ""])
    for row in industry_attr.to_dict(orient="records"):
        lines.append(
            f"- {row['industry']}: total_pnl {row['total_pnl']:.2f}，已实现 {row['realized_pnl']:.2f}，未实现 {row['unrealized_pnl']:.2f}，成交 {int(row['trade_count'])}，贡献 {row['contribution_pct_of_total_pnl']:.2%}"
        )
    lines.extend(["", "## position attribution", ""])
    for row in position_attr.sort_values("total_pnl", ascending=False).head(12).to_dict(orient="records"):
        lines.append(
            f"- {row['ts_code']} {row['name']}: total_pnl {row['total_pnl']:.2f}，已实现 {row['realized_pnl']:.2f}，未实现 {row['unrealized_pnl']:.2f}，持仓日 {int(row['holding_days_total'])}，open={bool(row['is_open_position'])}。"
        )
    lines.extend(["", "## entry signal attribution", ""])
    for level in ("BUY_1", "BUY_2", "BUY_3", "GRID_ADD"):
        row = entry_rows[entry_rows["entry_signal_level"] == level]
        if row.empty:
            if level == "BUY_3":
                lines.append("- BUY_3: 无独立 BUY_3 entry attribution。")
            elif level == "GRID_ADD":
                lines.append("- GRID_ADD: 当前引擎没有独立 GRID_ADD 动作枚举，加仓记录在 BUY_2/BUY_3。")
            else:
                lines.append(f"- {level}: 无记录。")
            continue
        item = row.iloc[0]
        lines.append(
            f"- {level}: total_pnl {float(item['total_pnl']):.2f}，已实现 {float(item['realized_pnl']):.2f}，未实现 {float(item['unrealized_pnl']):.2f}，win_rate {float(item['win_rate']):.2%}，profit_factor {float(item['profit_factor']):.2f}，avg_holding_days {float(item['avg_holding_days']):.2f}。"
        )
    lines.extend(["", "## exit signal attribution", ""])
    for row in exit_rows.to_dict(orient="records"):
        label = row["exit_reason"] or row["exit_action"]
        lines.append(
            f"- {label}: realized_pnl {row['realized_pnl']:.2f}，total_pnl {row['total_pnl']:.2f}，win_rate {row['win_rate']:.2%}，profit_factor {row['profit_factor']:.2f}，avg_holding_days {row['avg_holding_days']:.2f}。"
        )
    for label, frame in (
        ("valuation_reversion_exit", valuation_exit),
        ("trend_stop", trend_stop),
        ("soft_trim", soft_trim),
    ):
        if frame.empty:
            lines.append(f"- {label}: realized_pnl 0.00。")
    lines.extend(["", "## entry-exit pair attribution", ""])
    for row in pair_rows.head(15).to_dict(orient="records"):
        label = f"{row['entry_signal_level']} -> {row['exit_reason'] or row['exit_action']}"
        lines.append(
            f"- {label}: total_pnl {row['total_pnl']:.2f}，已实现 {row['realized_pnl']:.2f}，未实现 {row['unrealized_pnl']:.2f}，样本 {int(row['trade_count'])}。"
        )
    lines.extend(["", "## trade realization regime attribution", ""])
    for row in trade_regime.to_dict(orient="records"):
        lines.append(
            f"- trade_realization_regime {row['market_regime']}: realized_pnl {row['realized_pnl']:.2f}，卖出 {int(row['sell_count'])}，avg_holding_days {row['avg_holding_days']:.2f}。"
        )
    lines.extend(["", "## daily MTM regime attribution", ""])
    for row in regime_attr.to_dict(orient="records"):
        lines.append(
            f"- daily_mtm_regime {row['market_regime']}: 日盯市 PnL {row['total_daily_pnl']:.2f}，已实现 {row['total_realized_pnl']:.2f}，未实现/盯市 {row['total_unrealized_pnl']:.2f}，交易 {int(row['trade_count'])}。"
        )
    lines.extend(["", "## holding period attribution", ""])
    for row in holding_attr.to_dict(orient="records"):
        lines.append(
            f"- {row['holding_period_bucket']}: realized_pnl {row['realized_pnl']:.2f}，卖出 {int(row['sell_count'])}，avg_holding_days {row['avg_holding_days']:.2f}。"
        )
    lines.extend(["", "## major winners", ""])
    for row in winners.to_dict(orient="records"):
        lines.append(f"- {row['ts_code']} {row['name']}: total_pnl {row['total_pnl']:.2f}，行业 {row['industry']}，bucket {row['bucket']}。")
    lines.extend(["", "## major losers", ""])
    for row in losers.to_dict(orient="records"):
        lines.append(f"- {row['ts_code']} {row['name']}: total_pnl {row['total_pnl']:.2f}，行业 {row['industry']}，bucket {row['bucket']}。")
    lines.extend(
        [
            "",
            "## key answers",
            "",
            f"- combined_v2 的收益是否主要在 risk_on 日赚到: risk_on daily MTM PnL 为 {risk_on_mtm:.2f}，risk_on 卖出/成交日 realized PnL 为 {risk_on_realized:.2f}；以 daily MTM 为主判断赚钱发生在哪些市场状态。",
            f"- risk_off 负收益来源: risk_off daily MTM PnL 为 {risk_off_mtm:.2f}，risk_off realized PnL 为 {risk_off_realized:.2f}；若 realized 明显为负，说明 risk_off 中止损兑现占比高，否则更多来自持仓盯市波动。",
            "- 当前是否需要直接替换 v2 为 v2_1_risk_guard: 不需要；v2_1_risk_guard 是更保守观察候选，不替换主口径。",
            f"- defensive_dividend total_pnl: {float(bucket_attr.loc[bucket_attr['bucket'] == 'defensive_dividend', 'total_pnl'].sum()) if not bucket_attr.empty else 0.0:.2f}。",
            f"- cyclical_rotation total_pnl: {float(bucket_attr.loc[bucket_attr['bucket'] == 'cyclical_rotation', 'total_pnl'].sum()) if not bucket_attr.empty else 0.0:.2f}。",
            "- 正贡献、负贡献和成交多但贡献低的行业见 `combined_v2_industry_attribution.csv`。",
        ]
    )
    ensure_parent("reports/backtest/attribution/combined_v2_attribution_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
