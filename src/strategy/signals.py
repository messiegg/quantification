from __future__ import annotations

from collections import Counter
from math import ceil

import pandas as pd

from src.strategy.grid import can_add_grid_tranche, can_reduce_grid_tranche, compute_grid_step
from src.strategy.valuation_resolution import resolve_industry_valuation_quantile, resolve_stock_valuation_quantile


ACTIONS = {
    "BUY_1",
    "BUY_2",
    "BUY_3",
    "HOLD",
    "HOLD_FROZEN",
    "HOLD_WITH_PENDING_ADD",
    "REDUCE",
    "SELL_ALL",
    "EMPTY",
    "BLOCKED",
    "DATA_ERROR",
}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        numeric = float(value)
    except (TypeError, ValueError):
        return default
    if pd.isna(numeric):
        return default
    return numeric


def _safe_int(value: object, default: int = 0) -> int:
    try:
        numeric = int(float(value))
    except (TypeError, ValueError):
        return default
    return numeric if numeric >= 0 else default


def _close_to_ma(row: dict, ma_field: str) -> float:
    return float(row["close"]) / float(row[ma_field]) if _safe_float(row.get(ma_field)) else float("inf")


def _risk_off_allows_open(row: dict, regime: str, strategy_cfg: dict) -> bool:
    if regime != "risk_off":
        return True
    risk_off_cfg = strategy_cfg["market_regime"]["risk_off_opening_rules"]
    if row["bucket"] not in set(risk_off_cfg["allow_new_buckets"]):
        return False
    return _safe_float(row.get("stock_q_blended"), default=100.0) <= float(risk_off_cfg["defensive_dividend_max_stock_q_blended"])


def _entry_rule(row: dict, bucket_cfg: dict, current_tranches: int, max_tranches: int) -> tuple[str | None, list[str]]:
    next_tranche = current_tranches + 1
    if next_tranche > max_tranches:
        return None, []
    level_name = f"BUY_{next_tranche}"
    rule = bucket_cfg["buy_levels"].get(level_name)
    if not rule:
        return None, []
    reason_codes: list[str] = []
    if _safe_float(row.get("stock_q_blended"), default=100.0) <= float(rule["stock_q_blended_max"]):
        reason_codes.append("LOW_VALUATION")
    if _safe_float(row.get("industry_q_blended"), default=100.0) <= float(rule["industry_q_blended_max"]):
        reason_codes.append("INDUSTRY_CHEAP")
    if row["bucket"] == "defensive_dividend":
        if _close_to_ma(row, "ma120") <= float(rule["close_to_ma120_max"]):
            reason_codes.append("MA120_DISCOUNT")
        passed = bool(
            _safe_float(row.get("stock_q_blended"), default=100.0) <= float(rule["stock_q_blended_max"])
            and _safe_float(row.get("industry_q_blended"), default=100.0) <= float(rule["industry_q_blended_max"])
            and _close_to_ma(row, "ma120") <= float(rule["close_to_ma120_max"])
            and bool(row.get("quality_pass", False))
        )
    else:
        close_gt_ma20 = not rule.get("close_gt_ma20") or _safe_float(row.get("close")) > _safe_float(row.get("ma20"))
        close_gt_ma60 = not rule.get("close_gt_ma60") or _safe_float(row.get("close")) > _safe_float(row.get("ma60"))
        ma20_slope_ok = _safe_float(row.get("ma20_slope_10d"), default=-10**9) >= float(rule.get("ma20_slope_10d_min", -10**9))
        ma60_slope_ok = _safe_float(row.get("ma60_slope_20d"), default=-10**9) >= float(rule.get("ma60_slope_20d_min", -10**9))
        if close_gt_ma20 or close_gt_ma60 or ma20_slope_ok or ma60_slope_ok:
            reason_codes.append("TREND_CONFIRMED")
        passed = bool(
            _safe_float(row.get("stock_q_blended"), default=100.0) <= float(rule["stock_q_blended_max"])
            and _safe_float(row.get("industry_q_blended"), default=100.0) <= float(rule["industry_q_blended_max"])
            and close_gt_ma20
            and close_gt_ma60
            and ma20_slope_ok
            and ma60_slope_ok
            and bool(row.get("quality_pass", False))
            and not bool(row.get("cycle_peak_trap", False))
        )
    return (level_name if passed else None), reason_codes


def compute_entry_signal_score(row: dict, bucket_cfg: dict, level_name: str) -> float:
    rule = bucket_cfg["buy_levels"][level_name]
    stock_threshold = float(rule["stock_q_blended_max"])
    industry_threshold = float(rule["industry_q_blended_max"])
    stock_depth = max(stock_threshold - _safe_float(row.get("stock_q_blended"), default=stock_threshold), 0.0) / max(stock_threshold, 1.0) * 100.0
    industry_depth = max(industry_threshold - _safe_float(row.get("industry_q_blended"), default=industry_threshold), 0.0) / max(industry_threshold, 1.0) * 100.0
    valuation_score = stock_depth * 0.65 + industry_depth * 0.35
    if row["bucket"] == "defensive_dividend":
        ma_trigger = float(rule["close_to_ma120_max"])
        trend_score = max(ma_trigger - _close_to_ma(row, "ma120"), 0.0) / max(ma_trigger, 1e-6) * 100.0
    else:
        close_over_ma20 = max((_safe_float(row.get("close")) / max(_safe_float(row.get("ma20"), default=1.0), 1e-6)) - 1.0, 0.0) * 100.0
        close_over_ma60 = max((_safe_float(row.get("close")) / max(_safe_float(row.get("ma60"), default=1.0), 1e-6)) - 1.0, 0.0) * 100.0
        slope_bonus = max(_safe_float(row.get("ma20_slope_10d")), 0.0) * 2000.0 + max(_safe_float(row.get("ma60_slope_20d")), 0.0) * 1000.0
        trend_score = min(100.0, close_over_ma20 + close_over_ma60 + slope_bonus)
    return round(min(100.0, valuation_score * 0.6 + trend_score * 0.4), 4)


def _priority_score(row: dict, entry_signal_score: float) -> float:
    universe_score = _safe_float(row.get("universe_final_score", row.get("final_score")), default=0.0)
    return round(universe_score * 0.60 + entry_signal_score * 0.40, 4)


def _profile_name(strategy_cfg: dict) -> str:
    return str(strategy_cfg.get("profile", strategy_cfg.get("strategy_profile", "")))


def _is_v2_strategy(strategy_cfg: dict) -> bool:
    return _profile_name(strategy_cfg).startswith("combined_v2")


def _control_flag(strategy_cfg: dict, name: str) -> bool:
    return bool((strategy_cfg.get("control_overrides", {}) or {}).get(name, False))


def _is_risk_guard_strategy(strategy_cfg: dict) -> bool:
    return _profile_name(strategy_cfg) == "combined_v2_1_risk_guard" or _control_flag(strategy_cfg, "risk_guard")


def _stock_valuation_quantile(row: dict, bucket: str) -> float:
    return _safe_float(resolve_stock_valuation_quantile(row, bucket, None).value, default=100.0)


def _industry_valuation_quantile(row: dict, bucket: str) -> float:
    return _safe_float(resolve_industry_valuation_quantile(row, bucket, None).value, default=100.0)


def _grid_step_for_row(row: dict, grid_cfg: dict) -> float:
    return compute_grid_step(_safe_float(row.get("atr20")), max(_safe_float(row.get("close")), 1e-9), grid_cfg)


def _action_for_target(current_tranches: int, target_tranches: int, holding_state: str) -> str:
    if holding_state == "FORCE_EXIT":
        return "SELL_ALL"
    if target_tranches == 0 and current_tranches > 0:
        return "SELL_ALL"
    if target_tranches < current_tranches:
        return "REDUCE"
    if target_tranches > current_tranches:
        return f"BUY_{target_tranches}"
    if holding_state == "FROZEN" and current_tranches > 0:
        return "HOLD_FROZEN"
    if current_tranches > 0:
        return "HOLD"
    return "EMPTY"


def compute_lot_aware_order(
    *,
    symbol: str,
    latest_price: float,
    current_position_shares: float,
    current_position_value: float,
    account_equity: float,
    available_cash: float,
    min_trade_value: float,
    round_lot: int,
    max_single_stock_weight: float,
    target_position_value: float,
    intended_order_value: float,
    action_type: str,
    current_positions_count: int,
    max_positions: int,
    daily_new_position_count: int,
    max_new_positions_per_day: int,
    daily_add_count: int,
    max_adds_per_day: int,
) -> dict:
    price = _safe_float(latest_price)
    lot = max(1, int(round_lot or 1))
    equity = max(0.0, _safe_float(account_equity))
    cash = max(0.0, _safe_float(available_cash))
    min_trade = max(0.0, _safe_float(min_trade_value))
    current_value = max(0.0, _safe_float(current_position_value))
    target_value = max(0.0, _safe_float(target_position_value))
    intended_value = max(0.0, _safe_float(intended_order_value))
    max_single_weight = max(0.0, _safe_float(max_single_stock_weight))
    action = str(action_type).upper()
    lot_notional = price * lot if price > 0 else 0.0
    max_single_value = equity * max_single_weight
    remaining_capacity = max(0.0, max_single_value - current_value)
    minimum_order_value = max(min_trade, lot_notional)
    minimum_lots = ceil(minimum_order_value / lot_notional) if lot_notional > 0 else 0
    minimum_lot_order_value = minimum_lots * lot_notional
    payload = {
        "symbol": symbol,
        "action_type": action,
        "lot_notional": lot_notional,
        "minimum_lot_order_value": minimum_lot_order_value,
        "minimum_lots": minimum_lots,
        "max_single_position_value": max_single_value,
        "remaining_single_name_capacity": remaining_capacity,
        "executable": False,
        "executable_amount": 0.0,
        "executable_shares": 0,
        "block_reason": "",
        "pending_add_state": False,
        "pending_reason": "",
        "pending_until_condition": "",
        "execution_eligible_for_new_buy": False,
        "execution_ineligible_reason": "",
    }
    if price <= 0 or lot_notional <= 0 or equity <= 0:
        payload["block_reason"] = "MISSING_FILL_PRICE"
        payload["execution_ineligible_reason"] = "MISSING_FILL_PRICE"
        return payload

    def block(reason: str) -> dict:
        payload["block_reason"] = reason
        payload["execution_ineligible_reason"] = reason
        return payload

    if action == "NEW_BUY":
        if current_positions_count >= max_positions:
            return block("MAX_POSITIONS_LIMIT")
        if daily_new_position_count >= max_new_positions_per_day:
            return block("DAILY_NEW_POSITION_LIMIT")
        if lot_notional > max_single_value + 1e-9:
            return block("PRICE_TOO_HIGH_FOR_ACCOUNT_LOT")
        if lot_notional > cash + 1e-9:
            return block("CASH_INSUFFICIENT_FOR_ONE_LOT")
        if minimum_lot_order_value > max_single_value + 1e-9:
            return block("PRICE_TOO_HIGH_FOR_ACCOUNT_LOT")
        if minimum_lot_order_value > cash + 1e-9:
            return block("CASH_INSUFFICIENT")
        desired_value = min(target_value, max_single_value, cash)
        desired_lots = int(desired_value // lot_notional)
        if desired_lots < minimum_lots:
            desired_lots = minimum_lots
        order_value = desired_lots * lot_notional
        if order_value > max_single_value + 1e-9 or order_value > cash + 1e-9:
            order_value = minimum_lot_order_value
            desired_lots = minimum_lots
        if order_value > max_single_value + 1e-9:
            return block("PRICE_TOO_HIGH_FOR_ACCOUNT_LOT")
        if order_value > cash + 1e-9:
            return block("CASH_INSUFFICIENT")
        if desired_lots <= 0:
            return block("LOT_SIZE_ZERO")
        payload["executable"] = True
        payload["execution_eligible_for_new_buy"] = True
        payload["executable_amount"] = float(order_value)
        payload["executable_shares"] = int(desired_lots * lot)
        return payload

    if action == "ADD":
        payload["pending_until_condition"] = (
            "remaining_single_name_capacity >= lot_notional and available_cash >= lot_notional "
            "and accumulated_target_gap >= lot_notional"
        )
        if daily_add_count >= max_adds_per_day:
            return block("DAILY_ADD_LIMIT")
        if remaining_capacity < lot_notional - 1e-9:
            payload["pending_add_state"] = True
            payload["pending_reason"] = "LOT_SIZE_ACCUMULATION_REQUIRED"
            return block("PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY")
        if lot_notional > cash + 1e-9:
            payload["pending_add_state"] = True
            payload["pending_reason"] = "LOT_SIZE_ACCUMULATION_REQUIRED"
            return block("CASH_INSUFFICIENT_FOR_ONE_LOT")
        accumulated_gap = min(max(target_value - current_value, intended_value), intended_value if intended_value > 0 else target_value)
        if accumulated_gap < lot_notional - 1e-9:
            payload["pending_add_state"] = True
            payload["pending_reason"] = "LOT_SIZE_ACCUMULATION_REQUIRED"
            return block("LOT_SIZE_ACCUMULATION_REQUIRED")
        desired_value = min(accumulated_gap, remaining_capacity, cash)
        desired_lots = int(desired_value // lot_notional)
        if desired_lots <= 0:
            payload["pending_add_state"] = True
            payload["pending_reason"] = "LOT_SIZE_ACCUMULATION_REQUIRED"
            return block("LOT_SIZE_ACCUMULATION_REQUIRED")
        order_value = desired_lots * lot_notional
        if order_value < min_trade - 1e-9:
            minimum_add_lots = ceil(min_trade / lot_notional)
            minimum_add_value = minimum_add_lots * lot_notional
            if minimum_add_value <= remaining_capacity + 1e-9 and minimum_add_value <= cash + 1e-9:
                desired_lots = minimum_add_lots
                order_value = minimum_add_value
            else:
                payload["pending_add_state"] = True
                payload["pending_reason"] = "LOT_SIZE_ACCUMULATION_REQUIRED"
                return block("LOT_SIZE_ACCUMULATION_REQUIRED")
        if order_value > remaining_capacity + 1e-9:
            payload["pending_add_state"] = True
            payload["pending_reason"] = "LOT_SIZE_ACCUMULATION_REQUIRED"
            return block("PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY")
        if order_value > cash + 1e-9:
            payload["pending_add_state"] = True
            payload["pending_reason"] = "LOT_SIZE_ACCUMULATION_REQUIRED"
            return block("CASH_INSUFFICIENT")
        payload["executable"] = True
        payload["executable_amount"] = float(order_value)
        payload["executable_shares"] = int(desired_lots * lot)
        return payload

    return block("UNKNOWN")


class SignalEngine:
    def __init__(self, strategy_cfg: dict, universe_rules_cfg: dict | None = None, account_cfg: dict | None = None) -> None:
        self.strategy_cfg = strategy_cfg
        self.universe_rules_cfg = universe_rules_cfg or {}
        self.account_cfg = account_cfg or {}
        self.is_v2 = _is_v2_strategy(strategy_cfg)
        execution_cfg = self.account_cfg.get("execution", {}) if isinstance(self.account_cfg, dict) else {}
        position_sizing = self.account_cfg.get("position_sizing", {}) if isinstance(self.account_cfg, dict) else {}
        self.default_tranches = int(position_sizing.get("max_tranches_per_stock", strategy_cfg["execution"]["default_tranches"]))
        self.tranche_weight_map = {
            int(key): float(value)
            for key, value in (position_sizing.get("tranche_weights", {}) or {}).items()
        }
        if 0 not in self.tranche_weight_map:
            self.tranche_weight_map[0] = 0.0
        if not any(key > 0 for key in self.tranche_weight_map):
            target_universe = int(
                self.universe_rules_cfg.get("target_universe_size", strategy_cfg["execution"].get("equal_weight_target_universe_size", 16))
            )
            unit_weight = 1.0 / float(target_universe) / float(self.default_tranches)
            self.tranche_weight_map = {index: round(unit_weight * index, 6) for index in range(0, self.default_tranches + 1)}
        self.max_single_stock_weight = float(position_sizing.get("max_single_stock_weight", max(self.tranche_weight_map.values(), default=0.0)))
        self.round_lot = max(1, int(execution_cfg.get("round_lot", 100)))
        self.commission_rate = float(execution_cfg.get("commission_rate", strategy_cfg["execution"].get("fee_rate", 0.0)))
        self.stamp_duty_rate_sell = float(
            execution_cfg.get("stamp_duty_rate_sell", strategy_cfg["execution"].get("stamp_tax_rate", 0.0))
        )
        self.min_trade_value = float(position_sizing.get("min_trade_value", 0.0))
        strategy_execution = strategy_cfg.get("execution", {}) if isinstance(strategy_cfg, dict) else {}
        self.lot_aware_sizing = bool(strategy_execution.get("lot_aware_sizing", False))
        self.pending_add_state_enabled = bool(strategy_execution.get("pending_add_state", self.lot_aware_sizing))
        self.duplicate_blocked_signal_suppression = bool(
            strategy_execution.get("duplicate_blocked_signal_suppression", self.lot_aware_sizing)
        )

    def _bucket_cfg(self, bucket: str) -> dict:
        return self.strategy_cfg["buckets"].get(bucket, {})

    def _weight_for_tranches(self, tranches: int, bucket: str | None = None) -> float:
        tranches = max(0, int(tranches))
        if self.is_v2 and bucket:
            bucket_weights = self._bucket_cfg(bucket).get("tranche_weights", {})
            if bucket_weights:
                weights = {int(key): float(value) for key, value in bucket_weights.items()}
                if tranches in weights:
                    return weights[tranches]
                return weights.get(max(weights), 0.0)
        if tranches in self.tranche_weight_map:
            return float(self.tranche_weight_map[tranches])
        return float(self.tranche_weight_map.get(max(self.tranche_weight_map), 0.0))

    def _bucket_max_weight(self, bucket: str) -> float:
        if self.is_v2:
            return float(self._bucket_cfg(bucket).get("max_single_name_weight", self.max_single_stock_weight))
        return self.max_single_stock_weight

    def _hard_add_ban_v2(self, record: dict) -> bool:
        bucket = str(record.get("bucket"))
        if _safe_float(record.get("close")) < _safe_float(record.get("ma250")) and _safe_float(record.get("ma120_slope_20d")) < 0:
            return True
        if bool(record.get("fundamental_break")):
            return True
        if bucket == "cyclical_rotation" and bool(record.get("cycle_peak_trap")):
            return True
        if bool(record.get("data_stale")) or not bool(record.get("core_fields_complete", True)):
            return True
        if _safe_float(record.get("current_weight")) >= self._bucket_max_weight(bucket) - 1e-9:
            return True
        return False

    def _grid_add_ok_v2(self, record: dict) -> bool:
        if _control_flag(self.strategy_cfg, "disable_grid"):
            return False
        if self._hard_add_ban_v2(record):
            return False
        if bool(record.get("fundamental_break")):
            return False
        if not bool(record.get("thesis_still_valid", True)):
            return False
        grid_cfg = self.strategy_cfg["execution"]["grid_execution"]
        last_fill = _safe_float(record.get("last_fill_price"), default=_safe_float(record.get("close")))
        close = _safe_float(record.get("close"))
        if close > last_fill * (1.0 - _grid_step_for_row(record, grid_cfg)):
            return False
        if record.get("bucket") == "cyclical_rotation":
            if bool(record.get("cycle_peak_trap")):
                return False
            if _safe_float(record.get("ma20_slope_10d"), default=-1.0) < -0.01:
                return False
        return True

    def _grid_trim_ok_v2(self, record: dict) -> bool:
        if _control_flag(self.strategy_cfg, "disable_grid"):
            return False
        if int(record.get("current_position_tranches", 0)) <= 1:
            return False
        grid_cfg = self.strategy_cfg["execution"]["grid_execution"]
        last_fill = _safe_float(record.get("last_fill_price"), default=_safe_float(record.get("close")))
        close = _safe_float(record.get("close"))
        return bool(
            close >= last_fill * (1.0 + _grid_step_for_row(record, grid_cfg))
            and _stock_valuation_quantile(record, str(record.get("bucket"))) >= float(grid_cfg.get("reduce_extra_min_stock_q_blended", 55))
        )

    def _buy_level_v2(self, record: dict, current_tranches: int) -> tuple[int, str]:
        bucket = str(record.get("bucket"))
        bucket_cfg = self._bucket_cfg(bucket)
        final_score = _safe_float(record.get("universe_final_score", record.get("final_score")))
        stock_q = _stock_valuation_quantile(record, bucket)
        industry_q = _industry_valuation_quantile(record, bucket)
        close = _safe_float(record.get("close"))
        ma120 = _safe_float(record.get("ma120"), default=0.0)
        close_to_ma120 = close / ma120 if ma120 else float("inf")
        current_weight = _safe_float(record.get("current_weight"))
        if self._hard_add_ban_v2(record):
            return current_tranches, "hard_add_ban 阻断开仓或加仓。"

        if bucket == "defensive_dividend":
            if (
                not _control_flag(self.strategy_cfg, "disable_high_dividend_supplement")
                and _safe_float(record.get("dv_ttm")) >= 0.045
                and final_score >= 65
                and stock_q <= 45
                and close_to_ma120 <= 1.03
                and current_tranches == 0
            ):
                return 1, "高股息补充触发 BUY_1。"
            if current_tranches == 0:
                passed = bool(
                    final_score >= 55
                    and stock_q <= 40
                    and industry_q <= 55
                    and close_to_ma120 <= 1.00
                    and _safe_float(record.get("dv_ttm")) >= 0.025
                    and _safe_float(record.get("latest_net_profit")) > 0
                    and current_weight < self._weight_for_tranches(1, bucket)
                )
                return (1, "满足 defensive BUY_1。") if passed else (0, "未满足 defensive BUY_1。")
            if current_tranches == 1:
                elapsed_ok = _safe_int(record.get("days_since_last_buy")) >= 20 and close_to_ma120 <= 1.00
                passed = bool(
                    final_score >= 60
                    and stock_q <= 30
                    and industry_q <= 45
                    and close_to_ma120 <= 0.96
                    and current_weight < self._weight_for_tranches(2, bucket)
                    and (self._grid_add_ok_v2(record) or elapsed_ok)
                )
                return (2, "满足 defensive BUY_2。") if passed else (1, "未满足 defensive BUY_2 或网格加仓条件。")
            if current_tranches == 2:
                passed = bool(
                    final_score >= 65
                    and stock_q <= 20
                    and industry_q <= 35
                    and close_to_ma120 <= 0.92
                    and current_weight < self._weight_for_tranches(3, bucket)
                    and self._grid_add_ok_v2(record)
                    and not bool(record.get("fundamental_break"))
                )
                return (3, "满足 defensive BUY_3。") if passed else (2, "未满足 defensive BUY_3 或网格加仓条件。")
            return current_tranches, "已达到 defensive 最大分批。"

        pb_q = _safe_float(record.get("stock_pb_q_blended", stock_q), default=stock_q)
        industry_pb_q = _safe_float(record.get("industry_pb_q_blended", industry_q), default=industry_q)
        ma20 = _safe_float(record.get("ma20"))
        ma60 = _safe_float(record.get("ma60"))
        ma20_slope = _safe_float(record.get("ma20_slope_10d"), default=-1.0)
        if bool(record.get("cycle_peak_trap")):
            return current_tranches, "cycle_peak_trap 阻断周期股开仓或加仓。"
        if current_tranches == 0:
            passed = bool(
                final_score >= 55
                and pb_q <= 35
                and industry_pb_q <= 45
                and (close >= ma20 or ma20_slope >= 0)
                and close_to_ma120 <= 1.08
                and current_weight < self._weight_for_tranches(1, bucket)
            )
            return (1, "满足 cyclical BUY_1。") if passed else (0, "未满足 cyclical BUY_1。")
        if current_tranches == 1:
            elapsed_ok = _safe_int(record.get("days_since_last_buy")) >= 20 and ma20_slope >= 0
            passed = bool(
                final_score >= 60
                and pb_q <= 25
                and industry_pb_q <= 35
                and (close >= ma60 or (close >= ma20 and ma20_slope > 0))
                and current_weight < self._weight_for_tranches(2, bucket)
                and (self._grid_add_ok_v2(record) or elapsed_ok)
            )
            return (2, "满足 cyclical BUY_2。") if passed else (1, "未满足 cyclical BUY_2 或网格加仓条件。")
        if current_tranches == 2:
            passed = bool(
                final_score >= 65
                and pb_q <= 15
                and industry_pb_q <= 25
                and close >= ma60
                and ma20_slope >= 0
                and current_weight < self._weight_for_tranches(3, bucket)
                and self._grid_add_ok_v2(record)
            )
            return (3, "满足 cyclical BUY_3。") if passed else (2, "未满足 cyclical BUY_3 或网格加仓条件。")
        return current_tranches, "已达到 cyclical 最大分批。"

    def _sell_target_v2(self, record: dict, current_tranches: int) -> tuple[int, str, str]:
        bucket = str(record.get("bucket"))
        stock_q = _stock_valuation_quantile(record, bucket)
        industry_q = _industry_valuation_quantile(record, bucket)
        close = _safe_float(record.get("close"))
        ma20 = _safe_float(record.get("ma20"))
        ma60 = _safe_float(record.get("ma60"))
        ma120 = _safe_float(record.get("ma120"))
        ma250 = _safe_float(record.get("ma250"))
        ma120_slope = _safe_float(record.get("ma120_slope_20d"))
        holding_days = _safe_int(record.get("holding_days"))
        unrealized_pnl_pct = _safe_float(record.get("unrealized_pnl_pct"))
        min_trim_days = int(self.strategy_cfg["execution"].get("min_holding_days_for_soft_trim", 40))
        min_exit_days = int(self.strategy_cfg["execution"].get("min_holding_days_for_soft_exit", 60))

        if bool(record.get("fundamental_break")):
            return 0, "fundamental_break，强制清仓。", "fundamental_break"
        if not _control_flag(self.strategy_cfg, "disable_trend_stop") and close < ma250 and ma120_slope < 0 and unrealized_pnl_pct <= -0.12:
            return 0, "长期趋势破坏且亏损超过阈值，强制清仓。", "trend_stop"
        if bucket == "cyclical_rotation" and bool(record.get("cycle_peak_trap")) and close < ma60 and _safe_float(record.get("ma20_slope_10d")) < 0:
            return 0, "cycle_peak_trap 叠加趋势转弱，清仓。", "cycle_peak_trap_trend_break"

        if bucket == "defensive_dividend":
            if holding_days >= min_exit_days and (
                (stock_q >= 90 and ma120 and close >= 1.10 * ma120)
                or (industry_q >= 90 and stock_q >= 80)
            ):
                return 0, "防御股估值明显回归，清仓。", "valuation_reversion_exit"
            if holding_days >= min_trim_days and current_tranches > 1 and (
                (stock_q >= 65 and ma120 and close >= 1.05 * ma120)
                or self._grid_trim_ok_v2(record)
            ):
                return max(1, current_tranches - 1), "防御股估值回升或网格止盈，减一档。", "soft_trim"
        else:
            if holding_days >= min_exit_days and (stock_q >= 85 or industry_q >= 90):
                return 0, "周期股估值回归，清仓。", "valuation_reversion_exit"
            if holding_days >= min_trim_days and current_tranches > 1 and (
                (stock_q >= 60 and close >= ma20)
                or self._grid_trim_ok_v2(record)
            ):
                return max(1, current_tranches - 1), "周期股估值回升或网格止盈，减一档。", "soft_trim"
        return current_tranches, "继续持有。", ""

    def _apply_v2_buy_guards(
        self,
        record: dict,
        market_regime: dict,
        current_tranches: int,
        target_tranches: int,
        action_reason: str,
    ) -> tuple[int, str]:
        if target_tranches <= current_tranches:
            return target_tranches, action_reason
        regime = str(market_regime.get("regime", ""))
        bucket = str(record.get("bucket"))
        final_score = _safe_float(record.get("universe_final_score", record.get("final_score")))
        close = _safe_float(record.get("close"))
        ma60 = _safe_float(record.get("ma60"))
        ma120 = _safe_float(record.get("ma120"))
        ma20_slope = _safe_float(record.get("ma20_slope_10d"), default=-1.0)
        stock_q = _stock_valuation_quantile(record, bucket)
        industry_q = _industry_valuation_quantile(record, bucket)

        if _control_flag(self.strategy_cfg, "risk_off_no_new_buy") and regime == "risk_off":
            if current_tranches == 0:
                record["blocked_reason"] = "REGIME_OPEN_BLOCK"
            record["reason_codes"].append("REGIME_OPEN_BLOCK")
            return current_tranches, "risk_off_no_new_buy 对照：risk_off 不允许新开仓或加仓。"

        if not _is_risk_guard_strategy(self.strategy_cfg):
            return target_tranches, action_reason

        if regime == "risk_on":
            return target_tranches, action_reason

        if regime == "neutral" and bucket == "cyclical_rotation" and current_tranches == 0:
            passed = bool(
                stock_q <= 30
                and industry_q <= 35
                and (close >= ma60 or ma20_slope > 0)
                and final_score >= 60
            )
            if not passed:
                record["blocked_reason"] = "REGIME_OPEN_BLOCK"
                record["reason_codes"].append("REGIME_OPEN_BLOCK")
                return current_tranches, "v2_1 neutral 周期开仓风险约束未通过。"
            return target_tranches, action_reason

        if regime == "risk_off":
            if bucket == "cyclical_rotation":
                if current_tranches == 0:
                    record["blocked_reason"] = "REGIME_OPEN_BLOCK"
                record["reason_codes"].append("REGIME_OPEN_BLOCK")
                return current_tranches, "v2_1 risk_off 禁止 cyclical_rotation 新开仓和加仓。"
            if bucket == "defensive_dividend":
                if current_tranches > 0 or target_tranches > 1:
                    record["reason_codes"].append("REGIME_OPEN_BLOCK")
                    return current_tranches, "v2_1 risk_off defensive 只允许 BUY_1，不允许加仓。"
                passed = bool(
                    _safe_float(record.get("dv_ttm")) >= 0.035
                    and stock_q <= 30
                    and industry_q <= 40
                    and final_score >= 65
                    and ma120 > 0
                    and close <= ma120
                    and not self._hard_add_ban_v2(record)
                )
                if not passed:
                    record["blocked_reason"] = "REGIME_OPEN_BLOCK"
                    record["reason_codes"].append("REGIME_OPEN_BLOCK")
                    return current_tranches, "v2_1 risk_off defensive BUY_1 风险约束未通过。"
                return target_tranches, action_reason

        return target_tranches, action_reason

    def _base_decision_v2(self, record: dict, market_regime: dict, safe_mode: bool) -> dict:
        bucket = str(record.get("bucket"))
        current_tranches = int(record.get("current_position_tranches", 0))
        current_weight = _safe_float(record.get("current_weight"), default=self._weight_for_tranches(current_tranches, bucket))
        holding_state = record.get("holding_state", "NONE")
        record["current_position_tranches"] = current_tranches
        record["current_weight"] = round(current_weight, 6)
        record["current_shares"] = _safe_int(record.get("current_shares"))
        record["avg_cost"] = round(_safe_float(record.get("avg_cost")), 4)
        record["risk_flags"] = list(record.get("risk_flags", []))
        record["reason_codes"] = list(record.get("reason_codes", []))
        record["blocked_reason"] = record.get("blocked_reason")
        record["data_status"] = record.get("data_status", "ok")
        record["entry_signal_score"] = 0.0
        record["priority_score"] = round(_safe_float(record.get("universe_final_score", record.get("final_score"))), 4)
        stock_resolution = resolve_stock_valuation_quantile(record, bucket, None)
        industry_resolution = resolve_industry_valuation_quantile(record, bucket, None)
        record["stock_valuation_quantile"] = stock_resolution.value
        record["stock_valuation_quantile_source_field"] = stock_resolution.source_field
        record["stock_valuation_metric"] = stock_resolution.metric
        record["industry_valuation_quantile"] = industry_resolution.value
        record["industry_valuation_quantile_source_field"] = industry_resolution.source_field
        record["industry_valuation_metric"] = industry_resolution.metric
        record["valuation_fallback_used"] = bool(stock_resolution.fallback_used or industry_resolution.fallback_used)
        record["valuation_fallback_reason"] = ";".join(
            reason
            for reason in (stock_resolution.fallback_reason, industry_resolution.fallback_reason)
            if reason
        )
        if not stock_resolution.source_field:
            record["reason_codes"].append("VALUATION_QUANTILE_MISSING")
        if not industry_resolution.source_field:
            record["reason_codes"].append("INDUSTRY_VALUATION_QUANTILE_MISSING")

        if bool(record.get("cycle_peak_trap")):
            record["reason_codes"].append("CYCLE_TRAP")
            record["risk_flags"].append("cycle_trap")
        if bool(record.get("fundamental_break")):
            record["reason_codes"].append("FUNDAMENTAL_BREAK")
            record["risk_flags"].append("fundamental_break")
        if bool(record.get("data_stale")):
            record["reason_codes"].append("DATA_STALE_BLOCK")
            record["risk_flags"].append("data_stale")

        if current_tranches > 0:
            target_tranches, action_reason, exit_reason = self._sell_target_v2(record, current_tranches)
            if target_tranches == current_tranches and holding_state != "FROZEN" and not safe_mode:
                target_tranches, action_reason = self._buy_level_v2(record, current_tranches)
                target_tranches, action_reason = self._apply_v2_buy_guards(record, market_regime, current_tranches, target_tranches, action_reason)
            elif target_tranches == current_tranches and holding_state == "FROZEN":
                action_reason = "FROZEN 持仓不因出池直接卖出。"
                record["reason_codes"].append("FROZEN_NOT_BUYABLE")
            record["exit_reason"] = exit_reason
        else:
            if not bool(record.get("in_effective_universe", False)):
                target_tranches = 0
                action_reason = "不在 effective universe 中。"
                record["blocked_reason"] = "NOT_IN_EFFECTIVE_UNIVERSE"
            elif safe_mode:
                target_tranches = 0
                action_reason = "safe_mode 启用，仅做风险控制，不开新仓。"
                record["blocked_reason"] = "DATA_STALE_BLOCK"
                record["reason_codes"].append("DATA_STALE_BLOCK")
            elif market_regime["regime"] == "risk_off" and self.strategy_cfg["market_regime"].get("block_new_in_risk_off", False):
                target_tranches = 0
                action_reason = "risk_off 阻断新开仓。"
                record["blocked_reason"] = "REGIME_OPEN_BLOCK"
            else:
                target_tranches, action_reason = self._buy_level_v2(record, 0)
                target_tranches, action_reason = self._apply_v2_buy_guards(record, market_regime, 0, target_tranches, action_reason)
                if target_tranches == 0 and self._hard_add_ban_v2(record):
                    record["blocked_reason"] = "HARD_ADD_BAN"

        if target_tranches > current_tranches:
            level_name = f"BUY_{target_tranches}"
            record["entry_signal_score"] = compute_entry_signal_score(record, self._bucket_cfg(bucket), "BUY_1") if "buy_levels" in self._bucket_cfg(bucket) else 0.0
            record["signal_level"] = level_name
        elif target_tranches < current_tranches:
            record["signal_level"] = "SELL_ALL" if target_tranches == 0 else "SELL_HALF"
        else:
            record["signal_level"] = "HOLD"
        record["priority_score"] = round(
            _safe_float(record.get("universe_final_score", record.get("final_score")), default=0.0)
            + _safe_float(record.get("entry_signal_score")) * 0.1,
            4,
        )
        record["desired_target_tranches"] = target_tranches
        record["desired_target_weight"] = round(self._weight_for_tranches(target_tranches, bucket), 6)
        record["action_reason"] = action_reason
        return record

    def _base_decision(self, record: dict, market_regime: dict, safe_mode: bool) -> dict:
        if self.is_v2:
            return self._base_decision_v2(record, market_regime, safe_mode)
        bucket_cfg = self.strategy_cfg["buckets"].get(record["bucket"], {})
        current_tranches = int(record.get("current_position_tranches", 0))
        current_weight = _safe_float(record.get("current_weight"), default=self._weight_for_tranches(current_tranches))
        holding_state = record.get("holding_state", "NONE")
        record["current_position_tranches"] = current_tranches
        record["current_weight"] = round(current_weight, 6)
        record["current_shares"] = _safe_int(record.get("current_shares"))
        record["avg_cost"] = round(_safe_float(record.get("avg_cost")), 4)
        record["risk_flags"] = list(record.get("risk_flags", []))
        record["reason_codes"] = list(record.get("reason_codes", []))
        record["blocked_reason"] = record.get("blocked_reason")
        record["data_status"] = record.get("data_status", "ok")

        if bool(record.get("missing_from_features")):
            record["action_enum"] = "DATA_ERROR"
            record["action_reason"] = "决策范围内缺少当日特征，保留人工核查。"
            record["desired_target_tranches"] = current_tranches
            record["desired_target_weight"] = round(current_weight, 6)
            record["target_position_tranches"] = current_tranches
            record["target_weight"] = round(current_weight, 6)
            record["target_position_change"] = 0.0
            record["priority_score"] = 0.0
            record["entry_signal_score"] = 0.0
            return record

        if bool(record.get("cycle_peak_trap")):
            record["reason_codes"].append("CYCLE_TRAP")
            record["risk_flags"].append("cycle_trap")
        if bool(record.get("fundamental_break")):
            record["reason_codes"].append("FUNDAMENTAL_BREAK")
            record["risk_flags"].append("fundamental_break")
        if bool(record.get("data_stale")):
            record["reason_codes"].append("DATA_STALE_BLOCK")
            record["risk_flags"].append("data_stale")

        if holding_state == "FORCE_EXIT":
            record["desired_target_tranches"] = 0
            record["desired_target_weight"] = 0.0
            record["target_position_tranches"] = 0
            record["target_weight"] = 0.0
            record["target_position_change"] = round(-current_weight, 6)
            record["action_enum"] = "SELL_ALL"
            record["action_reason"] = "命中强制退出规则。"
            record["priority_score"] = 100.0
            record["entry_signal_score"] = 0.0
            return record

        if current_tranches > 0:
            position = {
                "current_position": current_weight,
                "remaining_tranches": max(0, self.default_tranches - current_tranches),
                "extra_tranches": int(record.get("extra_tranches", 0)),
                "last_fill_price": _safe_float(record.get("last_fill_price"), default=_safe_float(record.get("close"))),
            }
            if bool(record.get("fundamental_break")):
                target_tranches = 0
                action_reason = "基本面破坏，清仓退出。"
            elif record["bucket"] == "defensive_dividend" and (
                _safe_float(record.get("stock_q_blended")) >= float(bucket_cfg["sell_all"]["stock_q_blended_min"])
                or _safe_float(record.get("industry_q_blended")) >= float(bucket_cfg["sell_all"]["industry_q_blended_min"])
            ):
                target_tranches = 0
                action_reason = "估值过热，触发清仓。"
            elif record["bucket"] == "cyclical_rotation" and (
                _safe_float(record.get("stock_q_blended")) >= float(bucket_cfg["sell_all"]["stock_q_blended_min"])
                or _safe_float(record.get("industry_q_blended")) >= float(bucket_cfg["sell_all"]["industry_q_blended_min"])
                or (_safe_float(record.get("close")) < _safe_float(record.get("ma60")) and _safe_float(record.get("ma20_slope_10d")) < 0)
            ):
                target_tranches = 0
                action_reason = "周期趋势转弱，触发清仓。"
            elif can_reduce_grid_tranche(record, position, self.strategy_cfg["execution"]["grid_execution"]):
                target_tranches = max(0, current_tranches - 1)
                action_reason = "触发网格减仓。"
            elif record["bucket"] == "defensive_dividend" and (
                _safe_float(record.get("stock_q_blended")) >= float(bucket_cfg["reduce"]["stock_q_blended_min"])
                and _close_to_ma(record, "ma120") >= float(bucket_cfg["reduce"]["close_to_ma120_min"])
            ):
                target_tranches = max(0, current_tranches - 1)
                action_reason = "估值回升至减仓区间。"
            elif record["bucket"] == "cyclical_rotation" and (
                _safe_float(record.get("stock_q_blended")) >= float(bucket_cfg["reduce"]["stock_q_blended_min"])
                and _safe_float(record.get("close")) >= _safe_float(record.get("ma20"))
            ):
                target_tranches = max(0, current_tranches - 1)
                action_reason = "周期估值回升，减仓锁定收益。"
            elif holding_state == "FROZEN":
                target_tranches = current_tranches
                action_reason = "已冻结持仓，仅观察或风险控制。"
                record["reason_codes"].append("FROZEN_NOT_BUYABLE")
            elif safe_mode:
                target_tranches = current_tranches
                action_reason = "safe_mode 启用，仅做风险控制，不开新仓。"
            else:
                next_level, reason_codes = _entry_rule(record, bucket_cfg, current_tranches, self.default_tranches)
                record["reason_codes"].extend(reason_codes)
                if next_level and can_add_grid_tranche(record, position, self.strategy_cfg["execution"]["grid_execution"]):
                    target_tranches = min(self.default_tranches, current_tranches + 1)
                    action_reason = "满足下一笔买点并通过网格补仓条件。"
                else:
                    target_tranches = current_tranches
                    action_reason = "持仓继续观察。"
        else:
            if not bool(record.get("in_effective_universe", False)):
                target_tranches = 0
                action_reason = "不在 effective universe 中。"
            elif safe_mode:
                target_tranches = 0
                action_reason = "safe_mode 启用，仅做风险控制，不开新仓。"
                record["blocked_reason"] = "DATA_STALE_BLOCK"
                record["reason_codes"].append("DATA_STALE_BLOCK")
            elif bool(record.get("cycle_peak_trap")):
                target_tranches = 0
                action_reason = "命中周期高点陷阱过滤器。"
                record["blocked_reason"] = "CYCLE_TRAP"
            elif not _risk_off_allows_open(record, market_regime["regime"], self.strategy_cfg):
                target_tranches = 0
                action_reason = f"当前市场 {market_regime['regime']}，禁止该 bucket 新开仓。"
                record["blocked_reason"] = "REGIME_OPEN_BLOCK"
            else:
                next_level, reason_codes = _entry_rule(record, bucket_cfg, 0, self.default_tranches)
                record["reason_codes"].extend(reason_codes)
                if next_level:
                    target_tranches = 1
                    action_reason = "满足第一笔买点。"
                else:
                    target_tranches = 0
                    action_reason = "未满足开仓条件。"

        entry_signal_score = 0.0
        if target_tranches > current_tranches:
            level_name = f"BUY_{target_tranches}"
            entry_signal_score = compute_entry_signal_score(record, bucket_cfg, level_name)
        record["entry_signal_score"] = round(entry_signal_score, 4)
        record["priority_score"] = _priority_score(record, entry_signal_score) if target_tranches > current_tranches else round(
            _safe_float(record.get("universe_final_score", record.get("final_score")), default=0.0),
            4,
        )
        record["desired_target_tranches"] = target_tranches
        record["desired_target_weight"] = round(self._weight_for_tranches(target_tranches), 6)
        record["action_reason"] = action_reason
        return record

    def _merge_position_fields(self, decisions: list[dict], positions: pd.DataFrame) -> None:
        if positions.empty or not {"symbol"} <= set(positions.columns):
            return
        lookup = positions.set_index("symbol").to_dict(orient="index")
        for decision in decisions:
            position = lookup.get(decision["symbol"])
            if not position:
                continue
            for field in ("current_shares", "avg_cost", "current_position_tranches", "current_weight", "extra_tranches", "last_fill_price"):
                if field not in decision or pd.isna(decision.get(field)):
                    decision[field] = position.get(field)

    def _reset_to_current(self, decision: dict, action_reason: str | None = None) -> dict:
        decision["target_position_tranches"] = int(decision["current_position_tranches"])
        decision["target_weight"] = round(_safe_float(decision["current_weight"]), 6)
        decision["target_position_change"] = 0.0
        decision["target_shares"] = _safe_int(decision.get("current_shares"))
        decision["delta_shares"] = 0
        decision["rounded_lots"] = 0
        decision["estimated_turnover"] = 0.0
        decision["estimated_commission"] = 0.0
        decision["estimated_stamp_duty"] = 0.0
        decision["estimated_total_cash_impact"] = 0.0
        decision["target_price_reference"] = round(_safe_float(decision.get("close")), 4) if _safe_float(decision.get("close")) > 0 else None
        decision["target_order_value"] = 0.0
        if action_reason:
            decision["action_reason"] = action_reason
        return decision

    def _rounded_target_shares(self, target_value: float, price: float) -> int:
        if target_value <= 0 or price <= 0:
            return 0
        raw_shares = int(target_value // price)
        return raw_shares // self.round_lot * self.round_lot

    def _lot_aware_buy_plan(
        self,
        decision: dict,
        action_enum: str,
        latest_total_equity: float,
        price: float,
        current_shares: int,
        available_cash: float,
        current_positions_count: int,
        max_positions: int,
        daily_new_position_count: int,
        max_new_positions_per_day: int,
        daily_add_count: int,
        max_adds_per_day: int,
    ) -> tuple[dict, float]:
        desired_target_weight = round(_safe_float(decision.get("desired_target_weight", decision.get("target_weight"))), 6)
        desired_target_tranches = int(decision.get("desired_target_tranches", decision["current_position_tranches"]))
        current_value = current_shares * price
        target_value = desired_target_weight * latest_total_equity
        intended_order_value = max(0.0, target_value - current_value)
        current_tranches = int(decision.get("current_position_tranches", 0))
        action_type = "NEW_BUY" if current_tranches <= 0 and current_shares <= 0 else "ADD"
        plan = compute_lot_aware_order(
            symbol=str(decision.get("symbol", "")),
            latest_price=price,
            current_position_shares=current_shares,
            current_position_value=current_value,
            account_equity=latest_total_equity,
            available_cash=max(0.0, available_cash) / max(1.0 + self.commission_rate, 1e-9),
            min_trade_value=self.min_trade_value,
            round_lot=self.round_lot,
            max_single_stock_weight=self._bucket_max_weight(str(decision.get("bucket", ""))),
            target_position_value=target_value,
            intended_order_value=intended_order_value,
            action_type=action_type,
            current_positions_count=current_positions_count,
            max_positions=max_positions,
            daily_new_position_count=daily_new_position_count,
            max_new_positions_per_day=max_new_positions_per_day,
            daily_add_count=daily_add_count,
            max_adds_per_day=max_adds_per_day,
        )
        for field in (
            "lot_notional",
            "minimum_lot_order_value",
            "max_single_position_value",
            "remaining_single_name_capacity",
            "execution_eligible_for_new_buy",
            "execution_ineligible_reason",
            "pending_add_state",
            "pending_reason",
            "pending_until_condition",
        ):
            decision[field] = plan.get(field)
        decision["lot_aware_sizing"] = True
        decision["action_type"] = action_type
        if plan.get("executable"):
            delta_shares = int(plan["executable_shares"])
            target_shares = current_shares + delta_shares
            estimated_turnover = round(float(plan["executable_amount"]), 2)
            estimated_commission = round(estimated_turnover * self.commission_rate, 2)
            actual_target_weight = round((target_shares * price) / latest_total_equity, 6)
            decision["action_enum"] = action_enum
            decision["target_position_tranches"] = desired_target_tranches
            decision["target_weight"] = actual_target_weight
            decision["target_position_change"] = round(actual_target_weight - _safe_float(decision["current_weight"]), 6)
            decision["target_shares"] = target_shares
            decision["delta_shares"] = delta_shares
            decision["rounded_lots"] = int(delta_shares // self.round_lot)
            decision["estimated_turnover"] = estimated_turnover
            decision["estimated_commission"] = estimated_commission
            decision["estimated_stamp_duty"] = 0.0
            decision["estimated_total_cash_impact"] = round(-(estimated_turnover + estimated_commission), 2)
            decision["target_order_value"] = estimated_turnover
            return decision, max(0.0, estimated_turnover + estimated_commission)

        reason = str(plan.get("block_reason") or plan.get("pending_reason") or "LOT_SIZE_ZERO")
        decision["blocked_reason"] = reason
        decision["reason_codes"].append(reason)
        if plan.get("pending_reason") and plan.get("pending_reason") != reason:
            decision["reason_codes"].append(str(plan["pending_reason"]))
        if action_type == "ADD" and self.pending_add_state_enabled and plan.get("pending_add_state"):
            decision["action_enum"] = "HOLD_WITH_PENDING_ADD"
            self._reset_to_current(decision, "加仓目标、现金或剩余单票容量尚未同时满足一手，进入 pending add。")
            decision["action_enum"] = "HOLD_WITH_PENDING_ADD"
            decision["pending_add_state"] = True
            decision["pending_reason"] = plan.get("pending_reason") or "LOT_SIZE_ACCUMULATION_REQUIRED"
            decision["pending_until_condition"] = plan.get("pending_until_condition")
            decision["execution_ineligible_reason"] = reason
            return decision, 0.0
        decision["action_enum"] = "BLOCKED"
        self._reset_to_current(decision, "买入请求不满足 100 股整手、现金或单票上限。")
        decision["blocked_reason"] = reason
        decision["lot_aware_sizing"] = True
        decision["execution_ineligible_reason"] = reason
        return decision, 0.0

    def _execution_plan(
        self,
        decision: dict,
        action_enum: str,
        latest_total_equity: float,
        orders_degraded: bool,
        *,
        available_cash: float | None = None,
        current_positions_count: int = 0,
        max_positions: int = 10**9,
        daily_new_position_count: int = 0,
        max_new_positions_per_day: int = 10**9,
        daily_add_count: int = 0,
        max_adds_per_day: int = 10**9,
    ) -> tuple[dict, float]:
        decision["action_enum"] = action_enum
        price = _safe_float(decision.get("close"))
        current_shares = _safe_int(decision.get("current_shares"))
        decision["target_price_reference"] = round(price, 4) if price > 0 else None
        if orders_degraded or latest_total_equity <= 0 or price <= 0:
            decision["target_shares"] = None
            decision["delta_shares"] = None
            decision["rounded_lots"] = None
            decision["estimated_turnover"] = None
            decision["estimated_commission"] = None
            decision["estimated_stamp_duty"] = None
            decision["estimated_total_cash_impact"] = None
            decision["target_order_value"] = None
            if action_enum in {"HOLD", "HOLD_FROZEN", "EMPTY", "BLOCKED", "DATA_ERROR"}:
                decision["target_position_tranches"] = int(decision.get("target_position_tranches", decision["current_position_tranches"]))
                decision["target_weight"] = round(_safe_float(decision.get("target_weight", decision["current_weight"])), 6)
                decision["target_position_change"] = round(decision["target_weight"] - _safe_float(decision["current_weight"]), 6)
            return decision, 0.0

        if current_shares <= 0 and int(decision["current_position_tranches"]) > 0 and action_enum in {"BUY_2", "BUY_3", "REDUCE", "SELL_ALL", "HOLD", "HOLD_FROZEN"}:
            decision["blocked_reason"] = "MISSING_SHARE_COUNT"
            decision["reason_codes"].append("MISSING_SHARE_COUNT")
            decision["action_enum"] = "BLOCKED" if action_enum != "DATA_ERROR" else "DATA_ERROR"
            self._reset_to_current(decision, "缺少当前持仓股数，无法输出可执行订单。")
            return decision, 0.0

        if self.lot_aware_sizing and action_enum in {"BUY_1", "BUY_2", "BUY_3"}:
            return self._lot_aware_buy_plan(
                decision,
                action_enum,
                latest_total_equity,
                price,
                current_shares,
                available_cash if available_cash is not None else latest_total_equity,
                current_positions_count,
                max_positions,
                daily_new_position_count,
                max_new_positions_per_day,
                daily_add_count,
                max_adds_per_day,
            )

        desired_target_weight = round(_safe_float(decision.get("desired_target_weight", decision.get("target_weight"))), 6)
        desired_target_tranches = int(decision.get("desired_target_tranches", decision["current_position_tranches"]))
        target_shares = current_shares
        if action_enum == "SELL_ALL":
            target_shares = 0
        elif action_enum == "REDUCE":
            target_shares = min(current_shares, self._rounded_target_shares(desired_target_weight * latest_total_equity, price))
        elif action_enum in {"BUY_1", "BUY_2", "BUY_3"}:
            target_shares = max(current_shares, self._rounded_target_shares(desired_target_weight * latest_total_equity, price))
        elif action_enum in {"HOLD", "HOLD_FROZEN", "EMPTY", "BLOCKED", "DATA_ERROR"}:
            target_shares = current_shares

        delta_shares = target_shares - current_shares
        estimated_turnover = round(abs(delta_shares) * price, 2)
        estimated_commission = round(estimated_turnover * self.commission_rate, 2)
        estimated_stamp_duty = round(estimated_turnover * self.stamp_duty_rate_sell, 2) if delta_shares < 0 else 0.0
        estimated_total_cash_impact = round(
            -(estimated_turnover + estimated_commission) if delta_shares > 0 else estimated_turnover - estimated_commission - estimated_stamp_duty,
            2,
        )
        rounded_lots = ceil(abs(delta_shares) / self.round_lot) if delta_shares else 0

        if action_enum in {"BUY_1", "BUY_2", "BUY_3", "REDUCE"} and delta_shares == 0:
            decision["blocked_reason"] = "ROUND_LOT_BLOCK"
            decision["reason_codes"].append("ROUND_LOT_BLOCK")
            decision["action_enum"] = "BLOCKED"
            self._reset_to_current(decision, "目标变动低于整手约束，无法下达可执行订单。")
            return decision, 0.0

        if action_enum in {"BUY_1", "BUY_2", "BUY_3", "REDUCE"} and estimated_turnover > 0 and estimated_turnover < self.min_trade_value:
            decision["blocked_reason"] = "MIN_TRADE_VALUE"
            decision["reason_codes"].append("MIN_TRADE_VALUE")
            decision["action_enum"] = "BLOCKED"
            self._reset_to_current(decision, "目标成交额低于最小交易额，订单被阻断。")
            return decision, 0.0

        actual_target_weight = round((target_shares * price) / latest_total_equity, 6)
        decision["target_position_tranches"] = desired_target_tranches if action_enum in {"BUY_1", "BUY_2", "BUY_3", "REDUCE"} else int(
            decision.get("target_position_tranches", decision["current_position_tranches"])
        )
        decision["target_weight"] = actual_target_weight
        decision["target_position_change"] = round(actual_target_weight - _safe_float(decision["current_weight"]), 6)
        decision["target_shares"] = target_shares
        decision["delta_shares"] = delta_shares
        decision["rounded_lots"] = rounded_lots
        decision["estimated_turnover"] = estimated_turnover
        decision["estimated_commission"] = estimated_commission
        decision["estimated_stamp_duty"] = estimated_stamp_duty
        decision["estimated_total_cash_impact"] = estimated_total_cash_impact
        decision["target_order_value"] = estimated_turnover
        return decision, max(0.0, -estimated_total_cash_impact)

    def generate(
        self,
        snapshot: pd.DataFrame,
        positions: pd.DataFrame,
        market_regime: dict,
        safe_mode: bool = False,
        account_state: dict | None = None,
    ) -> list[dict]:
        if snapshot.empty:
            return []
        account_state = account_state or {}
        orders_degraded = bool(account_state.get("orders_degraded", False))
        latest_total_equity = float(account_state.get("latest_total_equity", 0.0))
        current_cash = float(account_state.get("current_cash", 0.0))
        reserved_cash = float(account_state.get("reserved_cash", 0.0))
        current_invested_value = float(account_state.get("current_invested_value", 0.0))
        holdings_count = int(account_state.get("holdings_count", 0))

        decisions = [self._base_decision(record.copy(), market_regime, safe_mode) for record in snapshot.to_dict(orient="records")]
        self._merge_position_fields(decisions, positions)
        for decision in decisions:
            current_tranches = int(decision.get("current_position_tranches", 0))
            desired_tranches = int(decision.get("desired_target_tranches", current_tranches))
            decision["intended_target_tranches"] = desired_tranches
            decision["intended_target_weight"] = round(self._weight_for_tranches(desired_tranches, str(decision.get("bucket"))), 6)
            decision["intended_action_enum"] = _action_for_target(current_tranches, desired_tranches, decision.get("holding_state", "NONE"))
        fixed_weight = 0.0
        released_cash = 0.0
        buy_requests: list[dict] = []
        for decision in decisions:
            current_tranches = int(decision["current_position_tranches"])
            target_tranches = int(decision["desired_target_tranches"])
            if target_tranches > current_tranches:
                buy_requests.append(decision)
                continue

            decision["target_position_tranches"] = target_tranches
            decision["target_weight"] = round(self._weight_for_tranches(target_tranches, str(decision.get("bucket"))), 6)
            decision["target_position_change"] = round(decision["target_weight"] - decision["current_weight"], 6)
            action_enum = (
                "BLOCKED"
                if current_tranches == 0 and decision.get("blocked_reason")
                else _action_for_target(current_tranches, target_tranches, decision.get("holding_state", "NONE"))
            )
            decision, _ = self._execution_plan(decision, action_enum, latest_total_equity, orders_degraded)
            fixed_weight += decision["target_weight"]
            if not orders_degraded and decision.get("estimated_total_cash_impact") is not None:
                released_cash += max(0.0, float(decision["estimated_total_cash_impact"]))

        capacity = max(0.0, float(market_regime["max_total_position"]) - fixed_weight)
        initial_buying_power = None
        available_buying_power = None
        if not orders_degraded and latest_total_equity > 0:
            gross_room_value = max(
                0.0,
                float(market_regime["max_total_position"]) * latest_total_equity - max(0.0, current_invested_value - released_cash),
            )
            cash_room_value = max(0.0, current_cash - reserved_cash + released_cash)
            initial_buying_power = round(min(cash_room_value, gross_room_value), 2)
            available_buying_power = initial_buying_power

        if self.is_v2:
            signal_rank = {"BUY_3": 3, "BUY_2": 2, "BUY_1": 1}
            ordered_requests = sorted(
                buy_requests,
                key=lambda item: (
                    -signal_rank.get(str(item.get("signal_level", item.get("intended_action_enum"))), 0),
                    -float(item.get("priority_score", 0.0)),
                    _stock_valuation_quantile(item, str(item.get("bucket"))),
                    -_safe_float(item.get("dv_ttm")),
                    -_safe_float(item.get("market_cap_billion")),
                    item["symbol"],
                ),
            )
        else:
            ordered_requests = sorted(
                buy_requests,
                key=lambda item: (
                    0 if int(item["current_position_tranches"]) > 0 else 1,
                    -float(item["priority_score"]),
                    item["symbol"],
                ),
            )
        new_buys_today = 0
        adds_today = 0
        max_new = int(self.strategy_cfg["execution"].get("max_new_positions_per_day", 10**9))
        max_adds = int(self.strategy_cfg["execution"].get("max_adds_per_day", 10**9))
        max_positions = int(self.strategy_cfg["execution"].get("max_positions", 10**9))
        for decision in ordered_requests:
            current_tranches = int(decision["current_position_tranches"])
            target_tranches = int(decision["desired_target_tranches"])
            decision["target_position_tranches"] = target_tranches
            decision["target_weight"] = round(self._weight_for_tranches(target_tranches, str(decision.get("bucket"))), 6)
            decision["target_position_change"] = round(decision["target_weight"] - decision["current_weight"], 6)
            decision, required_cash = self._execution_plan(
                decision,
                _action_for_target(current_tranches, target_tranches, decision.get("holding_state", "NONE")),
                latest_total_equity,
                orders_degraded,
                available_cash=available_buying_power,
                current_positions_count=holdings_count + new_buys_today,
                max_positions=max_positions,
                daily_new_position_count=new_buys_today,
                max_new_positions_per_day=max_new,
                daily_add_count=adds_today,
                max_adds_per_day=max_adds,
            )
            requested_weight = max(0.0, decision["target_weight"] - _safe_float(decision["current_weight"]))
            cash_blocked = available_buying_power is not None and required_cash > available_buying_power + 1e-9
            daily_limit_blocked = False
            daily_limit_reason = ""
            if self.is_v2 and decision["action_enum"] in {"BUY_1", "BUY_2", "BUY_3"}:
                if current_tranches == 0 and new_buys_today >= max_new:
                    daily_limit_blocked = True
                    daily_limit_reason = "DAILY_NEW_POSITION_LIMIT"
                if current_tranches == 0 and holdings_count + new_buys_today >= max_positions:
                    daily_limit_blocked = True
                    daily_limit_reason = "MAX_POSITIONS_LIMIT"
                if current_tranches > 0 and adds_today >= max_adds:
                    daily_limit_blocked = True
                    daily_limit_reason = "DAILY_ADD_LIMIT"
            if (
                decision["action_enum"] in {"BUY_1", "BUY_2", "BUY_3"}
                and requested_weight <= capacity + 1e-9
                and not decision.get("blocked_reason")
                and not cash_blocked
                and not daily_limit_blocked
            ):
                capacity = round(max(0.0, capacity - requested_weight), 6)
                if self.is_v2:
                    if current_tranches == 0:
                        new_buys_today += 1
                    else:
                        adds_today += 1
                if available_buying_power is not None:
                    available_buying_power = round(max(0.0, available_buying_power - required_cash), 2)
                continue

            if decision["action_enum"] in {"BUY_1", "BUY_2", "BUY_3"}:
                if requested_weight > capacity + 1e-9:
                    decision["blocked_reason"] = "REGIME_CAP_BLOCK"
                    decision["reason_codes"].append("REGIME_CAP_BLOCK")
                elif cash_blocked:
                    decision["blocked_reason"] = "INSUFFICIENT_CASH"
                    decision["reason_codes"].append("INSUFFICIENT_CASH")
                elif daily_limit_blocked:
                    decision["blocked_reason"] = daily_limit_reason or "DAILY_POSITION_LIMIT"
                    decision["reason_codes"].append(daily_limit_reason or "DAILY_POSITION_LIMIT")
                elif not decision.get("blocked_reason"):
                    decision["blocked_reason"] = "REGIME_CAP_BLOCK"
                    decision["reason_codes"].append("REGIME_CAP_BLOCK")
                decision["action_enum"] = "BLOCKED"
                self._reset_to_current(decision, "买入请求因仓位上限、资金约束或执行约束被阻断。")

        remaining_buying_power = initial_buying_power if initial_buying_power is not None else None
        if available_buying_power is not None:
            remaining_buying_power = available_buying_power
        for decision in decisions:
            decision["action_enum"] = decision.get("action_enum", "EMPTY")
            if decision["action_enum"] not in ACTIONS:
                decision["action_enum"] = "DATA_ERROR"
            decision["regime"] = market_regime["regime"]
            decision["reason_codes"] = sorted(set(decision.get("reason_codes", [])))
            decision["risk_flags"] = sorted(set(decision.get("risk_flags", [])))
            decision["current_position_tranches"] = int(decision["current_position_tranches"])
            decision["target_position_tranches"] = int(decision.get("target_position_tranches", decision["current_position_tranches"]))
            decision["current_shares"] = _safe_int(decision.get("current_shares"))
            decision["target_weight"] = round(_safe_float(decision.get("target_weight")), 6)
            decision["current_weight"] = round(_safe_float(decision.get("current_weight")), 6)
            decision["target_position_change"] = round(_safe_float(decision.get("target_position_change")), 6)
            if remaining_buying_power is None:
                decision["target_order_value"] = None
                decision["target_shares"] = decision.get("target_shares")
                decision["delta_shares"] = decision.get("delta_shares")
                decision["rounded_lots"] = decision.get("rounded_lots")
                decision["estimated_turnover"] = decision.get("estimated_turnover")
                decision["estimated_commission"] = decision.get("estimated_commission")
                decision["estimated_stamp_duty"] = decision.get("estimated_stamp_duty")
                decision["estimated_total_cash_impact"] = decision.get("estimated_total_cash_impact")
                decision["orders_degraded"] = True
                decision["latest_total_equity"] = None
                decision["current_cash"] = None
                decision["available_buying_power"] = None
            else:
                decision["orders_degraded"] = False
                decision["latest_total_equity"] = latest_total_equity
                decision["current_cash"] = current_cash
                decision["available_buying_power"] = remaining_buying_power
        return sorted(decisions, key=lambda item: (item.get("holding_state") == "NONE", item["symbol"]))

    @staticmethod
    def summarize_actions(decisions: list[dict], safe_mode: bool = False) -> str:
        if safe_mode:
            return "safe_mode"
        counter = Counter(item["action_enum"] for item in decisions)
        if not counter:
            return "无决策"
        return " / ".join(f"{action}:{count}" for action, count in sorted(counter.items()))
