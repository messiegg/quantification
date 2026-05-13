from __future__ import annotations

from dataclasses import dataclass


class StrategyIntent:
    BUY_1 = "BUY_1"
    BUY_2 = "BUY_2"
    BUY_3 = "BUY_3"
    HOLD = "HOLD"
    HOLD_FROZEN = "HOLD_FROZEN"
    HOLD_WITH_PENDING_ADD = "HOLD_WITH_PENDING_ADD"
    REDUCE = "REDUCE"
    SELL_ALL = "SELL_ALL"
    EMPTY = "EMPTY"
    BLOCKED = "BLOCKED"
    DATA_ERROR = "DATA_ERROR"


class ExecutionStatus:
    EXECUTABLE = "EXECUTABLE"
    WATCH = "WATCH"
    PENDING = "PENDING"
    BLOCKED = "BLOCKED"
    NO_ACTION = "NO_ACTION"


class ExecutionReason:
    EXECUTABLE = "EXECUTABLE"
    NO_ACTION = "NO_ACTION"
    STRATEGY_BLOCKED = "STRATEGY_BLOCKED"
    DATA_ERROR = "DATA_ERROR"
    WATCH_PORTFOLIO_FULL = "WATCH_PORTFOLIO_FULL"
    WATCH_COMPACT_RANK_OUT = "WATCH_COMPACT_RANK_OUT"
    WATCH_DAILY_NEW_LIMIT = "WATCH_DAILY_NEW_LIMIT"
    WATCH_DAILY_ADD_LIMIT = "WATCH_DAILY_ADD_LIMIT"
    WATCH_INDUSTRY_CONCENTRATION = "WATCH_INDUSTRY_CONCENTRATION"
    WATCH_REPLACEMENT_NOT_WORTH_IT = "WATCH_REPLACEMENT_NOT_WORTH_IT"
    PENDING_CASH_INSUFFICIENT_FOR_ONE_LOT = "PENDING_CASH_INSUFFICIENT_FOR_ONE_LOT"
    PENDING_CASH_RESERVED = "PENDING_CASH_RESERVED"
    PENDING_LOT_ACCUMULATION_REQUIRED = "PENDING_LOT_ACCUMULATION_REQUIRED"
    PENDING_SINGLE_NAME_CAPACITY = "PENDING_SINGLE_NAME_CAPACITY"
    BLOCK_PRICE_TOO_HIGH_FOR_ACCOUNT_LOT = "BLOCK_PRICE_TOO_HIGH_FOR_ACCOUNT_LOT"
    BLOCK_MISSING_FILL_PRICE = "BLOCK_MISSING_FILL_PRICE"
    BLOCK_MIN_TRADE_VALUE = "BLOCK_MIN_TRADE_VALUE"
    BLOCK_LOT_SIZE_ZERO = "BLOCK_LOT_SIZE_ZERO"
    BLOCK_INVALID_INPUT = "BLOCK_INVALID_INPUT"


BUY_INTENTS = {StrategyIntent.BUY_1, StrategyIntent.BUY_2, StrategyIntent.BUY_3}
ACTIONS = {
    StrategyIntent.BUY_1,
    StrategyIntent.BUY_2,
    StrategyIntent.BUY_3,
    StrategyIntent.HOLD,
    StrategyIntent.HOLD_FROZEN,
    StrategyIntent.HOLD_WITH_PENDING_ADD,
    StrategyIntent.REDUCE,
    StrategyIntent.SELL_ALL,
    StrategyIntent.EMPTY,
    StrategyIntent.BLOCKED,
    StrategyIntent.DATA_ERROR,
}


@dataclass(frozen=True)
class AccountExecutionPolicy:
    account_equity: float
    current_cash: float
    reserved_cash: float
    round_lot: int = 100
    min_trade_value: float = 0.0
    max_single_stock_weight: float = 0.12
    max_positions: int = 8
    max_new_positions_per_day: int = 1
    max_adds_per_day: int = 2
    compact_candidate_limit: int = 12
    cash_reserve_ratio: float = 0.10
    industry_max_positions: int = 2
    replacement_enabled: bool = True
    replacement_score_threshold: float = 5.0
    replacement_advisory_only: bool = True

    @classmethod
    def from_configs(
        cls,
        account_state: dict | None,
        strategy_cfg: dict | None,
        account_cfg: dict | None,
    ) -> "AccountExecutionPolicy":
        account_state = account_state or {}
        strategy_cfg = strategy_cfg or {}
        account_cfg = account_cfg or {}
        account_section = account_cfg.get("account", {}) if isinstance(account_cfg, dict) else {}
        execution_cfg = account_cfg.get("execution", {}) if isinstance(account_cfg, dict) else {}
        sizing_cfg = account_cfg.get("position_sizing", {}) if isinstance(account_cfg, dict) else {}
        portfolio_cfg = account_cfg.get("portfolio_execution", {}) if isinstance(account_cfg, dict) else {}
        replacement_cfg = portfolio_cfg.get("replacement", {}) if isinstance(portfolio_cfg, dict) else {}
        strategy_execution = strategy_cfg.get("execution", {}) if isinstance(strategy_cfg, dict) else {}

        account_profile = str(account_cfg.get("account_profile", account_cfg.get("profile_name", "")))
        raw_max_positions = int(float(strategy_execution.get("max_positions", 8)))
        if account_profile in {"retail_50k_lot_aware", "actual_50k_lot_aware"}:
            raw_max_positions = min(raw_max_positions, 8)

        return cls(
            account_equity=_float_first(
                account_state.get("latest_total_equity"),
                account_state.get("account_equity"),
                account_section.get("latest_total_equity"),
                account_section.get("initial_capital"),
                default=0.0,
            ),
            current_cash=_float_first(
                account_state.get("current_cash"),
                account_section.get("current_cash"),
                account_section.get("initial_capital"),
                default=0.0,
            ),
            reserved_cash=_float_first(account_state.get("reserved_cash"), account_section.get("reserved_cash"), default=0.0),
            round_lot=max(0, int(float(execution_cfg.get("round_lot", 100) or 0))),
            min_trade_value=max(0.0, _float_first(sizing_cfg.get("min_trade_value"), default=0.0)),
            max_single_stock_weight=max(0.0, _float_first(sizing_cfg.get("max_single_stock_weight"), default=0.12)),
            max_positions=max(0, raw_max_positions),
            max_new_positions_per_day=max(0, int(float(strategy_execution.get("max_new_positions_per_day", 1)))),
            max_adds_per_day=max(0, int(float(strategy_execution.get("max_adds_per_day", 2)))),
            compact_candidate_limit=max(0, int(float(portfolio_cfg.get("compact_candidate_limit", 12) or 0))),
            cash_reserve_ratio=max(0.0, _float_first(portfolio_cfg.get("cash_reserve_ratio"), default=0.10)),
            industry_max_positions=max(0, int(float(portfolio_cfg.get("industry_max_positions", 2) or 0))),
            replacement_enabled=bool(replacement_cfg.get("enabled", True)) if isinstance(replacement_cfg, dict) else True,
            replacement_score_threshold=_float_first(
                replacement_cfg.get("score_threshold") if isinstance(replacement_cfg, dict) else None,
                default=5.0,
            ),
            replacement_advisory_only=bool(replacement_cfg.get("advisory_only", True)) if isinstance(replacement_cfg, dict) else True,
        )


def _float_first(*values: object, default: float = 0.0) -> float:
    for value in values:
        try:
            if value is None:
                continue
            return float(value)
        except (TypeError, ValueError):
            continue
    return default
