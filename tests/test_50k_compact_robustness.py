from __future__ import annotations

import json
from pathlib import Path

import pandas as pd
import pytest

from scripts import run_50k_compact_experiments as compact
from src.utils.config import resolve_path


def _row(variant: str, **overrides) -> dict:
    values = {
        "variant": variant,
        "profile": "combined_v2_50k_compact",
        "research_only": True,
        "capital": 50_000.0,
        "round_lot": 100,
        "max_positions": 6,
        "max_tranches": 1,
        "target_universe_size": 8,
        "cash_reserve_ratio": 0.15,
        "max_new_positions_per_day": 1,
        "max_adds_per_day": 0,
        "annual_return": 0.0731252803049531,
        "cumulative_return": 0.2254692482530003,
        "max_drawdown": -0.1061596825035998,
        "annual_volatility": 0.681377699668382,
        "total_trades": 20,
        "buy_trades": 12,
        "sell_trades": 8,
        "average_cash_ratio": 0.343604320753212,
        "average_exposure": 0.6563956792467879,
        "max_exposure": 0.796237897909835,
        "average_positions": 5.4366391184573,
        "max_positions_used": 6,
        "executable_buy_count": 12,
        "strategy_eligible_count": 240,
        "account_actionable_buy_count": 12,
        "watch_only_count": 228,
        "executable_account_actionable_ratio": 1.0,
        "executable_strategy_eligible_ratio": 0.05,
        "industry_concentration_max": 1.0,
        "top_block_or_watch_reasons": "{'WATCH_ONLY_PORTFOLIO_FULL': 163}",
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
        "passes_hard_conditions": True,
    }
    values.update(overrides)
    return values


@pytest.fixture()
def metrics_csv(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    rows = [
        _row(compact.OBSERVATION_CANDIDATE_VARIANT),
        _row("mp6_tr1_tu10_cr15_add0", target_universe_size=10, watch_only_count=228),
        _row("mp5_tr1_tu8_cr15_add0", max_positions=5, annual_return=0.043, cumulative_return=0.13, max_drawdown=-0.13, watch_only_count=300),
        _row("mp5_tr1_tu10_cr20_add0", max_positions=5, target_universe_size=10, cash_reserve_ratio=0.20, annual_return=0.041, cumulative_return=0.12, max_drawdown=-0.12, watch_only_count=320),
        _row("mp6_tr2_tu8_cr15_add0", max_tranches=2, annual_return=0.014, cumulative_return=0.04, max_drawdown=-0.05, watch_only_count=620),
        _row("mp6_tr1_tu8_cr15_add1", max_adds_per_day=1),
        _row("mp8_tr1_tu8_cr15_add0", max_positions=8, annual_return=0.086, cumulative_return=0.27, max_drawdown=-0.08, max_exposure=0.848, total_trades=30, watch_only_count=180),
    ]
    csv_path = tmp_path / "compact_experiment_metrics.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    monkeypatch.setattr(compact, "OUT_DIR", str(tmp_path))
    monkeypatch.setattr(compact, "ROBUSTNESS_CSV", str(tmp_path / "compact_neighborhood_robustness.csv"))
    monkeypatch.setattr(compact, "ROBUSTNESS_MD", str(tmp_path / "compact_neighborhood_robustness.md"))
    monkeypatch.setattr(compact, "ROBUSTNESS_JSON", str(tmp_path / "compact_neighborhood_robustness.json"))
    monkeypatch.setattr(compact, "OBSERVATION_CANDIDATE_MD", str(tmp_path / "compact_observation_candidate.md"))
    monkeypatch.setattr(compact, "OBSERVATION_CANDIDATE_JSON", str(tmp_path / "compact_observation_candidate.json"))
    return csv_path


def test_neighborhood_builder_reads_existing_metrics_without_rerunning_matrix(
    metrics_csv: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(compact, "run_experiments", lambda: pytest.fail("should not rerun compact matrix"))
    monkeypatch.setattr(compact, "load_feature_window", lambda *args, **kwargs: pytest.fail("should not load full data"))

    result = compact.build_observation_candidate_reports(str(metrics_csv))

    assert result["candidate"]["variant"] == compact.OBSERVATION_CANDIDATE_VARIANT
    assert metrics_csv.with_name("compact_neighborhood_robustness.csv").exists()
    assert metrics_csv.with_name("compact_observation_candidate.json").exists()


def test_real_metrics_contain_required_best_candidate() -> None:
    frame = compact._load_compact_metrics(compact.OUT_CSV)
    best = compact._best_candidate_record(frame)

    assert best["variant"] == "mp6_tr1_tu8_cr15_add0"


def test_robustness_status_is_controlled_enum(metrics_csv: Path) -> None:
    result = compact.build_observation_candidate_reports(str(metrics_csv))

    assert result["robustness"]["status"] in compact.ROBUSTNESS_STATUSES


def test_observation_candidate_does_not_claim_release_pass(metrics_csv: Path) -> None:
    compact.build_observation_candidate_reports(str(metrics_csv))
    payload = json.loads(metrics_csv.with_name("compact_observation_candidate.json").read_text(encoding="utf-8"))
    md = metrics_csv.with_name("compact_observation_candidate.md").read_text(encoding="utf-8")

    assert payload["default_release_profile_replacement"] is False
    assert payload["auto_trading_approved"] is False
    assert "PASS_CANDIDATE" not in md
    assert "release_status: PASS" not in md
    assert "status: PASS" not in md


def test_observation_candidate_does_not_set_compact_as_default_release(metrics_csv: Path) -> None:
    result = compact.build_observation_candidate_reports(str(metrics_csv))

    assert result["candidate"]["default_release_profile_replacement"] is False
    assert "不得替换 release 默认口径" in result["candidate"]["observation_conclusion"]


def test_compact_candidate_never_uses_more_than_eight_positions(metrics_csv: Path) -> None:
    result = compact.build_observation_candidate_reports(str(metrics_csv))
    robustness = pd.read_csv(metrics_csv.with_name("compact_neighborhood_robustness.csv"))

    assert result["candidate"]["selected_metrics"]["max_positions"] <= 8
    assert robustness["max_positions"].max() <= 8


def test_200k_profile_is_not_candidate_decision_basis(metrics_csv: Path) -> None:
    compact.build_observation_candidate_reports(str(metrics_csv))
    payload = json.loads(metrics_csv.with_name("compact_observation_candidate.json").read_text(encoding="utf-8"))
    md = metrics_csv.with_name("compact_observation_candidate.md").read_text(encoding="utf-8")

    assert "200k" not in json.dumps(payload, ensure_ascii=False).lower()
    assert "200k" not in md.lower()


def test_real_generated_candidate_is_observation_only_when_present() -> None:
    path = resolve_path(compact.OBSERVATION_CANDIDATE_JSON)
    if not path.exists():
        pytest.skip("observation candidate report has not been generated yet")
    payload = json.loads(path.read_text(encoding="utf-8"))

    assert payload["variant"] == "mp6_tr1_tu8_cr15_add0"
    assert payload["research_only"] is True
    assert payload["default_release_profile_replacement"] is False
    assert payload["auto_trading_approved"] is False
