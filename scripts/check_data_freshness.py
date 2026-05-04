#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.config import load_yaml_optional, resolve_path


def _parse_date(value: object) -> pd.Timestamp | None:
    if value is None or value == "":
        return None
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return None
    return pd.Timestamp(ts).normalize()


def _date_str(ts: pd.Timestamp | None) -> str:
    return "" if ts is None else ts.strftime("%Y-%m-%d")


def _json_optional(path_like: str | Path) -> dict:
    path = resolve_path(path_like)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _max_date_from_parquet(path_like: str | Path, date_columns: tuple[str, ...] = ("date", "trade_date")) -> pd.Timestamp | None:
    path = resolve_path(path_like)
    if not path.exists():
        return None
    if path.is_dir():
        max_dates = [_max_date_from_parquet(child, date_columns) for child in path.glob("*.parquet")]
        valid = [date for date in max_dates if date is not None]
        return max(valid) if valid else None
    try:
        frame = pd.read_parquet(path)
    except Exception:
        return None
    for column in date_columns:
        if column in frame.columns:
            dates = pd.to_datetime(frame[column], errors="coerce").dropna()
            if not dates.empty:
                return pd.Timestamp(dates.max()).normalize()
    return None


def _feature_max_date() -> tuple[pd.Timestamp | None, str]:
    snapshot = resolve_path("data/features/latest_feature_snapshot.parquet")
    if snapshot.exists():
        date = _max_date_from_parquet(snapshot)
        if date is not None:
            return date, "data/features/latest_feature_snapshot.parquet"
    daily_dir = resolve_path("data/features/daily_features")
    date = _max_date_from_parquet(daily_dir)
    return date, "data/features/daily_features"


def _universe_max_effective_date() -> pd.Timestamp | None:
    candidates: list[pd.Timestamp] = []
    for directory in ("data/curated/universe_history", "reports/backtest/combined_v2_universe_history"):
        path = resolve_path(directory)
        if not path.exists():
            continue
        for file_path in path.glob("*.json"):
            date = _parse_date(file_path.stem)
            if date is not None:
                candidates.append(date)
    return max(candidates) if candidates else None


def _provider_date(payload: dict) -> pd.Timestamp | None:
    return _parse_date(payload.get("as_of_date") or payload.get("current_date") or payload.get("target_trading_date"))


def build_data_freshness_report(
    as_of_date: str,
    max_stale_calendar_days: int | None = None,
    output_dir: str | Path | None = None,
    write_report: bool = False,
) -> dict:
    observation = load_yaml_optional("config/observation.yml")
    obs_cfg = observation.get("observation", {}) if isinstance(observation, dict) else {}
    manual_cfg = observation.get("manual_observation", {}) if isinstance(observation, dict) else {}
    requested = _parse_date(as_of_date)
    if requested is None:
        raise ValueError(f"invalid --as-of-date: {as_of_date}")
    max_stale = int(max_stale_calendar_days if max_stale_calendar_days is not None else obs_cfg.get("max_stale_calendar_days_for_daily_report", 3))
    require_data_ge = bool(obs_cfg.get("require_data_max_date_ge_as_of_date", True))

    feature_date, feature_source = _feature_max_date()
    benchmark_date = _max_date_from_parquet("data/raw/benchmark_daily.parquet")
    universe_date = _universe_max_effective_date()
    provider_payload = _json_optional("provider_health/latest.json")
    quality_payload = _json_optional("data_quality/latest.json")
    provider_date = _provider_date(provider_payload)
    quality_date = _provider_date(quality_payload)
    manifest = _json_optional("reports/backtest/release/combined_v2_rc_manifest.json")
    manifest_data_date = _parse_date(manifest.get("data_max_date"))

    critical_dates = [date for date in (feature_date, benchmark_date) if date is not None]
    data_max_date = min(critical_dates) if critical_dates else manifest_data_date
    blocking: list[str] = []
    warnings: list[str] = []
    if feature_date is None:
        blocking.append("MISSING_FEATURE_SNAPSHOT")
    if benchmark_date is None:
        blocking.append("MISSING_BENCHMARK")
    if provider_date is None:
        warnings.append("MISSING_PROVIDER_HEALTH")
    if quality_date is None:
        warnings.append("MISSING_DATA_QUALITY")
    if data_max_date is None:
        blocking.append("MISSING_DATA_MAX_DATE")
    elif require_data_ge and data_max_date < requested:
        blocking.append("DATA_MAX_DATE_BEFORE_AS_OF_DATE")
    stale_days = None if data_max_date is None else int((requested - data_max_date).days)
    if stale_days is not None and stale_days > max_stale:
        blocking.append("STALE_CALENDAR_DAYS_EXCEED_LIMIT")

    is_current = not blocking
    allowed = "observation_report_allowed" if is_current else "historical_review_only"
    report = {
        "requested_as_of_date": _date_str(requested),
        "data_max_date": _date_str(data_max_date),
        "feature_max_date": _date_str(feature_date),
        "feature_source": feature_source,
        "benchmark_max_date": _date_str(benchmark_date),
        "universe_max_effective_date": _date_str(universe_date),
        "provider_health_date": _date_str(provider_date),
        "data_quality_date": _date_str(quality_date),
        "rc_manifest_data_max_date": _date_str(manifest_data_date),
        "stale_calendar_days": stale_days,
        "max_stale_calendar_days": max_stale,
        "is_data_current": is_current,
        "blocking_reason": "NONE" if is_current else "|".join(dict.fromkeys(blocking)),
        "warnings": warnings,
        "allowed_actions": allowed,
    }
    if write_report:
        base = resolve_path(output_dir or Path(str(manual_cfg.get("observation_report_dir", "reports/observation"))) / _date_str(requested))
        base.mkdir(parents=True, exist_ok=True)
        (base / "data_freshness_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines = [
            "# 数据新鲜度检查",
            "",
            f"- requested_as_of_date: {report['requested_as_of_date']}",
            f"- data_max_date: {report['data_max_date']}",
            f"- feature_max_date: {report['feature_max_date']}",
            f"- benchmark_max_date: {report['benchmark_max_date']}",
            f"- universe_max_effective_date: {report['universe_max_effective_date']}",
            f"- provider_health_date: {report['provider_health_date'] or '缺失'}",
            f"- data_quality_date: {report['data_quality_date'] or '缺失'}",
            f"- stale_calendar_days: {report['stale_calendar_days']}",
            f"- is_data_current: {report['is_data_current']}",
            f"- blocking_reason: {report['blocking_reason']}",
            f"- allowed_actions: {report['allowed_actions']}",
            "",
        ]
        if is_current:
            lines.append("数据新鲜度允许生成观察报告，但仍禁止自动下单。")
        else:
            lines.append("STALE_DATA_BLOCKED：只能历史复盘，不允许生成当日实盘观察日报或手工订单清单。")
        if warnings:
            lines.extend(["", "## WARN", ""])
            lines.extend([f"- {warning}" for warning in warnings])
        (base / "data_freshness_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether local data are fresh enough for observation daily reports.")
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--max-stale-calendar-days", type=int, default=None)
    parser.add_argument("--write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    build_data_freshness_report(args.as_of_date, args.max_stale_calendar_days, write_report=args.write_report)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
