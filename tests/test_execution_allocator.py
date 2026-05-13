from __future__ import annotations

from src.execution.allocator import apply_portfolio_execution_allocator
from src.execution.models import ExecutionReason, ExecutionStatus


def _account_cfg(**overrides) -> dict:
    cfg = {
        "account_profile": "retail_50k_lot_aware",
        "account": {"initial_capital": 50_000, "current_cash": 50_000, "reserved_cash": 0, "latest_total_equity": 50_000},
        "execution": {"round_lot": 100, "commission_rate": 0.0003, "stamp_duty_rate_sell": 0.0005, "slippage_bps": 5},
        "position_sizing": {"min_trade_value": 1_500, "max_single_stock_weight": 0.12},
        "portfolio_execution": {
            "enabled": True,
            "compact_candidate_limit": 12,
            "cash_reserve_ratio": 0.10,
            "industry_max_positions": 2,
            "replacement": {"enabled": True, "score_threshold": 5.0, "advisory_only": True},
        },
    }
    cfg.update(overrides)
    return cfg


def _strategy_cfg(**execution_overrides) -> dict:
    execution = {"max_positions": 8, "max_new_positions_per_day": 1, "max_adds_per_day": 2, "lot_aware_sizing": True}
    execution.update(execution_overrides)
    return {"profile": "combined_v2", "execution": execution}


def _account_state(**overrides) -> dict:
    state = {"current_cash": 50_000, "reserved_cash": 0, "latest_total_equity": 50_000}
    state.update(overrides)
    return state


def _buy(symbol: str, **overrides) -> dict:
    row = {
        "symbol": symbol,
        "name": symbol,
        "industry": "bank",
        "bucket": "defensive_dividend",
        "action_enum": "BUY_1",
        "intended_action_enum": "BUY_1",
        "signal_level": "BUY_1",
        "current_position_tranches": 0,
        "current_shares": 0,
        "current_weight": 0.0,
        "desired_target_tranches": 1,
        "desired_target_weight": 0.12,
        "target_position_tranches": 1,
        "target_weight": 0.12,
        "close": 20.0,
        "priority_score": 80.0,
        "stock_valuation_quantile": 10.0,
        "dv_ttm": 0.05,
        "reason_codes": [],
        "risk_flags": [],
    }
    row.update(overrides)
    return row


def _held(symbol: str, **overrides) -> dict:
    row = {
        "symbol": symbol,
        "name": symbol,
        "industry": "bank",
        "bucket": "defensive_dividend",
        "action_enum": "HOLD",
        "intended_action_enum": "HOLD",
        "current_position_tranches": 1,
        "current_shares": 100,
        "current_weight": 0.04,
        "target_position_tranches": 1,
        "target_weight": 0.04,
        "close": 20.0,
        "priority_score": 10.0,
        "holding_state": "ACTIVE",
        "reason_codes": [],
        "risk_flags": [],
    }
    row.update(overrides)
    return row


def test_portfolio_full_new_buy_becomes_watch_not_blocked() -> None:
    decisions = [_held(f"60000{i}.sh", industry=f"industry{i}") for i in range(8)]
    decisions.append(_buy("600099.sh", industry="new_industry"))

    allocated = apply_portfolio_execution_allocator(decisions, _account_state(), _strategy_cfg(), _account_cfg())
    target = next(item for item in allocated if item["symbol"] == "600099.sh")

    assert target["strategy_intent"] == "BUY_1"
    assert target["action_enum"] == "HOLD"
    assert target["execution_status"] == ExecutionStatus.WATCH
    assert target["execution_reason"] == ExecutionReason.WATCH_PORTFOLIO_FULL
    assert target["user_visible_action"] is False
    assert target["blocked_reason"] in (None, "")


def test_new_buy_outside_compact_candidate_limit_becomes_watch_rank_out() -> None:
    account_cfg = _account_cfg()
    account_cfg["portfolio_execution"]["compact_candidate_limit"] = 1
    strategy_cfg = _strategy_cfg(max_new_positions_per_day=5)
    decisions = [
        _buy("600001.sh", priority_score=90.0),
        _buy("600002.sh", priority_score=80.0),
    ]

    allocated = apply_portfolio_execution_allocator(decisions, _account_state(), strategy_cfg, account_cfg)
    by_symbol = {item["symbol"]: item for item in allocated}

    assert by_symbol["600001.sh"]["execution_status"] == ExecutionStatus.EXECUTABLE
    assert by_symbol["600002.sh"]["execution_status"] == ExecutionStatus.WATCH
    assert by_symbol["600002.sh"]["execution_reason"] == ExecutionReason.WATCH_COMPACT_RANK_OUT
    assert by_symbol["600002.sh"]["strategy_intent"] == "BUY_1"


def test_daily_new_position_limit_allows_only_one_new_buy() -> None:
    decisions = [
        _buy("600001.sh", priority_score=90.0, industry="bank"),
        _buy("600002.sh", priority_score=80.0, industry="utility"),
    ]

    allocated = apply_portfolio_execution_allocator(decisions, _account_state(), _strategy_cfg(max_new_positions_per_day=1), _account_cfg())
    executable = [item for item in allocated if item["execution_action_type"] == "NEW_BUY" and item["execution_status"] == ExecutionStatus.EXECUTABLE]
    watched = [item for item in allocated if item["execution_reason"] == ExecutionReason.WATCH_DAILY_NEW_LIMIT]

    assert len(executable) == 1
    assert len(watched) == 1
    assert watched[0]["action_enum"] == "HOLD"


def test_daily_add_limit_blocks_add_candidates_as_watch() -> None:
    decisions = [
        _buy(
            "600001.sh",
            action_enum="BUY_2",
            intended_action_enum="BUY_2",
            signal_level="BUY_2",
            current_position_tranches=1,
            current_shares=100,
            current_weight=0.04,
            desired_target_tranches=2,
            desired_target_weight=0.12,
            target_position_tranches=2,
            target_weight=0.12,
        )
    ]

    allocated = apply_portfolio_execution_allocator(decisions, _account_state(), _strategy_cfg(max_adds_per_day=0), _account_cfg())

    assert allocated[0]["execution_action_type"] == "ADD"
    assert allocated[0]["execution_status"] == ExecutionStatus.WATCH
    assert allocated[0]["execution_reason"] == ExecutionReason.WATCH_DAILY_ADD_LIMIT
    assert allocated[0]["action_enum"] == "HOLD"


def test_industry_max_positions_updates_after_executable_new_buy() -> None:
    account_cfg = _account_cfg()
    account_cfg["portfolio_execution"]["industry_max_positions"] = 1
    decisions = [
        _buy("600001.sh", priority_score=90.0, industry="bank"),
        _buy("600002.sh", priority_score=80.0, industry="bank"),
    ]

    allocated = apply_portfolio_execution_allocator(
        decisions,
        _account_state(),
        _strategy_cfg(max_new_positions_per_day=2),
        account_cfg,
    )
    by_symbol = {item["symbol"]: item for item in allocated}

    assert by_symbol["600001.sh"]["execution_status"] == ExecutionStatus.EXECUTABLE
    assert by_symbol["600002.sh"]["execution_status"] == ExecutionStatus.WATCH
    assert by_symbol["600002.sh"]["execution_reason"] == ExecutionReason.WATCH_INDUSTRY_CONCENTRATION
    assert by_symbol["600002.sh"]["action_enum"] == "HOLD"


def test_position_count_updates_after_executable_new_buy() -> None:
    decisions = [
        _buy("600001.sh", priority_score=90.0, industry="bank"),
        _buy("600002.sh", priority_score=80.0, industry="utility"),
    ]

    allocated = apply_portfolio_execution_allocator(
        decisions,
        _account_state(),
        _strategy_cfg(max_positions=1, max_new_positions_per_day=2),
        _account_cfg(),
    )
    executable = [item for item in allocated if item["execution_status"] == ExecutionStatus.EXECUTABLE]
    watched = [item for item in allocated if item["execution_reason"] == ExecutionReason.WATCH_PORTFOLIO_FULL]

    assert len(executable) == 1
    assert len(watched) == 1
    assert watched[0]["action_enum"] == "HOLD"


def test_price_too_high_for_account_lot_is_structural_block() -> None:
    decisions = [_buy("600309.sh", close=82.0)]

    allocated = apply_portfolio_execution_allocator(decisions, _account_state(), _strategy_cfg(), _account_cfg())

    assert allocated[0]["execution_status"] == ExecutionStatus.BLOCKED
    assert allocated[0]["execution_reason"] == ExecutionReason.BLOCK_PRICE_TOO_HIGH_FOR_ACCOUNT_LOT
    assert allocated[0]["action_enum"] == "BLOCKED"
    assert allocated[0]["blocked_reason"] == "PRICE_TOO_HIGH_FOR_ACCOUNT_LOT"


def test_cash_shortfall_is_pending_not_blocked() -> None:
    decisions = [_buy("600000.sh", close=20.0)]

    allocated = apply_portfolio_execution_allocator(decisions, _account_state(current_cash=6_000), _strategy_cfg(), _account_cfg())

    assert allocated[0]["execution_status"] == ExecutionStatus.PENDING
    assert allocated[0]["execution_reason"] == ExecutionReason.PENDING_CASH_INSUFFICIENT_FOR_ONE_LOT
    assert allocated[0]["action_enum"] == "HOLD"
    assert allocated[0]["blocked_reason"] in (None, "")


def test_replacement_advisory_fills_candidate_without_auto_sell() -> None:
    decisions = [
        _held("600010.sh", industry="bank", priority_score=10.0),
        _held("600011.sh", industry="utility", priority_score=20.0),
        _buy("600099.sh", industry="coal", priority_score=20.0),
    ]

    allocated = apply_portfolio_execution_allocator(
        decisions,
        _account_state(),
        _strategy_cfg(max_positions=2),
        _account_cfg(),
    )
    candidate = next(item for item in allocated if item["symbol"] == "600099.sh")

    assert candidate["execution_status"] == ExecutionStatus.WATCH
    assert candidate["execution_reason"] == ExecutionReason.WATCH_PORTFOLIO_FULL
    assert candidate["replacement_candidate_symbol"] == "600010.sh"
    assert candidate["replacement_candidate_score"] == 20.0
    assert candidate["replacement_required"] is True
    assert all(item["action_enum"] != "SELL_ALL" for item in allocated)
