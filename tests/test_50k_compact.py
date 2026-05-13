from __future__ import annotations

import json

import pandas as pd

from scripts import run_50k_compact_experiments as compact
from scripts import run_release_guard as guard
from src.strategy.backtest_engine import Position
from src.utils.config import load_yaml, resolve_path


def _params(**overrides) -> compact.CompactParams:
    values = {
        "max_positions": 4,
        "max_tranches": 1,
        "target_universe_size": 8,
        "cash_reserve_ratio": 0.10,
        "max_new_positions_per_day": 1,
        "max_adds_per_day": 0,
        "capital": 50_000.0,
        "round_lot": 100,
    }
    values.update(overrides)
    return compact.CompactParams(**values)


def _buy_decision(**overrides) -> dict:
    values = {
        "date": "2024-01-02",
        "symbol": "000001.sz",
        "ts_code": "000001.sz",
        "name": "fixture",
        "industry": "bank",
        "bucket": "defensive_dividend",
        "action_enum": "BUY_1",
        "signal_level": "BUY_1",
        "desired_target_tranches": 1,
        "target_position_tranches": 1,
        "current_position_tranches": 0,
        "current_shares": 0,
        "close": 80.0,
        "universe_final_score": 80.0,
        "stock_valuation_quantile": 10.0,
        "dv_ttm": 0.05,
    }
    values.update(overrides)
    return values


def test_portfolio_full_goes_to_watch_not_new_buy() -> None:
    params = _params(max_positions=4)
    decision = _buy_decision()

    gate = compact.compact_account_gate(
        decision,
        params,
        nav=50_000,
        cash=50_000,
        positions_count=4,
    )
    watch = compact._watch_record("2024-01-02", decision, gate)

    assert not gate.actionable
    assert gate.reason_code == compact.WATCH_REASON_PORTFOLIO_FULL
    assert watch["action_enum"] == "HOLD"
    assert watch["reason_codes"] == [compact.WATCH_REASON_PORTFOLIO_FULL]


def test_cash_reserve_blocks_buy_before_new_buy_output() -> None:
    params = _params(max_positions=4, cash_reserve_ratio=0.10)
    gate = compact.compact_account_gate(
        _buy_decision(close=80.0),
        params,
        nav=50_000,
        cash=12_000,
        positions_count=0,
    )

    assert not gate.actionable
    assert gate.reason_code == compact.WATCH_REASON_CASH_RESERVED


def test_one_lot_above_single_name_budget_goes_to_watch() -> None:
    params = _params(max_positions=8, cash_reserve_ratio=0.10)
    gate = compact.compact_account_gate(
        _buy_decision(close=80.0),
        params,
        nav=50_000,
        cash=50_000,
        positions_count=0,
    )

    assert not gate.actionable
    assert gate.reason_code == compact.WATCH_REASON_LOT_TOO_EXPENSIVE


def test_compact_experiment_grid_stays_within_50k_bounds() -> None:
    cfg = load_yaml(compact.CONFIG_PATH)
    params = compact._params_from_config(cfg)

    assert cfg["account"]["capital"] == 50_000
    assert cfg["account"]["round_lot"] == 100
    assert max(item.max_positions for item in params) <= 8
    assert 20 not in {item.max_positions for item in params}


def test_account_actionable_count_excludes_portfolio_full_watch_only() -> None:
    params = _params(max_positions=1)
    positions = {
        "000099.sz": Position(
            symbol="000099.sz",
            industry="bank",
            bucket="defensive_dividend",
            shares=100,
            current_position_tranches=1,
            current_shares=100,
        )
    }
    decisions = [
        _buy_decision(symbol="000001.sz", industry="bank"),
        _buy_decision(symbol="000002.sz", industry="steel"),
    ]

    selected, watch_records, strategy_eligible_count = compact._apply_compact_buy_selection(
        signal_date="2024-01-02",
        buy_decisions=decisions,
        params=params,
        nav=50_000,
        cash=10_000,
        positions=positions,
    )

    assert strategy_eligible_count == 2
    assert selected == []
    assert len(watch_records) == 2
    assert {row["reason_code"] for row in watch_records} == {compact.WATCH_REASON_PORTFOLIO_FULL}


def test_executable_account_actionable_ratio_denominator() -> None:
    assert compact._ratio_or_none(4, 5) == 0.8
    assert compact._ratio_or_none(0, 5) == 0.0
    assert compact._ratio_or_none(1, 0) is None


def test_compact_profile_does_not_change_default_release_account_profile() -> None:
    cfg = load_yaml(compact.CONFIG_PATH)
    manifest = json.loads(resolve_path("reports/backtest/release/combined_v2_rc_manifest.json").read_text(encoding="utf-8"))

    assert cfg["research_only"] is True
    assert cfg["release_profile_replacement"] is False
    assert manifest["profile"] == "combined_v2"
    assert manifest["account_profile"] in {"retail_50k_lot_aware", "actual_50k_lot_aware"}
    assert manifest["account_profile"] not in {"combined_v2_50k_compact", "reference_200k", "capital_200k_maxpos20"}


def test_compact_research_profile_does_not_turn_guard_warn_into_pass(monkeypatch) -> None:
    payload = {
        "status": "WARN",
        "default_release_profile": "actual_50k_lot_aware",
        "profiles": [
            {
                "profile": "actual_50k_lot_aware",
                "executable_raw_buy_ratio": 0.036,
                "buy_trades": 23,
                "max_positions": 8,
                "portfolio_max_positions": 8,
            },
            {
                "profile": "combined_v2_50k_compact",
                "research_only": True,
                "executable_raw_buy_ratio": 0.9,
                "buy_trades": 12,
                "max_positions": 4,
                "portfolio_max_positions": 4,
            },
        ],
    }
    monkeypatch.setattr(guard, "_read_json", lambda path: payload)
    rows: list[dict] = []

    guard._check_account_profile_comparison(rows)

    assert "default=actual_50k_lot_aware" in rows[-1]["actual"]
    assert rows[-1]["status"] == "WARN"
    assert guard._release_status_from_rows(pd.DataFrame([{"status": "WARN"}])) == "WARN"


def test_llm_and_broker_are_not_decision_authorities() -> None:
    cfg = load_yaml(compact.CONFIG_PATH)

    assert cfg["safety"]["manual_execution_only"] is True
    assert cfg["safety"]["auto_trading_approved"] is False
    assert cfg["safety"]["broker_integration_enabled"] is False
    assert cfg["safety"]["llm_decision_allowed"] is False
    assert cfg["safety"]["writes_real_trades"] is False


def test_compact_outputs_are_research_only_not_release_artifacts() -> None:
    from scripts.rc_hash_scope import RESEARCH_ONLY_EXCLUDED_FROM_RC_CODE_HASH

    excluded = set(RESEARCH_ONLY_EXCLUDED_FROM_RC_CODE_HASH)

    assert compact.CONFIG_PATH in excluded
    assert "scripts/run_50k_compact_experiments.py" in excluded
    assert "reports/backtest/50k_compact/**" in excluded
