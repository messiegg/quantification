from __future__ import annotations

import pandas as pd

from scripts import check_data_freshness as freshness


def _target_info(target: str = "2026-04-30", is_trading: bool = False) -> dict:
    return {
        "requested_as_of_date": "2026-05-04",
        "requested_as_of_is_trading_day": is_trading,
        "target_trading_date": target,
        "target_trading_date_is_valid": True,
        "calendar_source": "fixture",
        "calendar_min_date": "2026-04-01",
        "calendar_max_date": target,
        "calendar_market": "A_SHARE",
    }


def _patch_common(monkeypatch, feature_date: str, benchmark_date: str, target: str = "2026-04-30") -> None:
    monkeypatch.setattr(
        freshness,
        "load_yaml_optional",
        lambda path: {
            "observation": {
                "max_stale_calendar_days_for_daily_report": 60,
                "max_stale_trading_days_for_daily_report": 0,
                "require_data_max_date_ge_target_trading_date": True,
                "calendar_market": "A_SHARE",
            }
        },
    )
    monkeypatch.setattr(freshness, "resolve_target_trading_date", lambda *args, **kwargs: _target_info(target))
    monkeypatch.setattr(freshness, "_feature_max_date", lambda: (pd.Timestamp(feature_date), "fixture_features"))

    def fake_max(path, date_columns=("date", "trade_date")):
        if str(path) == "data/raw/benchmark_daily.parquet":
            return pd.Timestamp(benchmark_date)
        return pd.Timestamp(benchmark_date)

    monkeypatch.setattr(freshness, "_max_date_from_parquet", fake_max)
    monkeypatch.setattr(freshness, "_universe_max_effective_date", lambda: pd.Timestamp(target))
    monkeypatch.setattr(freshness, "_json_optional", lambda path: {"as_of_date": target})
    monkeypatch.setattr(
        freshness,
        "trading_dates_between",
        lambda start, end, market="A_SHARE", observation_config=None: []
        if str(start) >= str(end)
        else ["2026-04-30"],
    )


def test_2026_05_04_resolves_to_non_trading_day_target_2026_04_30() -> None:
    info = freshness.resolve_target_trading_date("2026-05-04")
    assert info["requested_as_of_is_trading_day"] is False
    assert info["target_trading_date"] == "2026-04-30"


def test_trading_day_maps_to_itself() -> None:
    info = freshness.resolve_target_trading_date("2026-04-30")
    assert info["requested_as_of_is_trading_day"] is True
    assert info["target_trading_date"] == "2026-04-30"


def test_data_max_before_target_blocks(monkeypatch) -> None:
    _patch_common(monkeypatch, feature_date="2026-04-03", benchmark_date="2026-04-03")
    report = freshness.build_data_freshness_report("2026-05-04", write_report=False)
    assert report["allowed_actions"] == "historical_review_only"
    assert "DATA_MAX_DATE_BEFORE_TARGET_TRADING_DATE" in report["blocking_reason"]
    assert "STALE_TRADING_DAYS_EXCEED_LIMIT" in report["blocking_reason"]


def test_data_max_equal_target_passes(monkeypatch) -> None:
    _patch_common(monkeypatch, feature_date="2026-04-30", benchmark_date="2026-04-30")
    report = freshness.build_data_freshness_report("2026-05-04", write_report=False)
    assert report["allowed_actions"] == "observation_report_allowed"
    assert report["is_data_current_for_target_trading_date"] is True


def test_feature_before_target_blocks(monkeypatch) -> None:
    _patch_common(monkeypatch, feature_date="2026-04-29", benchmark_date="2026-04-30")
    report = freshness.build_data_freshness_report("2026-05-04", write_report=False)
    assert "FEATURE_MAX_DATE_BEFORE_TARGET_TRADING_DATE" in report["blocking_reason"]


def test_benchmark_before_target_blocks(monkeypatch) -> None:
    _patch_common(monkeypatch, feature_date="2026-04-30", benchmark_date="2026-04-29")
    report = freshness.build_data_freshness_report("2026-05-04", write_report=False)
    assert "BENCHMARK_MAX_DATE_BEFORE_TARGET_TRADING_DATE" in report["blocking_reason"]
