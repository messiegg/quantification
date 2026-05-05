from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

from scripts import audit_config_consistency as config_audit
from scripts import audit_data_freshness as freshness_audit
from scripts import audit_universe_integrity as universe_audit
from scripts import refresh_universe
from scripts import run_release_guard as release_guard
from scripts.run_backtest_sensitivity import classify_parameter_binding
from src.pipeline.strict_data import build_market_cap_daily


def _rules() -> dict:
    return {
        "target_size": 4,
        "floor_size": 3,
        "ceiling_size": 5,
        "max_per_industry": 2,
        "bucket_filters": {
            "base": {
                "market_cap_billion_min": 300,
                "avg_amount_60d_million_min": 50,
                "require_industry": True,
            },
            "defensive_dividend": {
                "market_cap_billion_min": 300,
                "dv_ttm_min": 0.025,
            },
        },
        "core_required_fields": ["industry", "market_cap_billion", "avg_amount_60d_million"],
    }


def _stock(symbol: str = "600000.sh", market_cap: float = 400.0, selected_as: str = "new_entry") -> dict:
    return {
        "symbol": symbol,
        "name": "fixture",
        "bucket": "defensive_dividend",
        "industry_l1": "银行",
        "market_cap_billion": market_cap,
        "avg_amount_60d_million": 100,
        "dv_ttm": 0.03,
        "selected_as": selected_as,
    }


def test_universe_under_floor_fails() -> None:
    report = universe_audit.build_universe_integrity_report(
        write_report=False,
        universe_payload={"as_of_date": "2026-04-30", "stocks": [_stock()]},
        rules_payload=_rules(),
    )
    assert report["status"] == "FAIL"
    assert any(item["code"] == "UNIVERSE_UNDER_FLOOR" for item in report["violations"])


def test_universe_market_cap_violation_fails() -> None:
    report = universe_audit.build_universe_integrity_report(
        write_report=False,
        universe_payload={"as_of_date": "2026-04-30", "stocks": [_stock(market_cap=100.0)] * 3},
        rules_payload=_rules(),
    )
    assert report["status"] == "FAIL"
    assert any(item["code"] == "HARD_FILTER_VIOLATION" for item in report["violations"])


def test_universe_feature_enrichment_populates_hard_filter_results() -> None:
    rules = _rules()
    rules["floor_size"] = 1
    rules["target_size"] = 1
    rules["ceiling_size"] = 2
    rules["core_required_fields"] = ["industry", "market_cap_billion", "avg_amount_60d_million", "pb"]
    feature_frame = pd.DataFrame(
        [
            {
                "symbol": "600000.sh",
                "date": "2026-04-30",
                "industry": "银行",
                "market_cap_billion": 400.0,
                "avg_amount_60d_million": 100.0,
                "pb": 0.8,
                "dv_ttm": 0.03,
                "listed_days": 2000,
                "is_a_share": True,
                "is_st": False,
            }
        ]
    )
    report = universe_audit.build_universe_integrity_report(
        write_report=False,
        universe_payload={"as_of_date": "2026-04-30", "stocks": [_stock()]},
        rules_payload=rules,
        feature_frame=feature_frame,
    )

    assert report["status"] == "PASS"
    constituent = report["constituents"][0]
    assert constituent["pb"] == 0.8
    assert constituent["missing_fields"] == []
    assert any(item["field"] == "pb" and item["status"] == "PASS" for item in constituent["hard_filter_results"]["checks"])


def test_universe_missing_feature_field_enters_missing_fields() -> None:
    rules = _rules()
    rules["floor_size"] = 1
    rules["target_size"] = 1
    rules["ceiling_size"] = 2
    rules["core_required_fields"] = ["industry", "market_cap_billion", "avg_amount_60d_million", "pb"]
    feature_frame = pd.DataFrame(
        [
            {
                "symbol": "600000.sh",
                "date": "2026-04-30",
                "industry": "银行",
                "market_cap_billion": 400.0,
                "avg_amount_60d_million": 100.0,
                "dv_ttm": 0.03,
                "listed_days": 2000,
                "is_a_share": True,
                "is_st": False,
            }
        ]
    )
    report = universe_audit.build_universe_integrity_report(
        write_report=False,
        universe_payload={"as_of_date": "2026-04-30", "stocks": [_stock()]},
        rules_payload=rules,
        feature_frame=feature_frame,
    )

    assert report["status"] == "FAIL"
    assert "pb" in report["constituents"][0]["missing_fields"]
    assert "missing_pb" in report["constituents"][0]["failed_filters"]


def test_manual_override_without_basis_fails() -> None:
    report = universe_audit.build_universe_integrity_report(
        write_report=False,
        universe_payload={"as_of_date": "2026-04-30", "stocks": [_stock(selected_as="manual_override")] * 3},
        rules_payload=_rules(),
    )
    assert report["status"] == "FAIL"
    assert any(item["code"] == "MANUAL_OVERRIDE_WITHOUT_BASIS" for item in report["violations"])


def test_market_cap_daily_uses_100m_unit_conversion() -> None:
    price = pd.DataFrame(
        [{"code": "600000.sh", "date": "2026-04-30", "open": 10.0, "high": 10.0, "low": 10.0, "close": 20.0, "volume": 1, "amount": 1}]
    )
    shares = pd.DataFrame([{"symbol": "600000.sh", "date": "2026-04-30", "total_shares": 20_000_000_000, "float_shares": 10_000_000_000}])

    frame = build_market_cap_daily(price, shares)

    assert frame.loc[0, "market_cap_billion"] == 4000.0


def test_refresh_universe_defaults_to_combined_v2_rules(monkeypatch) -> None:
    monkeypatch.setattr(sys, "argv", ["refresh_universe.py"])

    args = refresh_universe.parse_args()

    assert args.universe_rules_config == "config/universe_rules_v2.yml"


def test_runtime_stamp_tax_conflict_fails(monkeypatch) -> None:
    monkeypatch.setattr(config_audit, "_check_manifest_conflicts", lambda active, issues: None)
    report = config_audit.build_config_consistency_report(
        write_report=False,
        readme_text="不接券商，不自动下单。",
        strategy={"profile": "combined_v2", "execution": {"stamp_tax_rate": 0.001, "fee_rate": 0.0003}},
        account={"execution": {"stamp_duty_rate_sell": 0.0005, "commission_rate": 0.0003}, "position_sizing": {}},
        universe_rules={"target_size": 36, "target_universe_size": 36},
        data_sources={"defaults": {}},
    )
    assert report["status"] == "FAIL"
    assert any(item["code"] == "RUNTIME_CONFLICT_STAMP_TAX" for item in report["violations"])


def test_readme_runtime_mismatch_warns(monkeypatch) -> None:
    monkeypatch.setattr(config_audit, "_check_manifest_conflicts", lambda active, issues: None)
    report = config_audit.build_config_consistency_report(
        write_report=False,
        readme_text="行业上限：每个行业最多 2 只。不接券商，不自动下单。",
        strategy={"profile": "combined_v2", "execution": {"stamp_tax_rate": 0.0005, "fee_rate": 0.0003}},
        account={"execution": {"stamp_duty_rate_sell": 0.0005, "commission_rate": 0.0003}, "position_sizing": {}},
        universe_rules={"target_size": 36, "target_universe_size": 36, "max_per_industry": 3, "max_names_per_industry": 3},
        data_sources={"defaults": {}},
    )
    assert report["status"] == "WARN"
    assert any(item["code"] == "DOC_MISMATCH_INDUSTRY_CAP" for item in report["warnings"])


def test_target_trade_date_after_market_data_asof_fails() -> None:
    report = freshness_audit.build_audit_data_freshness_report(
        "2026-05-04",
        write_report=False,
        freshness_payload={
            "allowed_actions": "historical_review_only",
            "blocking_reason": "DATA_MAX_DATE_BEFORE_TARGET_TRADING_DATE",
            "target_trading_date": "2026-04-30",
            "data_max_date": "2026-04-03",
            "feature_max_date": "2026-04-03",
            "benchmark_max_date": "2026-04-30",
        },
    )
    assert report["status"] == "FAIL"
    assert any(item["code"] == "MARKET_DATA_BEFORE_TARGET" for item in report["violations"])


def test_sensitivity_config_hash_unchanged_fails_binding() -> None:
    status, reason = classify_parameter_binding(
        changed_params=["x"],
        base_config_hash="same",
        variant_config_hash="same",
        base_trace={},
        variant_trace={},
    )
    assert status == "FAIL"
    assert reason == "PARAM_NOT_WIRED"


def test_sensitivity_identical_paths_are_non_binding() -> None:
    trace = {
        "action_path_hash": "a",
        "position_path_hash": "p",
        "equity_curve_hash": "e",
        "raw_buy_signal_count": 1,
        "raw_sell_signal_count": 0,
        "blocked_signal_count": 0,
    }
    status, reason = classify_parameter_binding(
        changed_params=["threshold"],
        base_config_hash="base",
        variant_config_hash="variant",
        base_trace=trace,
        variant_trace=dict(trace),
    )
    assert status == "NON_BINDING"
    assert reason == "NO_SIGNAL_COVERAGE"


def test_release_status_fails_on_any_core_fail() -> None:
    frame = pd.DataFrame([{"status": "PASS"}, {"status": "FAIL"}])
    assert release_guard._release_status_from_rows(frame) == "FAIL"


def test_release_manifest_never_allows_auto_trading(monkeypatch, tmp_path: Path) -> None:
    def fake_resolve(path: str | Path) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else tmp_path / candidate

    monkeypatch.setattr(release_guard, "resolve_path", fake_resolve)
    monkeypatch.setattr(
        release_guard,
        "write_json",
        lambda path, payload: (fake_resolve(path).parent.mkdir(parents=True, exist_ok=True), fake_resolve(path).write_text(json.dumps(payload), encoding="utf-8"))[1],
    )
    monkeypatch.setattr(release_guard, "git_branch", lambda: "codex/test")
    monkeypatch.setattr(release_guard, "git_commit", lambda: "abc")
    frame = pd.DataFrame([{"check_id": "X", "check_name": "fixture", "status": "PASS", "actual": "ok"}])
    release_guard._write_release_manifest(
        frame,
        "2026-05-04",
        {
            "data_freshness": {"status": "PASS", "target_trade_date": "2026-04-30"},
            "account_constraints": {"status": "WARN", "warnings": []},
        },
    )
    payload = json.loads((tmp_path / "reports/backtest/release/combined_v2_rc_manifest.json").read_text(encoding="utf-8"))
    assert payload["auto_trading_approved"] is False
    assert payload["broker_integration_enabled"] is False
    assert payload["llm_decision_allowed"] is False


def test_release_guard_requires_ci_sensitivity_report(monkeypatch, tmp_path: Path) -> None:
    report_path = tmp_path / "reports/backtest/robustness/sensitivity_report.json"
    report_path.parent.mkdir(parents=True)
    report_path.write_text(json.dumps({"status": "PASS", "mode": "full", "variants": []}), encoding="utf-8")

    def fake_resolve(path: str | Path) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else tmp_path / candidate

    monkeypatch.setattr(release_guard, "resolve_path", fake_resolve)
    rows: list[dict] = []
    release_guard._check_sensitivity(rows)

    assert rows[0]["status"] == "FAIL"
