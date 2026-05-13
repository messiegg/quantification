from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from scripts.audit_backtest_lookahead import build_valuation_field_resolution
from scripts.build_combined_v2_release_candidate import build_release_manifest, build_report_consistency_check
from scripts.check_report_freshness import build_report_freshness_check
from scripts.rc_hash_scope import CODE_HASH_SCOPE_VERSION, code_hash_manifest
from scripts.verify_combined_v2_rc import verify_release_candidate
from src.strategy.valuation_resolution import resolve_industry_valuation_quantile, resolve_stock_valuation_quantile
from src.utils.config import load_yaml, resolve_path


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_valuation_resolver_matches_v2_actual_fields() -> None:
    metric_map = load_yaml("config/metric_map.yml")
    defensive_pe = {
        "date": "2026-04-03",
        "industry": "通信",
        "bucket": "defensive_dividend",
        "pe_ttm": 18.0,
        "stock_pe_ttm_q_blended": 22.0,
        "industry_pe_ttm_q_blended": 33.0,
        "stock_pb_q_blended": 44.0,
        "industry_pb_q_blended": 55.0,
    }
    stock = resolve_stock_valuation_quantile(defensive_pe, "defensive_dividend", metric_map)
    industry = resolve_industry_valuation_quantile(defensive_pe, "defensive_dividend", metric_map)
    assert stock.value == 22.0
    assert stock.source_field == "stock_pe_ttm_q_blended"
    assert stock.metric == "pe_ttm"
    assert industry.value == 33.0
    assert industry.source_field == "industry_pe_ttm_q_blended"

    defensive_pb_fallback = dict(defensive_pe, pe_ttm=pd.NA)
    stock = resolve_stock_valuation_quantile(defensive_pb_fallback, "defensive_dividend", metric_map)
    assert stock.value == 44.0
    assert stock.source_field == "stock_pb_q_blended"
    assert stock.metric == "pb"
    assert stock.fallback_used is True

    cyclical = dict(defensive_pe, industry="有色金属", bucket="cyclical_rotation")
    stock = resolve_stock_valuation_quantile(cyclical, "cyclical_rotation", metric_map)
    industry = resolve_industry_valuation_quantile(cyclical, "cyclical_rotation", metric_map)
    assert stock.value == 44.0
    assert stock.metric == "pb"
    assert industry.value == 55.0
    assert industry.metric == "pb"


def test_lookahead_field_resolution_checks_resolver_source_fields() -> None:
    scores = pd.DataFrame(
        [
            {
                "date": "2024-01-03",
                "ts_code": "600000.sh",
                "industry": "银行",
                "bucket": "defensive_dividend",
                "stock_valuation_quantile": 20.0,
                "stock_valuation_quantile_source_field": "stock_pb_q_blended",
                "stock_valuation_metric": "pb",
                "industry_valuation_quantile": 30.0,
                "industry_valuation_quantile_source_field": "industry_pb_q_blended",
                "industry_valuation_metric": "pb",
            }
        ]
    )
    stock_daily = pd.DataFrame([{"date": "2024-01-02", "symbol": "600000.sh", "pb": 1.0}])
    industry_daily = pd.DataFrame([{"date": "2024-01-02", "industry_name": "银行", "pb": 1.1}])
    resolution = build_valuation_field_resolution(scores, stock_daily, industry_daily)
    row = resolution.iloc[0]
    assert row["pass_or_fail"] == "PASS"
    assert row["stock_valuation_quantile_source_field"] == "stock_pb_q_blended"
    assert row["max_source_date_used"] == "2024-01-02"


def test_report_consistency_and_manifest_do_not_mutate_trades_detailed(tmp_path: Path) -> None:
    trades_path = resolve_path("reports/backtest/combined_v2_trades_detailed.csv")
    before = _sha256(trades_path)
    build_report_consistency_check()
    build_release_manifest(json_path=tmp_path / "manifest.json", md_path=tmp_path / "manifest.md")
    after = _sha256(trades_path)
    assert after == before


def test_current_combined_v2_next_bar_strict_metrics_match_rc() -> None:
    manifest = load_yaml("reports/backtest/release/combined_v2_rc_manifest.json")
    execution = pd.read_csv(resolve_path("reports/backtest/audit/execution_mode_compare.csv"))
    row = execution[(execution["profile"] == "combined_v2") & (execution["execution_mode"] == "next_bar")].iloc[0]
    assert abs(float(row["annual_return"]) - float(manifest["annual_return"])) < 1e-12
    assert abs(float(row["cumulative_return"]) - float(manifest["cumulative_return"])) < 1e-12
    assert abs(float(row["max_drawdown"]) - float(manifest["max_drawdown"])) < 1e-12
    assert int(row["total_trades"]) == int(manifest["total_trades"])


def test_release_manifest_matches_current_trade_and_nav_artifacts(tmp_path: Path) -> None:
    code_manifest_path = tmp_path / "code_manifest.json"
    manifest = build_release_manifest(json_path=tmp_path / "manifest.json", md_path=tmp_path / "manifest.md", code_manifest_path=code_manifest_path)
    execution = pd.read_csv(resolve_path("reports/backtest/audit/execution_mode_compare.csv"))
    row = execution[(execution["profile"] == "combined_v2") & (execution["execution_mode"] == "next_bar")].iloc[0]
    expected_final_nav = float(manifest["initial_capital"]) * (1.0 + float(row["cumulative_return"]))
    assert abs(float(manifest["final_nav"]) - expected_final_nav) < 1e-6
    assert int(manifest["total_trades"]) == int(row["total_trades"])
    trade_hash = next(item for item in manifest["key_output_file_hashes"] if item["path"] == "reports/backtest/combined_v2_trades_detailed.csv")
    assert trade_hash["exists"]
    assert trade_hash["sha256"] == _sha256(resolve_path("reports/backtest/combined_v2_trades_detailed.csv"))
    assert manifest["hash_scope"]["code_scope_version"] == CODE_HASH_SCOPE_VERSION
    assert code_manifest_path.exists()


def test_verify_combined_v2_rc_passes_current_manifest() -> None:
    verify = verify_release_candidate(rerun_backtest=False, write_report=False)
    metrics = verify[verify["check_id"].astype(str).str.startswith("MET-")]
    assert set(metrics["status"]) == {"PASS"}
    manifest = load_yaml("reports/backtest/release/combined_v2_rc_manifest.json")
    total_trades = verify[verify["check_id"] == "MET-total_trades"].iloc[0]
    assert int(total_trades["expected"]) == int(manifest["total_trades"])
    assert f"total_trades 必须等于 {manifest['total_trades']}" in str(total_trades["recommendation"])
    assert "total_trades 必须等于 76" not in str(total_trades["recommendation"])


def test_current_rc_verify_report_has_no_release_total_trades_76_residue() -> None:
    text = resolve_path("reports/backtest/release/combined_v2_rc_verify.md").read_text(encoding="utf-8")
    assert "expected=41 | actual=41 | total_trades 必须等于 76" not in text


def test_verify_combined_v2_rc_fails_on_strategy_hash_drift() -> None:
    path = resolve_path("config/strategy_v2.yml")
    original = path.read_bytes()
    try:
        path.write_bytes(original + b"\n# test hash drift\n")
        verify = verify_release_candidate(rerun_backtest=False, write_report=False)
        row = verify[verify["check_name"] == "config/strategy_v2.yml sha256 matches RC manifest"].iloc[0]
        assert row["status"] == "FAIL"
    finally:
        path.write_bytes(original)


def test_build_and_verify_use_same_code_hash_scope(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    code_manifest_path = tmp_path / "code_manifest.json"
    build_release_manifest(json_path=manifest_path, md_path=tmp_path / "manifest.md", code_manifest_path=code_manifest_path)
    verify = verify_release_candidate(
        manifest_path=manifest_path,
        code_manifest_path=code_manifest_path,
        rerun_backtest=False,
        write_report=False,
    )
    scope_rows = verify[verify["check_id"] == "CODE-SCOPE-001"]
    if not scope_rows.empty:
        assert set(scope_rows["status"]) == {"PASS"}
    code = verify[verify["check_id"] == "CODE-001"].iloc[0]
    assert code["status"] == "PASS"
    assert code["actual"] == "no drift"


def test_verify_detects_code_hash_drift_after_rc_build(tmp_path: Path) -> None:
    manifest_path = tmp_path / "manifest.json"
    code_manifest_path = tmp_path / "code_manifest.json"
    build_release_manifest(json_path=manifest_path, md_path=tmp_path / "manifest.md", code_manifest_path=code_manifest_path)
    payload = code_hash_manifest()
    payload["files"][0]["sha256"] = "0" * 64
    code_manifest_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    verify = verify_release_candidate(
        manifest_path=manifest_path,
        code_manifest_path=code_manifest_path,
        rerun_backtest=False,
        write_report=False,
    )
    code = verify[verify["check_id"] == "CODE-001"].iloc[0]
    assert code["status"] == "WARN"
    assert payload["files"][0]["path"] in str(code["actual"])


def test_check_report_freshness_detects_legacy_attribution_line(tmp_path: Path) -> None:
    report = tmp_path / "combined_v2_attribution_report.md"
    report.write_text("signal BUY_1: 成交 39，已实现 0.00\n", encoding="utf-8")
    frame = build_report_freshness_check(
        scan_globs=[str(tmp_path / "*.md")],
        output_csv=tmp_path / "check.csv",
        output_md=tmp_path / "check.md",
    )
    matched = frame[frame["check_name"] == "old_attribution_residue"]
    assert not matched.empty
    assert set(matched["status"]) == {"FAIL"}


def test_current_reports_have_no_unmarked_legacy_attribution_lines() -> None:
    frame = build_report_freshness_check(write_report=False)
    failures = frame[(frame["status"] == "FAIL") & (frame["check_name"].str.contains("old_attribution", regex=False))]
    assert failures.empty


def test_report_diagnostics_keep_nav_and_monthly_consistency() -> None:
    consistency = build_report_consistency_check()
    failed = consistency[consistency["status"] == "FAIL"]
    assert failed.empty
    monthly = pd.read_csv(resolve_path("reports/backtest/attribution/combined_v2_monthly_returns.csv"))
    assert abs(float(monthly["diff"].iloc[-1])) < 1e-8
    daily = pd.read_csv(resolve_path("reports/backtest/attribution/combined_v2_daily_regime_attribution.csv"))
    execution = pd.read_csv(resolve_path("reports/backtest/audit/execution_mode_compare.csv"))
    row = execution[(execution["profile"] == "combined_v2") & (execution["execution_mode"] == "next_bar")].iloc[0]
    manifest = load_yaml("reports/backtest/release/combined_v2_rc_manifest.json")
    expected_pnl = float(manifest["initial_capital"]) * float(row["cumulative_return"])
    assert abs(float(daily["daily_pnl"].sum()) - expected_pnl) < 1e-6
