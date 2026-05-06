from __future__ import annotations

import copy

from scripts.report_metadata import stable_hash
from scripts.run_account_profile_backtests import _adoption_decision, _profile_configs, _profile_status
from src.utils.config import load_yaml


def test_retail_50k_lot_aware_default_account_config_values() -> None:
    account = load_yaml("config/account.yml")
    strategy = load_yaml("config/strategy_v2.yml")
    universe = load_yaml("config/universe_rules_v2.yml")

    assert account["account_profile"] == "retail_50k_lot_aware"
    assert account["account"]["initial_capital"] == 50000
    assert account["account"]["current_cash"] == 50000
    assert account["account"]["latest_total_equity"] == 50000
    assert account["account"]["reserved_cash"] == 0
    assert account["position_sizing"]["min_trade_value"] == 1500
    assert account["execution"]["round_lot"] == 100
    assert strategy["execution"]["max_positions"] == 8
    assert strategy["execution"]["equal_weight_target_universe_size"] == 8
    assert strategy["execution"]["max_new_positions_per_day"] == 1
    assert strategy["execution"]["max_adds_per_day"] == 2
    assert strategy["execution"]["lot_aware_sizing"] is True
    assert universe["target_size"] == 36
    assert universe["target_universe_size"] == 36


def test_reference_and_retail_profile_hashes_are_distinct() -> None:
    reference = load_yaml("config/account_profiles/reference_200k.yml")
    retail = load_yaml("config/account_profiles/retail_50k.yml")
    lot_aware = load_yaml("config/account_profiles/retail_50k_lot_aware.yml")
    assert stable_hash(reference) != stable_hash(retail)
    assert stable_hash(retail) != stable_hash(lot_aware)
    assert reference["research_only"] is True
    assert retail["research_only"] is False
    assert lot_aware["account"]["initial_capital"] == 50000


def test_generated_profile_configs_keep_research_only_out_of_default_release() -> None:
    configs = {
        "v2_strategy": load_yaml("config/strategy_v2.yml"),
    }
    profiles = _profile_configs(configs)
    assert profiles["reference_200k_current"]["research_only"] is True
    assert profiles["actual_50k_unmodified"]["research_only"] is True
    assert profiles["actual_50k_retail"]["research_only"] is False
    assert profiles["actual_50k_lot_aware"]["research_only"] is True
    assert profiles["actual_50k_retail"]["account"]["account_profile"] == "retail_50k"
    assert profiles["actual_50k_lot_aware"]["account"]["account_profile"] == "retail_50k_lot_aware"
    assert profiles["actual_50k_lot_aware"]["strategy"]["execution"]["max_positions"] == 8
    assert profiles["actual_50k_lot_aware"]["strategy"]["execution"]["equal_weight_target_universe_size"] == 8


def test_profile_status_warns_on_low_execution_ratio_and_fails_position_limit() -> None:
    account = copy.deepcopy(load_yaml("config/account_profiles/retail_50k.yml"))
    strategy = copy.deepcopy(load_yaml("config/strategy_v2.yml"))
    account_report = {
        "raw_buy_signal_count": 100,
        "executable_raw_buy_ratio": 0.2,
        "min_trade_amount_block_count": 10,
    }
    metrics = {
        "avg_positions": 5,
        "max_positions": 8,
        "max_weight_after": 0.12,
        "total_fees": 10,
        "total_tax": 0,
        "total_slippage": 0,
    }
    status, warnings, violations = _profile_status(
        profile_id="actual_50k_retail",
        metrics=metrics,
        account_report=account_report,
        account=account,
        strategy=strategy,
        years=3.0,
    )
    assert status == "WARN"
    assert any(item["code"] == "ACCOUNT_CONSTRAINTS_DOMINATE_EXECUTION" for item in warnings)
    assert not violations

    metrics["max_positions"] = 9
    status, _, violations = _profile_status(
        profile_id="actual_50k_retail",
        metrics=metrics,
        account_report=account_report,
        account=account,
        strategy=strategy,
        years=3.0,
    )
    assert status == "FAIL"
    assert any(item["code"] == "MAX_POSITIONS_EXCEED_LIMIT" for item in violations)


def test_lot_aware_adoption_rejects_when_rules_not_met() -> None:
    retail = {
        "profile_id": "actual_50k_retail",
        "executable_raw_buy_ratio": 0.02,
        "executable_buy_count": 12,
        "min_trade_amount_block_ratio": 0.3,
        "lot_size_zero_block_count": 100,
        "max_drawdown": -0.04,
    }
    lot = {
        "profile_id": "actual_50k_lot_aware",
        "executable_raw_buy_ratio": 0.01,
        "executable_buy_count": 8,
        "min_trade_amount_block_ratio": 0.4,
        "lot_size_zero_block_count": 90,
        "portfolio_max_positions": 8,
        "violations": [],
        "annualized_transaction_cost_drag": 0.01,
        "max_drawdown": -0.05,
        "buy_trades": 8,
    }
    adopted, _, failures = _adoption_decision([retail, lot])
    assert adopted is False
    assert failures
