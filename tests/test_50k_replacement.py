from __future__ import annotations

from src.execution.replacement import evaluate_50k_core_replacement


def _policy(**overrides) -> dict:
    policy = {
        "enabled": True,
        "advisory_only_for_live": True,
        "backtest_switch_plan_enabled": True,
        "mode": "backtest",
        "portfolio_full": True,
        "score_gap_threshold": 10,
        "max_replacements_per_month": 1,
        "month_replacement_count": 0,
        "min_holding_days_before_replacement": 40,
        "industry_max_positions": 1,
        "industry_position_counts": {"银行": 1, "公用事业": 1},
        "account_equity": 50_000,
        "max_single_stock_weight": 0.16,
        "round_lot": 100,
        "commission_rate": 0.0003,
        "stamp_duty_rate_sell": 0.0005,
    }
    policy.update(overrides)
    return policy


def _holding(symbol: str, **overrides) -> dict:
    row = {
        "symbol": symbol,
        "industry": "银行",
        "expected_edge_score": 45,
        "relative_strength": -5,
        "holding_days": 60,
        "unrealized_pnl_pct": -0.03,
        "close": 35,
        "ma120": 40,
        "stock_q_blended": 70,
        "fundamental_break": False,
        "thesis_still_valid": False,
        "shares": 100,
        "avg_cost": 40,
    }
    row.update(overrides)
    return row


def _candidate(**overrides) -> dict:
    row = {
        "symbol": "600999.sh",
        "industry": "银行",
        "expected_edge_score": 60,
        "structural_lot_block": False,
        "close": 60,
        "lot_notional": 6_000,
    }
    row.update(overrides)
    return row


def test_replacement_does_not_trigger_when_portfolio_not_full() -> None:
    result = evaluate_50k_core_replacement([_holding("600001.sh")], _candidate(), _policy(portfolio_full=False))

    assert result["triggered"] is False
    assert result["reason"] == "PORTFOLIO_NOT_FULL"


def test_replacement_triggers_simulated_switch_when_gap_and_weak_holding_pass() -> None:
    result = evaluate_50k_core_replacement([_holding("600001.sh")], _candidate(), _policy())

    assert result["triggered"] is True
    assert result["research_only_simulated_replacement"] is True
    assert result["simulated_sell_symbol"] == "600001.sh"
    assert result["simulated_buy_symbol"] == "600999.sh"
    assert result["score_gap"] == 15
    assert result["estimated_turnover"] > 0


def test_replacement_does_not_trigger_when_score_gap_is_insufficient() -> None:
    result = evaluate_50k_core_replacement([_holding("600001.sh", expected_edge_score=55)], _candidate(expected_edge_score=60), _policy(score_gap_threshold=10))

    assert result["triggered"] is False
    assert result["reason"] == "SCORE_GAP_INSUFFICIENT"


def test_replacement_does_not_replace_valid_positive_rs_thesis() -> None:
    result = evaluate_50k_core_replacement(
        [_holding("600001.sh", thesis_still_valid=True, relative_strength=8, expected_edge_score=45)],
        _candidate(expected_edge_score=70),
        _policy(),
    )

    assert result["triggered"] is False
    assert result["reason"] == "HOLDING_THESIS_VALID_RS_POSITIVE"


def test_replacement_respects_monthly_limit() -> None:
    result = evaluate_50k_core_replacement([_holding("600001.sh")], _candidate(), _policy(month_replacement_count=1, max_replacements_per_month=1))

    assert result["triggered"] is False
    assert result["reason"] == "MONTHLY_REPLACEMENT_LIMIT"


def test_live_manual_mode_is_advisory_only() -> None:
    result = evaluate_50k_core_replacement([_holding("600001.sh")], _candidate(), _policy(mode="live_manual"))

    assert result["triggered"] is False
    assert result["advisory_only"] is True
    assert result["research_only_simulated_replacement"] is False
    assert result["simulated_sell_symbol"] == "600001.sh"
    assert result["simulated_buy_symbol"] == "600999.sh"
