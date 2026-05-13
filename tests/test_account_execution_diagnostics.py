from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

from scripts.build_account_constraints_report import build_account_constraints_report


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(rows).to_csv(path, index=False)


def _write_configs(tmp_path: Path) -> tuple[Path, Path]:
    account = {
        "account_profile": "fixture_50k",
        "account": {"initial_capital": 50000, "current_cash": 50000, "latest_total_equity": 50000},
        "execution": {"round_lot": 100, "commission_rate": 0.0003, "stamp_duty_rate_sell": 0.0005, "slippage_bps": 5},
        "position_sizing": {"min_trade_value": 1500, "max_single_stock_weight": 0.12},
    }
    strategy = {"profile": "combined_v2", "execution": {"max_positions": 8, "equal_weight_target_universe_size": 8}}
    account_path = tmp_path / "account.yml"
    strategy_path = tmp_path / "strategy.yml"
    account_path.write_text(yaml.safe_dump(account), encoding="utf-8")
    strategy_path.write_text(yaml.safe_dump(strategy), encoding="utf-8")
    return account_path, strategy_path


def test_account_execution_diagnostics_split_ratios_and_repeats(tmp_path: Path) -> None:
    account_path, strategy_path = _write_configs(tmp_path)
    funnel = tmp_path / "signal_funnel.csv"
    blocked = tmp_path / "blocked.csv"
    trades = tmp_path / "trades.csv"
    _write_csv(
        funnel,
        [
            {
                "raw_buy_signal_count": 8,
                "unique_raw_buy_intent_count": 4,
                "repeated_blocked_buy_signal_count": 4,
                "raw_sell_signal_count": 0,
                "account_feasible_buy_signal_count": 4,
                "user_visible_buy_recommendation_count": 3,
                "user_visible_blocked_buy_count": 5,
                "pending_buy_intent_count": 1,
                "executable_buy_count": 3,
                "executable_sell_count": 0,
                "current_cash": 50000,
                "current_total_exposure": 0.5,
            }
        ],
    )
    _write_csv(
        blocked,
        [
            {"date": "2024-01-02", "ts_code": "000001.sz", "bucket": "defensive_dividend", "intended_action": "BUY_1", "intended_signal_level": "BUY_1", "current_weight": 0.0, "reason_code": "MAX_POSITIONS_LIMIT"},
            {"date": "2024-01-03", "ts_code": "000002.sz", "bucket": "defensive_dividend", "intended_action": "BUY_1", "intended_signal_level": "BUY_1", "current_weight": 0.0, "reason_code": "MAX_POSITIONS_LIMIT"},
            {"date": "2024-01-04", "ts_code": "000003.sz", "bucket": "cyclical_rotation", "intended_action": "BUY_1", "intended_signal_level": "BUY_1", "current_weight": 0.0, "reason_code": "CASH_INSUFFICIENT_FOR_ONE_LOT"},
            {"date": "2024-01-05", "ts_code": "000004.sz", "bucket": "cyclical_rotation", "intended_action": "HOLD_WITH_PENDING_ADD", "intended_signal_level": "BUY_2", "current_weight": 0.04, "reason_code": "LOT_SIZE_ACCUMULATION_REQUIRED"},
            {"date": "2024-01-06", "ts_code": "000005.sz", "bucket": "defensive_dividend", "intended_action": "BUY_2", "intended_signal_level": "BUY_2", "current_weight": 0.03, "reason_code": "MIN_TRADE_VALUE"},
        ],
    )
    _write_csv(
        trades,
        [
            {"date": "2024-01-03", "ts_code": "000006.sz", "side": "BUY", "action": "BUY_1", "position_before": 0},
            {"date": "2024-01-04", "ts_code": "000007.sz", "side": "BUY", "action": "BUY_2", "position_before": 100},
            {"date": "2024-01-05", "ts_code": "000008.sz", "side": "BUY", "action": "BUY_3", "position_before": 200},
        ],
    )

    report = build_account_constraints_report(
        signal_funnel_path=str(funnel),
        blocked_signals_path=str(blocked),
        trades_path=str(trades),
        account_config=str(account_path),
        strategy_config=str(strategy_path),
        write_report=False,
    )

    assert report["executable_unique_raw_intent_ratio"] == 3 / 4
    assert report["repeat_raw_buy_intent_count"] == 4
    assert report["repeat_raw_buy_intent_ratio"] == 4 / 8
    assert report["full_portfolio_raw_buy_intent_count"] == 2
    assert report["full_portfolio_raw_buy_intent_ratio"] == 2 / 8
    assert report["new_position_raw_intent_count"] == 4
    assert report["add_position_raw_intent_count"] == 4
    assert report["executable_new_position_buy_count"] == 1
    assert report["executable_add_buy_count"] == 2
    assert report["cash_block_ratio"] == 0
    assert report["cash_liquidity_block_ratio"] == 1 / 8


def test_block_reason_breakdown_denominators(tmp_path: Path) -> None:
    account_path, strategy_path = _write_configs(tmp_path)
    funnel = tmp_path / "signal_funnel.csv"
    blocked = tmp_path / "blocked.csv"
    trades = tmp_path / "trades.csv"
    _write_csv(funnel, [{"raw_buy_signal_count": 8, "unique_raw_buy_intent_count": 4, "account_feasible_buy_signal_count": 4, "executable_buy_count": 3}])
    _write_csv(
        blocked,
        [
            {"date": "2024-01-02", "ts_code": "000001.sz", "bucket": "defensive_dividend", "intended_action": "BUY_1", "intended_signal_level": "BUY_1", "current_weight": 0, "reason_code": "MAX_POSITIONS_LIMIT"},
            {"date": "2024-01-03", "ts_code": "000002.sz", "bucket": "defensive_dividend", "intended_action": "BUY_1", "intended_signal_level": "BUY_1", "current_weight": 0, "reason_code": "MAX_POSITIONS_LIMIT"},
            {"date": "2024-01-04", "ts_code": "000003.sz", "bucket": "cyclical_rotation", "intended_action": "BUY_1", "intended_signal_level": "BUY_1", "current_weight": 0, "reason_code": "CASH_INSUFFICIENT_FOR_ONE_LOT"},
            {"date": "2024-01-05", "ts_code": "000004.sz", "bucket": "cyclical_rotation", "intended_action": "BUY_2", "intended_signal_level": "BUY_2", "current_weight": 0.03, "reason_code": "LOT_SIZE_ACCUMULATION_REQUIRED"},
        ],
    )
    _write_csv(trades, [])

    report = build_account_constraints_report(
        signal_funnel_path=str(funnel),
        blocked_signals_path=str(blocked),
        trades_path=str(trades),
        account_config=str(account_path),
        strategy_config=str(strategy_path),
        write_report=False,
    )

    max_pos = next(row for row in report["block_reason_breakdown"] if row["reason_code"] == "MAX_POSITIONS_LIMIT")
    assert max_pos["count"] == 2
    assert max_pos["count_pct_of_raw"] == 2 / 8
    assert max_pos["count_pct_of_blocked"] == 2 / 4
    assert max_pos["affected_unique_symbols"] == 2
    assert max_pos["affected_trade_dates"] == 2
    assert max_pos["dominant_bucket"] == "defensive_dividend"


def test_account_execution_diagnostics_zero_denominators(tmp_path: Path) -> None:
    account_path, strategy_path = _write_configs(tmp_path)
    funnel = tmp_path / "signal_funnel.csv"
    blocked = tmp_path / "blocked.csv"
    trades = tmp_path / "trades.csv"
    _write_csv(funnel, [{"raw_buy_signal_count": 0, "unique_raw_buy_intent_count": 0, "account_feasible_buy_signal_count": 0, "executable_buy_count": 0}])
    _write_csv(blocked, [])
    _write_csv(trades, [])

    report = build_account_constraints_report(
        signal_funnel_path=str(funnel),
        blocked_signals_path=str(blocked),
        trades_path=str(trades),
        account_config=str(account_path),
        strategy_config=str(strategy_path),
        write_report=False,
    )

    assert report["executable_raw_buy_ratio"] is None
    assert report["executable_unique_raw_intent_ratio"] is None
    assert report["executable_account_feasible_buy_ratio"] is None
    assert report["repeat_raw_buy_intent_ratio"] is None
    assert report["full_portfolio_raw_buy_intent_ratio"] is None
    assert report["block_reason_breakdown"] == []
