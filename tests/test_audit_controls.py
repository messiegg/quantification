from __future__ import annotations

import copy
import json
from pathlib import Path

import pandas as pd

from scripts.audit_backtest_lookahead import _audit_financial_availability
from scripts.run_backtest_compare import _generate_v2_history
from scripts.run_backtest_sensitivity import _variants


def test_financial_announcement_after_signal_is_rejected() -> None:
    features = pd.DataFrame(
        [
            {
                "date": "2024-04-10",
                "symbol": "600000.sh",
                "roe": 10.0,
                "report_date": "2024-03-31",
                "announcement_date": "2024-04-20",
            }
        ]
    )

    rows, violations = _audit_financial_availability(features, fallback_days=30)

    roe = [row for row in rows if row["check_id"] == "LH-FIN-roe"][0]
    assert roe["status"] == "FAIL"
    assert violations[0]["violation_type"] == "announcement_date_after_signal_date"


def test_financial_report_date_fallback_uses_lag() -> None:
    features = pd.DataFrame(
        [
            {
                "date": "2024-04-10",
                "symbol": "600000.sh",
                "roe": 10.0,
                "report_date": "2024-03-31",
                "announcement_date": pd.NA,
            }
        ]
    )

    rows, violations = _audit_financial_availability(features, fallback_days=30)

    roe = [row for row in rows if row["check_id"] == "LH-FIN-roe"][0]
    assert roe["status"] == "FAIL"
    assert violations[0]["violation_type"] == "report_date_fallback_after_signal_date"


def test_v2_history_generation_uses_source_as_of_not_effective_date(tmp_path: Path, monkeypatch) -> None:
    source_dir = tmp_path / "baseline_history"
    target_dir = tmp_path / "v2_history"
    source_dir.mkdir()
    (source_dir / "2024-01-03.json").write_text(
        json.dumps({"as_of_date": "2024-01-02", "effective_from": "2024-01-03", "effective_to": "2024-01-31", "stocks": []}),
        encoding="utf-8",
    )
    features = pd.DataFrame(
        [
            {"date": "2024-01-02", "symbol": "OLD.sh", "score": 1},
            {"date": "2024-01-03", "symbol": "FUTURE.sh", "score": 100},
        ]
    )

    def fake_candidate_pool(snapshot, universe_rules_cfg, metric_map_cfg, as_of_date):
        return snapshot.rename(columns={"score": "final_score"})

    def fake_effective_universe(candidate_pool, previous_payload, empty_holdings, universe_rules_cfg):
        return candidate_pool.sort_values("final_score", ascending=False).head(1), []

    monkeypatch.setattr("scripts.run_backtest_compare.build_candidate_pool", fake_candidate_pool)
    monkeypatch.setattr("scripts.run_backtest_compare.build_effective_universe", fake_effective_universe)

    _generate_v2_history(features, source_dir, target_dir, {"methodology_version": "combined_v2", "rebalance_frequency": "monthly"}, {})

    payload = json.loads((target_dir / "2024-01-03.json").read_text(encoding="utf-8"))
    assert payload["as_of_date"] == "2024-01-02"
    assert payload["effective_from"] == "2024-01-03"
    assert payload["stocks"][0]["symbol"] == "OLD.sh"


def test_sensitivity_variants_do_not_mutate_current_configs(configs: dict) -> None:
    audit_configs = {
        "v2_strategy": copy.deepcopy(configs["strategy"]),
        "v2_universe": copy.deepcopy(configs["universe_rules"]),
    }
    before_strategy = copy.deepcopy(audit_configs["v2_strategy"])
    before_universe = copy.deepcopy(audit_configs["v2_universe"])

    variants = _variants(audit_configs)
    variants[0]["strategy"]["execution"]["default_tranches"] = 99

    assert audit_configs["v2_strategy"] == before_strategy
    assert audit_configs["v2_universe"] == before_universe
