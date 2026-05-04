#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_data_freshness import _json_optional, _parse_date, _date_str, resolve_target_trading_date
from src.utils.config import load_yaml_optional, resolve_path


OUTPUT_JSON = "data_quality_observation_report.json"
OUTPUT_MD = "data_quality_observation_report.md"
CORE_FIELD_MAP = {
    "close": "close",
    "ma20": "ma20",
    "ma60": "ma60",
    "ma120": "ma120",
    "ma200": "ma200",
    "ma250": "ma250",
    "atr20": "atr20",
    "pb": "stock_pb",
    "pe_ttm": "stock_pe_ttm",
    "roe": "roe",
    "cfo_ttm": "cfo_ttm",
    "net_profit_ttm": "net_profit_ttm_effective",
    "dividend_yield_ttm": "dv_ttm",
}
STOCK_VALUATION_SOURCE_FIELDS = ["stock_pb_q_blended", "stock_pe_ttm_q_blended"]
INDUSTRY_VALUATION_SOURCE_FIELDS = ["industry_pb_q_blended", "industry_pe_ttm_q_blended"]


def _read_parquet_optional(path_like: str | Path) -> pd.DataFrame:
    path = resolve_path(path_like)
    if not path.exists():
        return pd.DataFrame()
    if path.is_dir():
        frames = []
        for child in path.glob("*.parquet"):
            try:
                frames.append(pd.read_parquet(child))
            except Exception:
                continue
        return pd.concat(frames, ignore_index=True, sort=False) if frames else pd.DataFrame()
    try:
        return pd.read_parquet(path)
    except Exception:
        return pd.DataFrame()


def _repo_relative(path_like: str | Path) -> str:
    path = resolve_path(path_like)
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _feature_frame_on_date(target_date: str) -> pd.DataFrame:
    year_path = resolve_path(f"data/features/daily_features/{pd.Timestamp(target_date).year}.parquet")
    frame = _read_parquet_optional(year_path if year_path.exists() else "data/features/daily_features")
    if frame.empty or "date" not in frame.columns:
        return pd.DataFrame()
    return frame[frame["date"].astype(str) == target_date].copy()


def _benchmark_frame() -> pd.DataFrame:
    frame = _read_parquet_optional("data/raw/benchmark_daily.parquet")
    if not frame.empty and "date" in frame.columns:
        frame = frame.copy()
        frame["date"] = pd.to_datetime(frame["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        frame = frame.sort_values("date").reset_index(drop=True)
    return frame


def _latest_universe_file(target_date: str) -> str:
    candidates: list[Path] = []
    for directory in ("data/curated/universe_history", "reports/backtest/combined_v2_universe_history"):
        path = resolve_path(directory)
        if not path.exists():
            continue
        for child in path.glob("*.json"):
            date = _parse_date(child.stem)
            target = _parse_date(target_date)
            if date is not None and target is not None and date <= target:
                candidates.append(child)
    if not candidates:
        return ""
    return _repo_relative(max(candidates, key=lambda item: item.stem))


def _row(rows: list[dict], check_id: str, check_name: str, status: str, expected: object, actual: object, evidence: str, recommendation: str) -> None:
    rows.append(
        {
            "check_id": check_id,
            "check_name": check_name,
            "status": status,
            "expected": expected,
            "actual": actual,
            "evidence": evidence,
            "recommendation": recommendation,
        }
    )


def build_data_quality_observation_report(
    as_of_date: str,
    target_trading_date: str | None = None,
    output_dir: str | Path | None = None,
    write_report: bool = False,
) -> dict:
    cfg = load_yaml_optional("config/observation.yml")
    obs_cfg = cfg.get("observation", {}) if isinstance(cfg, dict) else {}
    manual_cfg = cfg.get("manual_observation", {}) if isinstance(cfg, dict) else {}
    target_info = resolve_target_trading_date(
        as_of_date,
        market=str(obs_cfg.get("calendar_market", "A_SHARE")),
        observation_config=obs_cfg,
        target_trading_date=target_trading_date,
    )
    target = str(target_info.get("target_trading_date") or "")
    rows: list[dict] = []

    stock_list = _read_parquet_optional("data/raw/stock_list.parquet")
    total_count = int(len(stock_list)) if not stock_list.empty else 0
    active_count = total_count
    if not stock_list.empty and "name" in stock_list.columns:
        active_count = int((~stock_list["name"].astype(str).str.contains("退", na=False)).sum())
    _row(rows, "STOCK-001", "total_a_share_count", "PASS" if total_count > 0 else "FAIL", "> 0", total_count, "data/raw/stock_list.parquet", "缺少股票列表时不能生成观察报告。")
    _row(rows, "STOCK-002", "active_a_share_count", "PASS" if active_count > 0 else "FAIL", "> 0", active_count, "data/raw/stock_list.parquet", "缺少活跃 A 股范围时不能生成观察报告。")

    features = _feature_frame_on_date(target) if target else pd.DataFrame()
    unique_stocks = int(features["symbol"].nunique()) if not features.empty and "symbol" in features.columns else 0
    _row(rows, "FEATURE-001", "feature_rows_on_target_date", "PASS" if len(features) > 0 else "FAIL", "> 0", len(features), target, "目标交易日必须有特征行。")
    _row(rows, "FEATURE-002", "unique_stocks_on_target_date", "PASS" if unique_stocks > 0 else "FAIL", "> 0", unique_stocks, target, "目标交易日必须覆盖可交易股票。")

    core_missing: dict[str, float | None] = {}
    for public_name, column in CORE_FIELD_MAP.items():
        if features.empty or column not in features.columns:
            core_missing[public_name] = None
            status = "FAIL" if public_name in {"close", "pb"} else "WARN"
            actual = "missing_column"
        else:
            rate = float(features[column].isna().mean()) if len(features) else 1.0
            core_missing[public_name] = round(rate, 6)
            if public_name in {"close"}:
                status = "PASS" if rate == 0 else "FAIL"
            elif public_name == "pb":
                status = "PASS" if rate <= 0.2 else "FAIL"
            elif public_name == "pe_ttm":
                status = "PASS" if rate <= 0.2 else "WARN"
            else:
                status = "PASS" if rate <= 0.2 else "WARN"
            actual = round(rate, 6)
        _row(rows, f"CORE-{public_name}", f"{public_name} completeness", status, "missing_rate within rule", actual, column, "核心字段缺失超过规则时阻断或降级观察。")

    benchmark = _benchmark_frame()
    benchmark_row = benchmark[benchmark["date"].astype(str) == target].copy() if not benchmark.empty and target else pd.DataFrame()
    benchmark_exists = not benchmark_row.empty
    _row(rows, "BENCH-001", "benchmark row exists on target_trading_date", "PASS" if benchmark_exists else "FAIL", "exists", benchmark_exists, target, "目标交易日必须有 benchmark 行。")
    if benchmark.empty or "close" not in benchmark.columns or not target:
        ma60_available = False
        ma200_available = False
    else:
        benchmark = benchmark.copy()
        benchmark["close"] = pd.to_numeric(benchmark["close"], errors="coerce")
        benchmark["ma60"] = benchmark["close"].rolling(60, min_periods=60).mean()
        benchmark["ma200"] = benchmark["close"].rolling(200, min_periods=200).mean()
        target_rows = benchmark[benchmark["date"].astype(str) == target]
        ma60_available = bool(not target_rows.empty and pd.notna(target_rows.iloc[-1].get("ma60")))
        ma200_available = bool(not target_rows.empty and pd.notna(target_rows.iloc[-1].get("ma200")))
    _row(rows, "BENCH-002", "benchmark ma60 available", "PASS" if ma60_available else "FAIL", "available", ma60_available, target, "benchmark ma60 缺失时 market regime 不可靠。")
    _row(rows, "BENCH-003", "benchmark ma200 available", "PASS" if ma200_available else "FAIL", "available", ma200_available, target, "benchmark ma200 缺失时 market regime 不可靠。")

    stock_fields_exist = all(column in features.columns for column in STOCK_VALUATION_SOURCE_FIELDS) if not features.empty else False
    industry_fields_exist = all(column in features.columns for column in INDUSTRY_VALUATION_SOURCE_FIELDS) if not features.empty else False
    _row(rows, "VAL-001", "stock valuation source fields exist", "PASS" if stock_fields_exist else "FAIL", STOCK_VALUATION_SOURCE_FIELDS, stock_fields_exist, target, "估值 resolver 需要 stock source fields。")
    _row(rows, "VAL-002", "industry valuation source fields exist", "PASS" if industry_fields_exist else "FAIL", INDUSTRY_VALUATION_SOURCE_FIELDS, industry_fields_exist, target, "估值 resolver 需要 industry source fields。")

    universe_file = _latest_universe_file(target)
    _row(rows, "UNIVERSE-001", "effective universe available for target_trading_date", "PASS" if universe_file else "FAIL", "available", universe_file or "missing", target, "目标交易日必须能找到有效股票池。")

    provider = _json_optional("provider_health/latest.json")
    provider_date = str(provider.get("as_of_date", ""))
    provider_failures = [
        entry
        for entry in provider.get("providers", [])
        if isinstance(entry, dict) and str(entry.get("success", "")).lower() == "false"
    ]
    _row(rows, "PROVIDER-001", "latest provider health date", "PASS" if provider_date else "WARN", "present", provider_date or "missing", "provider_health/latest.json", "provider health 缺失时降级为 WARN 并显式记录。")
    _row(rows, "PROVIDER-002", "provider failures", "PASS" if not provider_failures else "WARN", "0", len(provider_failures), "provider_health/latest.json", "存在 provider 失败时继续人工审阅数据质量。")

    frame = pd.DataFrame(rows)
    if (frame["status"] == "FAIL").any():
        overall = "FAIL"
    elif (frame["status"] == "WARN").any():
        overall = "WARN"
    else:
        overall = "PASS"
    report = {
        **target_info,
        "status": overall,
        "total_a_share_count": total_count,
        "active_a_share_count": active_count,
        "feature_rows_on_target_date": int(len(features)),
        "unique_stocks_on_target_date": unique_stocks,
        "core_field_missing_rates": core_missing,
        "benchmark_row_exists_on_target_trading_date": benchmark_exists,
        "benchmark_ma60_available": ma60_available,
        "benchmark_ma200_available": ma200_available,
        "stock_valuation_source_fields_exist": stock_fields_exist,
        "industry_valuation_source_fields_exist": industry_fields_exist,
        "effective_universe_file": universe_file,
        "provider_health_date": provider_date,
        "provider_failure_count": len(provider_failures),
        "checks": frame.to_dict(orient="records"),
    }
    if write_report:
        base = resolve_path(output_dir or Path(str(manual_cfg.get("observation_report_dir", "reports/observation"))) / str(as_of_date))
        base.mkdir(parents=True, exist_ok=True)
        (base / OUTPUT_JSON).write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines = [
            "# 观察期数据质量检查",
            "",
            f"- status: {overall}",
            f"- requested_as_of_date: {report['requested_as_of_date']}",
            f"- target_trading_date: {report['target_trading_date'] or '无法解析'}",
            f"- total_a_share_count: {total_count}",
            f"- active_a_share_count: {active_count}",
            f"- feature_rows_on_target_date: {len(features)}",
            f"- unique_stocks_on_target_date: {unique_stocks}",
            f"- benchmark_row_exists_on_target_trading_date: {benchmark_exists}",
            f"- effective_universe_file: {universe_file or '缺失'}",
            f"- provider_health_date: {provider_date or '缺失'}",
            "",
            "## checks",
            "",
        ]
        for row in frame.to_dict(orient="records"):
            lines.append(f"- {row['status']} | {row['check_id']} | {row['check_name']} | actual={row['actual']} | {row['recommendation']}")
        (base / OUTPUT_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check data quality required by the observation pipeline.")
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--target-trading-date", default="")
    parser.add_argument("--write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_data_quality_observation_report(
        args.as_of_date,
        target_trading_date=args.target_trading_date or None,
        write_report=args.write_report,
    )
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
