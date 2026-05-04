from __future__ import annotations

import json
from dataclasses import dataclass
from math import sqrt
from pathlib import Path

import pandas as pd

from src.strategy.regime import determine_market_regime
from src.strategy.signals import SignalEngine
from src.utils.config import resolve_path


@dataclass
class Position:
    symbol: str
    industry: str
    bucket: str
    shares: float = 0.0
    avg_cost: float = 0.0
    current_position_tranches: int = 0
    current_weight: float = 0.0
    extra_tranches: int = 0
    last_fill_price: float = 0.0
    current_shares: int = 0
    entry_date: str = ""
    entry_index: int = 0
    entry_reason: str = ""
    last_buy_date: str = ""
    last_buy_index: int = 0


@dataclass
class BacktestResult:
    metrics: dict
    nav: pd.DataFrame
    trade_list: pd.DataFrame
    stock_attribution: pd.DataFrame
    industry_attribution: pd.DataFrame
    approximate_backtest: bool = False
    daily_diagnostics: pd.DataFrame | None = None
    blocked_signals: pd.DataFrame | None = None
    trades_detailed: pd.DataFrame | None = None
    final_cash: float = 0.0
    final_positions: pd.DataFrame | None = None
    execution_mode: str = "next_bar"


class BacktestEngine:
    def __init__(
        self,
        strategy_cfg: dict,
        universe_rules_cfg: dict | None = None,
        account_cfg: dict | None = None,
        initial_cash: float | None = None,
        historical_universe_dir: str | Path | None = "data/curated/universe_history",
        execution_mode: str | None = None,
    ) -> None:
        self.strategy_cfg = strategy_cfg
        self.universe_rules_cfg = universe_rules_cfg or {}
        self.account_cfg = account_cfg or {}
        account_initial = float(self.account_cfg.get("account", {}).get("initial_capital", 1_000_000.0))
        self.initial_cash = float(initial_cash if initial_cash is not None else account_initial)
        self.signal_engine = SignalEngine(strategy_cfg, self.universe_rules_cfg, self.account_cfg)
        self.historical_universe_dir = resolve_path(historical_universe_dir) if historical_universe_dir else None
        execution_cfg = self.account_cfg.get("execution", {}) if isinstance(self.account_cfg, dict) else {}
        self.fee_rate = float(execution_cfg.get("commission_rate", self.strategy_cfg["execution"].get("fee_rate", 0.0)))
        self.tax_rate = float(execution_cfg.get("stamp_duty_rate_sell", self.strategy_cfg["execution"].get("stamp_tax_rate", 0.0)))
        slippage_bps = execution_cfg.get("slippage_bps")
        if slippage_bps is None:
            self.slippage_rate = float(self.strategy_cfg["execution"].get("slippage_rate", 0.0))
        else:
            self.slippage_rate = float(slippage_bps) / 10_000.0
        self.execution_mode = self._resolve_execution_mode(execution_mode)

    def _resolve_execution_mode(self, execution_mode: str | None) -> str:
        if execution_mode:
            raw_mode = execution_mode
        else:
            account_execution = self.account_cfg.get("execution", {}) if isinstance(self.account_cfg, dict) else {}
            strategy_execution = self.strategy_cfg.get("execution", {}) if isinstance(self.strategy_cfg, dict) else {}
            raw_mode = account_execution.get("execution_mode") or strategy_execution.get("execution_mode") or strategy_execution.get("trade_at")
        aliases = {
            "next_bar": "next_bar",
            "next_day_open": "next_bar",
            "next_day_close": "next_bar",
            "same_close": "same_close",
            "same_day_close": "same_close",
            "close": "same_close",
            "None": "next_bar",
        }
        resolved = aliases.get(str(raw_mode))
        if resolved is None:
            raise ValueError(f"Unsupported execution_mode: {raw_mode}")
        return resolved

    def run(self, features: pd.DataFrame, benchmark: pd.DataFrame, bucket: str = "combined") -> BacktestResult:
        features = features.sort_values(["date", "symbol"]).copy()
        features = self._prepare_backtest_features(features)
        features, approximate_backtest = self._overlay_historical_universe(features)
        benchmark = benchmark.sort_values("date").copy()
        feature_by_date = {date: frame.copy() for date, frame in features.groupby("date", sort=True)}
        dates = sorted(feature_by_date)
        if len(dates) < 2:
            raise ValueError("Backtest requires at least two trading days.")

        cash = self.initial_cash
        positions: dict[str, Position] = {}
        nav_records: list[dict] = []
        trades: list[dict] = []
        trades_detailed: list[dict] = []
        daily_diagnostics: list[dict] = []
        blocked_signals: list[dict] = []
        is_v2 = str(self.strategy_cfg.get("profile", self.strategy_cfg.get("strategy_profile", ""))).startswith("combined_v2")

        signal_indices = range(len(dates) - 1) if self.execution_mode == "next_bar" else range(len(dates))
        for index in signal_indices:
            signal_date = dates[index]
            fill_index = index + 1 if self.execution_mode == "next_bar" else index
            fill_date = dates[fill_index]
            todays = feature_by_date[signal_date].copy()
            if bucket != "combined":
                todays = todays[todays["bucket"] == bucket].copy()
            benchmark_until_today = benchmark[benchmark["date"] <= signal_date]
            regime = determine_market_regime(benchmark_until_today, self.strategy_cfg)
            positions_df = self._positions_frame(positions, current_index=index, current_date=signal_date)
            todays = self._apply_positions_to_features(todays, positions_df)
            if is_v2:
                todays = self._apply_v2_holding_state(todays)
            nav = self._portfolio_value(cash, positions, todays.set_index("symbol"), mark_field="close")
            if "in_effective_universe" in todays.columns:
                decision_scope = todays[
                    todays["in_effective_universe"].astype(bool)
                    | todays["symbol"].astype(str).isin(set(positions.keys()))
                ].copy()
            else:
                decision_scope = todays.copy()
            account_state = {
                "orders_degraded": False,
                "current_cash": cash,
                "reserved_cash": 0.0,
                "latest_total_equity": nav,
                "current_invested_value": max(0.0, nav - cash),
                "holdings_count": len(positions),
            }
            decisions = self.signal_engine.generate(decision_scope, positions_df, regime, safe_mode=False, account_state=account_state)
            day_trade_count_before = len(trades)
            next_day = feature_by_date[fill_date].set_index("symbol")
            for decision in decisions:
                action = decision["action_enum"]
                if action not in {"BUY_1", "BUY_2", "BUY_3", "REDUCE", "SELL_ALL"}:
                    continue
                if decision["symbol"] not in next_day.index:
                    continue
                fill_open, fill_price_field = self._raw_fill_price(next_day, decision["symbol"])
                if fill_open <= 0:
                    blocked_signals.append(self._execution_block_record(signal_date, decision, "MISSING_FILL_PRICE", "成交日缺少可用价格。"))
                    continue
                fill_price = fill_open * (
                    1 + self.slippage_rate
                    if action in {"BUY_1", "BUY_2", "BUY_3"}
                    else 1 - self.slippage_rate
                )
                trade_value = abs(float(decision.get("target_order_value", 0.0)))
                if trade_value <= 0:
                    trade_value = abs(float(decision["target_position_change"])) * nav
                realized_pnl = 0.0
                requested_shares = abs(int(decision.get("delta_shares", 0) or 0))
                cash_before = cash
                existing_position = positions.get(decision["symbol"])
                position_before = float(existing_position.shares) if existing_position else 0.0
                weight_before = position_before * fill_price / nav if nav > 0 else 0.0
                avg_cost_before = float(existing_position.avg_cost) if existing_position else 0.0
                entry_date = existing_position.entry_date if existing_position else ""
                entry_reason = existing_position.entry_reason if existing_position else ""
                holding_days = (fill_index - existing_position.entry_index) if existing_position else 0
                fee = 0.0
                tax = 0.0
                execution_adjustment = ""
                execution_reason_code = ""

                if action in {"BUY_1", "BUY_2", "BUY_3"}:
                    shares = float(requested_shares) if requested_shares > 0 else (trade_value / fill_price if fill_price else 0.0)
                    adjusted_shares, execution_reason_code = self._constrain_buy_shares(
                        requested_shares=shares,
                        fill_price=fill_price,
                        cash=cash,
                        positions=positions,
                        symbol=decision["symbol"],
                        price_frame=next_day,
                        market_regime=regime,
                        bucket=str(decision.get("bucket", "")),
                    )
                    if adjusted_shares <= 0:
                        blocked_signals.append(
                            self._execution_block_record(
                                signal_date,
                                decision,
                                execution_reason_code or "EXECUTION_CONSTRAINT",
                                "成交日价格重算后，现金、整手、最小成交额、总仓位或单票上限不满足。",
                            )
                        )
                        continue
                    if adjusted_shares < shares:
                        execution_adjustment = "CLIPPED"
                    shares = float(adjusted_shares)
                    trade_value = shares * fill_price
                    fee = trade_value * self.fee_rate
                    cash -= trade_value + fee
                    position = positions.get(
                        decision["symbol"],
                        Position(
                            symbol=decision["symbol"],
                            industry=str(decision["industry"]),
                            bucket=str(decision["bucket"]),
                            entry_date=fill_date,
                            entry_index=fill_index,
                            entry_reason=str(decision.get("action_reason", "")),
                            last_buy_date=fill_date,
                            last_buy_index=fill_index,
                        ),
                    )
                    if not position.entry_date:
                        position.entry_date = fill_date
                        position.entry_index = fill_index
                        position.entry_reason = str(decision.get("action_reason", ""))
                    total_cost = position.avg_cost * position.shares + trade_value
                    position.shares += shares
                    position.avg_cost = total_cost / position.shares if position.shares else 0.0
                    position.current_position_tranches = int(decision["target_position_tranches"])
                    position.current_weight = float(decision["target_weight"])
                    position.last_fill_price = fill_price
                    position.last_buy_date = fill_date
                    position.last_buy_index = fill_index
                    position.current_shares = int(round(position.shares))
                    positions[decision["symbol"]] = position
                else:
                    if decision["symbol"] not in positions:
                        continue
                    position = positions[decision["symbol"]]
                    fee = trade_value * self.fee_rate
                    tax = trade_value * self.tax_rate
                    if action == "SELL_ALL":
                        shares = position.shares
                        trade_value = shares * fill_price
                        fee = trade_value * self.fee_rate
                        tax = trade_value * self.tax_rate
                        cash += trade_value - fee - tax
                        realized_pnl = trade_value - position.avg_cost * shares - fee - tax
                        positions.pop(decision["symbol"], None)
                    else:
                        shares = min(position.shares, float(requested_shares) if requested_shares > 0 else (trade_value / fill_price if fill_price else 0.0))
                        shares = self._round_down_lot(shares)
                        if shares <= 0:
                            blocked_signals.append(self._execution_block_record(signal_date, decision, "LOT_SIZE_ZERO", "成交日价格重算后，减仓股数低于整手。"))
                            continue
                        realized_value = shares * fill_price
                        if realized_value < self.signal_engine.min_trade_value:
                            blocked_signals.append(self._execution_block_record(signal_date, decision, "MIN_TRADE_AMOUNT", "成交日价格重算后，减仓金额低于最小成交额。"))
                            continue
                        trade_value = realized_value
                        fee = realized_value * self.fee_rate
                        tax = realized_value * self.tax_rate
                        cash += realized_value - fee - tax
                        realized_pnl = realized_value - position.avg_cost * shares - fee - tax
                        position.shares -= shares
                        position.current_position_tranches = int(decision["target_position_tranches"])
                        position.current_weight = float(decision["target_weight"])
                        position.last_fill_price = fill_price
                        position.current_shares = int(round(position.shares))
                        if position.shares <= 1e-9:
                            positions.pop(decision["symbol"], None)
                        else:
                            positions[decision["symbol"]] = position

                remaining_position = positions.get(decision["symbol"])
                position_after = float(remaining_position.shares) if remaining_position else 0.0
                weight_after = position_after * fill_price / nav if nav > 0 else 0.0
                close_after = float(next_day.loc[decision["symbol"], "close"]) if decision["symbol"] in next_day.index and "close" in next_day.columns else fill_price
                unrealized_pnl_after = (
                    position_after * (close_after - float(remaining_position.avg_cost))
                    if remaining_position and position_after > 0
                    else 0.0
                )
                trades.append(
                    {
                        "signal_date": signal_date,
                        "fill_date": fill_date,
                        "symbol": decision["symbol"],
                        "industry": decision["industry"],
                        "bucket": decision["bucket"],
                        "action": action,
                        "fill_price": fill_price,
                        "realized_pnl": realized_pnl,
                    }
                )
                trades_detailed.append(
                    {
                        "date": fill_date,
                        "signal_date": signal_date,
                        "ts_code": decision["symbol"],
                        "symbol": decision["symbol"],
                        "name": decision.get("name"),
                        "industry": decision.get("industry"),
                        "bucket": decision.get("bucket"),
                        "side": "BUY" if action in {"BUY_1", "BUY_2", "BUY_3"} else "SELL",
                        "action": action,
                        "signal_level": decision.get("signal_level", action),
                        "shares": shares,
                        "price": fill_price,
                        "amount": trade_value,
                        "fee": fee,
                        "tax": tax,
                        "slippage": abs(fill_price - fill_open),
                        "slippage_cost": abs(fill_price - fill_open) * shares,
                        "cash_before": cash_before,
                        "cash_after": cash,
                        "position_before": position_before,
                        "position_after": position_after,
                        "weight_before": weight_before,
                        "weight_after": weight_after,
                        "target_weight": decision.get("target_weight"),
                        "entry_date": entry_date or (fill_date if action in {"BUY_1", "BUY_2", "BUY_3"} else ""),
                        "entry_reason": decision.get("action_reason") if action in {"BUY_1", "BUY_2", "BUY_3"} else entry_reason,
                        "exit_reason": decision.get("exit_reason", decision.get("action_reason")) if action in {"REDUCE", "SELL_ALL"} else "",
                        "holding_days": holding_days,
                        "avg_cost_before": avg_cost_before,
                        "realized_pnl": realized_pnl,
                        "unrealized_pnl_after_trade": unrealized_pnl_after,
                        "market_regime": regime["regime"],
                        "execution_mode": self.execution_mode,
                        "fill_price_field": fill_price_field,
                        "execution_adjustment": execution_adjustment,
                        "execution_reason_code": execution_reason_code,
                    }
                )

            nav_records.append(
                {
                    "date": fill_date,
                    "nav": self._portfolio_value(cash, positions, next_day, mark_field="close"),
                    "cash": cash,
                    "invested_value": max(0.0, self._portfolio_value(cash, positions, next_day, mark_field="close") - cash),
                    "exposure": max(0.0, self._portfolio_value(cash, positions, next_day, mark_field="close") - cash)
                    / max(self._portfolio_value(cash, positions, next_day, mark_field="close"), 1e-9),
                    "holdings_count": len(positions),
                }
            )
            executed_today = trades[day_trade_count_before:]
            daily_diagnostics.append(self._daily_diagnostic_record(signal_date, todays, decisions, benchmark_until_today, regime, nav, cash_before=account_state["current_cash"], positions=positions, executed_trades=executed_today))
            blocked_signals.extend(self._blocked_signal_records(signal_date, decisions))

        nav_frame = pd.DataFrame(nav_records)
        trade_frame = pd.DataFrame(trades)
        detailed_frame = pd.DataFrame(trades_detailed)
        metrics = self._metrics(nav_frame, trade_frame, detailed_frame)
        final_price_frame = feature_by_date[dates[-1]].set_index("symbol")
        final_positions = self._final_positions_frame(positions, final_price_frame)
        stock_attr = trade_frame.groupby("symbol", as_index=False)["realized_pnl"].sum() if not trade_frame.empty else pd.DataFrame(columns=["symbol", "realized_pnl"])
        industry_attr = trade_frame.groupby("industry", as_index=False)["realized_pnl"].sum() if not trade_frame.empty else pd.DataFrame(columns=["industry", "realized_pnl"])
        return BacktestResult(
            metrics,
            nav_frame,
            trade_frame,
            stock_attr,
            industry_attr,
            approximate_backtest=approximate_backtest,
            daily_diagnostics=pd.DataFrame(daily_diagnostics),
            blocked_signals=pd.DataFrame(blocked_signals),
            trades_detailed=detailed_frame,
            final_cash=float(cash),
            final_positions=final_positions,
            execution_mode=self.execution_mode,
        )

    @staticmethod
    def _prepare_backtest_features(features: pd.DataFrame) -> pd.DataFrame:
        prepared = features.copy()
        defaults = {
            "in_effective_universe": True,
            "holding_state": "NONE",
            "current_position_tranches": 0,
            "current_weight": 0.0,
            "extra_tranches": 0,
            "last_fill_price": 0.0,
            "current_shares": 0,
            "data_stale": False,
            "fundamental_break": False,
            "cycle_peak_trap": False,
            "quality_pass": True,
        }
        for column, default in defaults.items():
            if column not in prepared.columns:
                prepared[column] = default
            else:
                prepared[column] = prepared[column].fillna(default)
        if "universe_final_score" not in prepared.columns and "final_score" in prepared.columns:
            prepared["universe_final_score"] = prepared["final_score"]
        return prepared

    def _overlay_historical_universe(self, features: pd.DataFrame) -> tuple[pd.DataFrame, bool]:
        if self.historical_universe_dir is None or not self.historical_universe_dir.exists():
            return features, True
        histories: list[dict] = []
        for path in sorted(self.historical_universe_dir.glob("*.json")):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue
            effective_from = payload.get("effective_from")
            effective_to = payload.get("effective_to")
            stocks = payload.get("stocks", [])
            if not effective_from:
                continue
            histories.append(
                {
                    "effective_from": pd.Timestamp(effective_from),
                    "effective_to": pd.Timestamp(effective_to) if effective_to else None,
                    "symbols": {str(item.get("symbol")) for item in stocks if item.get("symbol")},
                    "stock_map": {
                        str(item.get("symbol")): {
                            "universe_bucket": item.get("bucket"),
                            "universe_main_metric": item.get("main_metric"),
                            "universe_final_score": item.get("final_score"),
                            "universe_industry": item.get("industry_l1"),
                            "industry_rank": item.get("industry_rank"),
                            "selected_as": item.get("selected_as"),
                        }
                        for item in stocks
                        if item.get("symbol")
                    },
                }
            )
        if not histories:
            return features, True
        prepared = features.copy()
        approximate_backtest = False
        for date in sorted(pd.to_datetime(prepared["date"].dropna().unique())):
            matches = [
                item
                for item in histories
                if item["effective_from"] <= date and (item["effective_to"] is None or date <= item["effective_to"])
            ]
            if not matches:
                approximate_backtest = True
                continue
            selected = max(matches, key=lambda item: item["effective_from"])
            mask = prepared["date"] == date.strftime("%Y-%m-%d")
            current = prepared.loc[mask].copy()
            current["in_effective_universe"] = current["symbol"].astype(str).isin(selected["symbols"])
            stock_details = current["symbol"].astype(str).map(selected["stock_map"])
            bucket_updates = stock_details.map(lambda item: item.get("universe_bucket") if isinstance(item, dict) else pd.NA)
            main_metric_updates = stock_details.map(lambda item: item.get("universe_main_metric") if isinstance(item, dict) else pd.NA)
            universe_final_score_updates = pd.to_numeric(
                stock_details.map(lambda item: item.get("universe_final_score") if isinstance(item, dict) else pd.NA),
                errors="coerce",
            )
            universe_industry_updates = stock_details.map(lambda item: item.get("universe_industry") if isinstance(item, dict) else pd.NA)
            industry_rank_updates = pd.to_numeric(
                stock_details.map(lambda item: item.get("industry_rank") if isinstance(item, dict) else pd.NA),
                errors="coerce",
            )
            selected_as_updates = stock_details.map(lambda item: item.get("selected_as") if isinstance(item, dict) else pd.NA)

            prepared.loc[mask, "in_effective_universe"] = current["in_effective_universe"].values
            prepared.loc[mask, "bucket"] = bucket_updates.combine_first(current["bucket"]).values if "bucket" in current.columns else bucket_updates.values
            prepared.loc[mask, "main_metric"] = (
                main_metric_updates.combine_first(current["main_metric"]).values if "main_metric" in current.columns else main_metric_updates.values
            )
            prepared.loc[mask, "universe_bucket"] = bucket_updates.values
            prepared.loc[mask, "universe_main_metric"] = main_metric_updates.values
            prepared.loc[mask, "universe_final_score"] = universe_final_score_updates.values
            prepared.loc[mask, "universe_industry"] = universe_industry_updates.values
            prepared.loc[mask, "industry_rank"] = (
                industry_rank_updates.combine_first(pd.to_numeric(current["industry_rank"], errors="coerce")).values
                if "industry_rank" in current.columns
                else industry_rank_updates.values
            )
            prepared.loc[mask, "selected_as"] = selected_as_updates.values
        return prepared, approximate_backtest

    @staticmethod
    def _positions_frame(positions: dict[str, Position], current_index: int = 0, current_date: str = "") -> pd.DataFrame:
        if not positions:
            return pd.DataFrame(
                columns=[
                    "symbol",
                    "current_position_tranches",
                    "current_weight",
                    "extra_tranches",
                    "last_fill_price",
                    "current_shares",
                    "avg_cost",
                    "entry_date",
                    "last_buy_date",
                    "holding_days",
                    "days_since_last_buy",
                ]
            )
        return pd.DataFrame(
            [
                {
                    "symbol": position.symbol,
                    "current_position_tranches": position.current_position_tranches,
                    "current_weight": position.current_weight,
                    "extra_tranches": position.extra_tranches,
                    "last_fill_price": position.last_fill_price,
                    "current_shares": position.current_shares,
                    "avg_cost": position.avg_cost,
                    "entry_date": position.entry_date,
                    "last_buy_date": position.last_buy_date,
                    "holding_days": max(0, current_index - int(position.entry_index)),
                    "days_since_last_buy": max(0, current_index - int(position.last_buy_index)),
                }
                for position in positions.values()
            ]
        )

    @staticmethod
    def _apply_positions_to_features(features: pd.DataFrame, positions: pd.DataFrame) -> pd.DataFrame:
        if features.empty or positions.empty:
            return features
        merged = features.merge(
            positions,
            how="left",
            on="symbol",
            suffixes=("", "_position"),
        )
        for column in (
            "current_position_tranches",
            "current_weight",
            "extra_tranches",
            "last_fill_price",
            "current_shares",
            "avg_cost",
            "entry_date",
            "last_buy_date",
            "holding_days",
            "days_since_last_buy",
        ):
            position_column = f"{column}_position"
            if position_column not in merged.columns:
                continue
            merged[column] = merged[position_column].combine_first(merged[column])
            merged = merged.drop(columns=[position_column])
        if {"avg_cost", "close", "current_shares"} <= set(merged.columns):
            invested_cost = pd.to_numeric(merged["avg_cost"], errors="coerce").fillna(0.0)
            close = pd.to_numeric(merged["close"], errors="coerce").fillna(0.0)
            shares = pd.to_numeric(merged["current_shares"], errors="coerce").fillna(0.0)
            merged["unrealized_pnl_pct"] = ((close - invested_cost) / invested_cost).where((shares > 0) & (invested_cost > 0), 0.0).fillna(0.0)
        return merged

    @staticmethod
    def _apply_v2_holding_state(features: pd.DataFrame) -> pd.DataFrame:
        if features.empty:
            return features
        prepared = features.copy()
        held = pd.to_numeric(prepared.get("current_position_tranches", 0), errors="coerce").fillna(0).astype(int) > 0
        prepared.loc[~held, "holding_state"] = "NONE"
        active = held & prepared["in_effective_universe"].astype(bool)
        frozen = held & ~prepared["in_effective_universe"].astype(bool)
        fundamental_break = prepared["fundamental_break"].astype(bool) if "fundamental_break" in prepared.columns else pd.Series(False, index=prepared.index)
        is_st = prepared["is_st"].astype(bool) if "is_st" in prepared.columns else pd.Series(False, index=prepared.index)
        delist_risk = prepared["delist_risk"].fillna(False).astype(bool) if "delist_risk" in prepared.columns else pd.Series(False, index=prepared.index)
        force_exit = held & (fundamental_break | is_st | delist_risk)
        prepared.loc[active, "holding_state"] = "ACTIVE"
        prepared.loc[frozen, "holding_state"] = "FROZEN"
        prepared.loc[force_exit, "holding_state"] = "FORCE_EXIT"
        return prepared

    @staticmethod
    def _portfolio_value(cash: float, positions: dict[str, Position], price_frame: pd.DataFrame, mark_field: str) -> float:
        value = cash
        for symbol, position in positions.items():
            if symbol in price_frame.index:
                value += position.shares * float(price_frame.loc[symbol, mark_field])
        return value

    def _raw_fill_price(self, price_frame: pd.DataFrame, symbol: str) -> tuple[float, str]:
        if self.execution_mode == "same_close":
            return float(price_frame.loc[symbol, "close"]), "close"
        if "open" in price_frame.columns and pd.notna(price_frame.loc[symbol, "open"]):
            return float(price_frame.loc[symbol, "open"]), "open"
        return float(price_frame.loc[symbol, "close"]), "close"

    def _round_down_lot(self, shares: float) -> float:
        lot = max(1, int(self.signal_engine.round_lot))
        return float(int(max(0.0, shares)) // lot * lot)

    def _constrain_buy_shares(
        self,
        requested_shares: float,
        fill_price: float,
        cash: float,
        positions: dict[str, Position],
        symbol: str,
        price_frame: pd.DataFrame,
        market_regime: dict,
        bucket: str,
    ) -> tuple[float, str]:
        requested = self._round_down_lot(requested_shares)
        if requested <= 0:
            return 0.0, "LOT_SIZE_ZERO"
        equity = self._portfolio_value(cash, positions, price_frame, mark_field="close")
        invested_value = max(0.0, equity - cash)
        existing = positions.get(symbol)
        existing_value = (existing.shares * fill_price) if existing else 0.0
        max_single = self.signal_engine._bucket_max_weight(existing.bucket if existing else bucket)
        max_cash_value = max(0.0, cash / max(1.0 + self.fee_rate, 1e-9))
        max_total_value = max(0.0, float(market_regime["max_total_position"]) * equity - invested_value)
        max_single_value = max(0.0, max_single * equity - existing_value)
        allowed_value = min(requested * fill_price, max_cash_value, max_total_value, max_single_value)
        adjusted = self._round_down_lot(allowed_value / fill_price if fill_price > 0 else 0.0)
        if adjusted <= 0:
            if max_cash_value <= 0:
                return 0.0, "CASH_INSUFFICIENT_AT_FILL"
            if max_total_value <= 0:
                return 0.0, "TOTAL_EXPOSURE_LIMIT_AT_FILL"
            if max_single_value <= 0:
                return 0.0, "SINGLE_NAME_LIMIT_AT_FILL"
            return 0.0, "LOT_SIZE_ZERO"
        amount = adjusted * fill_price
        if amount < self.signal_engine.min_trade_value:
            return 0.0, "MIN_TRADE_AMOUNT_AT_FILL"
        if adjusted < requested:
            if max_cash_value <= allowed_value + 1e-9:
                return adjusted, "CASH_CLIPPED_AT_FILL"
            if max_total_value <= allowed_value + 1e-9:
                return adjusted, "TOTAL_EXPOSURE_CLIPPED_AT_FILL"
            if max_single_value <= allowed_value + 1e-9:
                return adjusted, "SINGLE_NAME_CLIPPED_AT_FILL"
            return adjusted, "ORDER_CLIPPED_AT_FILL"
        return adjusted, ""

    @staticmethod
    def _execution_block_record(signal_date: str, decision: dict, reason_code: str, detail: str) -> dict:
        return {
            "date": signal_date,
            "ts_code": decision.get("symbol"),
            "symbol": decision.get("symbol"),
            "name": decision.get("name"),
            "bucket": decision.get("bucket"),
            "intended_action": decision.get("action_enum"),
            "intended_signal_level": decision.get("signal_level", decision.get("action_enum")),
            "intended_target_weight": decision.get("target_weight"),
            "current_weight": decision.get("current_weight"),
            "close": decision.get("close"),
            "reason_code": reason_code,
            "reason_detail": detail,
        }

    @staticmethod
    def _final_positions_frame(positions: dict[str, Position], price_frame: pd.DataFrame) -> pd.DataFrame:
        rows = []
        for symbol, position in positions.items():
            close = float(price_frame.loc[symbol, "close"]) if symbol in price_frame.index else 0.0
            rows.append(
                {
                    "symbol": symbol,
                    "industry": position.industry,
                    "bucket": position.bucket,
                    "shares": float(position.shares),
                    "avg_cost": float(position.avg_cost),
                    "latest_close": close,
                    "market_value": float(position.shares) * close,
                    "unrealized_pnl": float(position.shares) * (close - float(position.avg_cost)),
                    "entry_date": position.entry_date,
                    "last_buy_date": position.last_buy_date,
                    "current_position_tranches": position.current_position_tranches,
                    "current_weight": position.current_weight,
                    "last_fill_price": position.last_fill_price,
                }
            )
        return pd.DataFrame(rows)

    @staticmethod
    def _stable_reason_code(raw: object) -> str:
        mapping = {
            "REGIME_OPEN_BLOCK": "MARKET_REGIME_BLOCK",
            "REGIME_CAP_BLOCK": "TOTAL_EXPOSURE_LIMIT",
            "INSUFFICIENT_CASH": "CASH_INSUFFICIENT",
            "MIN_TRADE_VALUE": "MIN_TRADE_AMOUNT",
            "ROUND_LOT_BLOCK": "LOT_SIZE_ZERO",
            "HARD_ADD_BAN": "HARD_ADD_BAN",
            "CYCLE_TRAP": "HARD_ADD_BAN",
            "DATA_STALE_BLOCK": "MISSING_REQUIRED_FIELD",
            "NOT_IN_EFFECTIVE_UNIVERSE": "NOT_IN_EFFECTIVE_UNIVERSE",
            "DAILY_POSITION_LIMIT": "TOTAL_EXPOSURE_LIMIT",
            "MISSING_SHARE_COUNT": "UNKNOWN",
            "FROZEN_NOT_BUYABLE": "HARD_ADD_BAN",
            "CASH_INSUFFICIENT_AT_FILL": "CASH_INSUFFICIENT",
            "TOTAL_EXPOSURE_LIMIT_AT_FILL": "TOTAL_EXPOSURE_LIMIT",
            "SINGLE_NAME_LIMIT_AT_FILL": "SINGLE_NAME_LIMIT",
            "MIN_TRADE_AMOUNT_AT_FILL": "MIN_TRADE_AMOUNT",
            "CASH_CLIPPED_AT_FILL": "CASH_INSUFFICIENT",
            "TOTAL_EXPOSURE_CLIPPED_AT_FILL": "TOTAL_EXPOSURE_LIMIT",
            "SINGLE_NAME_CLIPPED_AT_FILL": "SINGLE_NAME_LIMIT",
            "MISSING_FILL_PRICE": "MISSING_REQUIRED_FIELD",
            "VALUATION_QUANTILE_MISSING": "VALUATION_QUANTILE_MISSING",
            "INDUSTRY_VALUATION_QUANTILE_MISSING": "INDUSTRY_VALUATION_QUANTILE_MISSING",
        }
        if raw is None or pd.isna(raw):
            return "UNKNOWN"
        return mapping.get(str(raw), str(raw) if str(raw) in {
            "NOT_IN_EFFECTIVE_UNIVERSE",
            "MARKET_REGIME_BLOCK",
            "CASH_INSUFFICIENT",
            "TOTAL_EXPOSURE_LIMIT",
            "SINGLE_NAME_LIMIT",
            "MIN_TRADE_AMOUNT",
            "LOT_SIZE_ZERO",
            "HARD_ADD_BAN",
            "ALREADY_AT_OR_ABOVE_TARGET",
            "MISSING_REQUIRED_FIELD",
            "QUALITY_FAIL",
            "VALUATION_FAIL",
            "VALUATION_QUANTILE_MISSING",
            "INDUSTRY_VALUATION_QUANTILE_MISSING",
            "PRICE_TRIGGER_FAIL",
            "MISSING_FILL_PRICE",
            "UNKNOWN",
        } else "UNKNOWN")

    def _daily_diagnostic_record(
        self,
        signal_date: str,
        todays: pd.DataFrame,
        decisions: list[dict],
        benchmark_until_today: pd.DataFrame,
        regime: dict,
        nav: float,
        cash_before: float,
        positions: dict[str, Position],
        executed_trades: list[dict],
    ) -> dict:
        decision_frame = pd.DataFrame(decisions)
        if decision_frame.empty:
            decision_frame = pd.DataFrame(columns=["action_enum", "intended_action_enum", "blocked_reason"])
        current_exposure = max(0.0, nav - cash_before) / max(nav, 1e-9)
        intended = decision_frame.get("intended_action_enum", pd.Series(dtype=object)).fillna("")
        actions = decision_frame.get("action_enum", pd.Series(dtype=object)).fillna("")
        blocked = decision_frame.get("blocked_reason", pd.Series(dtype=object))
        reason_codes = blocked.map(self._stable_reason_code) if not blocked.empty else pd.Series(dtype=object)
        executed_buy = sum(1 for item in executed_trades if item.get("action") in {"BUY_1", "BUY_2", "BUY_3"})
        executed_sell = sum(1 for item in executed_trades if item.get("action") in {"REDUCE", "SELL_ALL"})
        is_a_share = todays["is_a_share"].astype(bool) if "is_a_share" in todays.columns else pd.Series(True, index=todays.index)
        is_st = todays["is_st"].astype(bool) if "is_st" in todays.columns else pd.Series(False, index=todays.index)
        industry = todays["industry"] if "industry" in todays.columns else pd.Series(pd.NA, index=todays.index)
        market_cap = pd.to_numeric(
            todays["market_cap_billion"] if "market_cap_billion" in todays.columns else pd.Series(0, index=todays.index),
            errors="coerce",
        ).fillna(0)
        avg_amount = pd.to_numeric(
            todays["avg_amount_60d_million"] if "avg_amount_60d_million" in todays.columns else pd.Series(0, index=todays.index),
            errors="coerce",
        ).fillna(0)
        passed_base = todays[
            is_a_share
            & ~is_st
            & industry.notna()
            & (market_cap > 0)
            & (avg_amount > 0)
        ]
        passed_bucket = todays[todays.get("bucket", pd.Series(pd.NA, index=todays.index)).notna()]
        stock_q = pd.to_numeric(todays.get("stock_q_blended", pd.Series(100, index=todays.index)), errors="coerce").fillna(100)
        industry_q = pd.to_numeric(todays.get("industry_q_blended", pd.Series(100, index=todays.index)), errors="coerce").fillna(100)
        passed_valuation = todays[(stock_q <= 40) & (industry_q <= 55)]
        passed_quality = passed_valuation[passed_valuation.get("quality_pass", pd.Series(False, index=passed_valuation.index)).astype(bool)]
        close = pd.to_numeric(todays.get("close", pd.Series(0, index=todays.index)), errors="coerce").fillna(0)
        ma120 = pd.to_numeric(todays.get("ma120", pd.Series(0, index=todays.index)), errors="coerce").fillna(0)
        passed_price = todays[(ma120 > 0) & (close <= ma120)]
        return {
            "date": signal_date,
            "benchmark_close": float(benchmark_until_today["close"].iloc[-1]) if not benchmark_until_today.empty else None,
            "market_regime": regime["regime"],
            "max_total_exposure": float(regime["max_total_position"]),
            "current_total_exposure": current_exposure,
            "current_cash": cash_before,
            "effective_universe_size": int(todays.get("in_effective_universe", pd.Series(False, index=todays.index)).astype(bool).sum()),
            "holdings_count": int(len(positions)),
            "decision_scope_size": int(len(todays)),
            "candidates_seen": int(len(todays)),
            "passed_base_filter_count": int(len(passed_base)),
            "passed_bucket_filter_count": int(len(passed_bucket)),
            "passed_valuation_filter_count": int(len(passed_valuation)),
            "passed_quality_filter_count": int(len(passed_quality)),
            "passed_price_trigger_count": int(len(passed_price)),
            "raw_buy_signal_count": int(intended.isin(["BUY_1", "BUY_2", "BUY_3"]).sum()),
            "raw_sell_signal_count": int(intended.isin(["REDUCE", "SELL_ALL"]).sum()),
            "blocked_by_universe_count": int((reason_codes == "NOT_IN_EFFECTIVE_UNIVERSE").sum()),
            "blocked_by_market_regime_count": int((reason_codes == "MARKET_REGIME_BLOCK").sum()),
            "blocked_by_cash_count": int((reason_codes == "CASH_INSUFFICIENT").sum()),
            "blocked_by_position_limit_count": int((reason_codes == "TOTAL_EXPOSURE_LIMIT").sum()),
            "blocked_by_single_name_limit_count": int((reason_codes == "SINGLE_NAME_LIMIT").sum()),
            "blocked_by_min_trade_amount_count": int((reason_codes == "MIN_TRADE_AMOUNT").sum()),
            "blocked_by_lot_size_count": int((reason_codes == "LOT_SIZE_ZERO").sum()),
            "blocked_by_existing_position_count": int((reason_codes == "ALREADY_AT_OR_ABOVE_TARGET").sum()),
            "blocked_by_hard_add_ban_count": int((reason_codes == "HARD_ADD_BAN").sum()),
            "executable_buy_count": int(actions.isin(["BUY_1", "BUY_2", "BUY_3"]).sum()),
            "executable_sell_count": int(actions.isin(["REDUCE", "SELL_ALL"]).sum()),
            "executed_buy_count": int(executed_buy),
            "executed_sell_count": int(executed_sell),
        }

    def _blocked_signal_records(self, signal_date: str, decisions: list[dict]) -> list[dict]:
        records: list[dict] = []
        for decision in decisions:
            intended_action = decision.get("intended_action_enum", decision.get("action_enum"))
            if intended_action not in {"BUY_1", "BUY_2", "BUY_3", "REDUCE", "SELL_ALL"}:
                continue
            if decision.get("action_enum") != "BLOCKED":
                continue
            reason_code = self._stable_reason_code(decision.get("blocked_reason"))
            records.append(
                {
                    "date": signal_date,
                    "ts_code": decision.get("symbol"),
                    "symbol": decision.get("symbol"),
                    "name": decision.get("name"),
                    "bucket": decision.get("bucket"),
                    "intended_action": intended_action,
                    "intended_signal_level": decision.get("signal_level", intended_action),
                    "intended_target_weight": decision.get("intended_target_weight"),
                    "current_weight": decision.get("current_weight"),
                    "close": decision.get("close"),
                    "stock_valuation_quantile": decision.get("stock_valuation_quantile"),
                    "stock_valuation_quantile_source_field": decision.get("stock_valuation_quantile_source_field"),
                    "industry_valuation_quantile": decision.get("industry_valuation_quantile"),
                    "industry_valuation_quantile_source_field": decision.get("industry_valuation_quantile_source_field"),
                    "valuation_fallback_used": decision.get("valuation_fallback_used", False),
                    "valuation_fallback_reason": decision.get("valuation_fallback_reason", ""),
                    "reason_code": reason_code,
                    "reason_detail": decision.get("action_reason"),
                }
            )
        return records

    def _metrics(self, nav_frame: pd.DataFrame, trade_frame: pd.DataFrame, detailed_frame: pd.DataFrame | None = None) -> dict:
        if nav_frame.empty:
            return {"cagr": 0.0, "max_drawdown": 0.0, "win_rate": 0.0, "sharpe": 0.0}
        nav = nav_frame["nav"].astype(float)
        returns = nav.pct_change().dropna()
        years = max(len(nav_frame) / 252, 1 / 252)
        cagr = (nav.iloc[-1] / self.initial_cash) ** (1 / years) - 1
        cumulative_return = nav.iloc[-1] / self.initial_cash - 1
        drawdown = nav / nav.cummax() - 1
        wins = (
            (trade_frame["realized_pnl"] > 0).sum() / max((trade_frame["action"].isin(["REDUCE", "SELL_ALL"])).sum(), 1)
            if not trade_frame.empty
            else 0.0
        )
        sharpe = (
            returns.mean() / returns.std(ddof=0) * sqrt(252)
            if not returns.empty and returns.std(ddof=0) > 0
            else 0.0
        )
        volatility = returns.std(ddof=0) * sqrt(252) if not returns.empty else 0.0
        sell_trades = int((trade_frame["action"].isin(["REDUCE", "SELL_ALL"])).sum()) if not trade_frame.empty else 0
        buy_trades = int((trade_frame["action"].isin(["BUY_1", "BUY_2", "BUY_3"])).sum()) if not trade_frame.empty else 0
        realized_pnl = float(trade_frame["realized_pnl"].sum()) if not trade_frame.empty else 0.0
        total_fees = float(detailed_frame["fee"].sum()) if detailed_frame is not None and not detailed_frame.empty and "fee" in detailed_frame else 0.0
        total_tax = float(detailed_frame["tax"].sum()) if detailed_frame is not None and not detailed_frame.empty and "tax" in detailed_frame else 0.0
        total_slippage = float(detailed_frame["slippage_cost"].sum()) if detailed_frame is not None and not detailed_frame.empty and "slippage_cost" in detailed_frame else 0.0
        holding_days = (
            pd.to_numeric(detailed_frame.loc[detailed_frame["side"] == "SELL", "holding_days"], errors="coerce").dropna()
            if detailed_frame is not None and not detailed_frame.empty and "holding_days" in detailed_frame
            else pd.Series(dtype=float)
        )
        wins_sum = float(trade_frame.loc[trade_frame["realized_pnl"] > 0, "realized_pnl"].sum()) if not trade_frame.empty else 0.0
        losses_sum = abs(float(trade_frame.loc[trade_frame["realized_pnl"] < 0, "realized_pnl"].sum())) if not trade_frame.empty else 0.0
        exposure = pd.to_numeric(nav_frame.get("exposure", pd.Series(dtype=float)), errors="coerce")
        holdings = pd.to_numeric(nav_frame.get("holdings_count", pd.Series(dtype=float)), errors="coerce")
        return {
            "cagr": float(cagr),
            "execution_mode": self.execution_mode,
            "annual_return": float(cagr),
            "cumulative_return": float(cumulative_return),
            "max_drawdown": float(drawdown.min()),
            "win_rate": float(wins),
            "sharpe": float(sharpe),
            "calmar": float(cagr / abs(drawdown.min())) if drawdown.min() < 0 else 0.0,
            "volatility": float(volatility),
            "profit_factor": float(wins_sum / losses_sum) if losses_sum > 0 else (float("inf") if wins_sum > 0 else 0.0),
            "total_trades": int(len(trade_frame)),
            "buy_trades": buy_trades,
            "sell_trades": sell_trades,
            "avg_holding_days": float(holding_days.mean()) if not holding_days.empty else 0.0,
            "median_holding_days": float(holding_days.median()) if not holding_days.empty else 0.0,
            "avg_daily_exposure": float(exposure.mean()) if not exposure.empty else 0.0,
            "max_daily_exposure": float(exposure.max()) if not exposure.empty else 0.0,
            "exposure_active_days_ratio": float((exposure > 0.001).mean()) if not exposure.empty else 0.0,
            "avg_positions": float(holdings.mean()) if not holdings.empty else 0.0,
            "max_positions": int(holdings.max()) if not holdings.empty else 0,
            "turnover": float(detailed_frame["amount"].abs().sum() / max(self.initial_cash, 1e-9)) if detailed_frame is not None and not detailed_frame.empty else 0.0,
            "total_fees": total_fees,
            "total_tax": total_tax,
            "total_slippage": total_slippage,
            "realized_pnl": realized_pnl,
            "unrealized_pnl": float(nav.iloc[-1] - self.initial_cash - realized_pnl) if not nav.empty else 0.0,
        }
