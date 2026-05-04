#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import timedelta
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.config import load_yaml_optional, resolve_path


A_SHARE_DEFAULT_CLOSED_DATES = {
    # 2026 Qingming and Labor Day exchange closures. These are observation
    # calendar controls, not strategy rules.
    "2026-04-06",
    "2026-05-01",
    "2026-05-04",
    "2026-05-05",
    "2026-05-09",
}


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


def _date_frame_from_parquet(path_like: str | Path, date_columns: tuple[str, ...] = ("date", "trade_date")) -> pd.DataFrame:
    path = resolve_path(path_like)
    if not path.exists():
        return pd.DataFrame(columns=["date"])
    if path.is_dir():
        frames = [_date_frame_from_parquet(child, date_columns) for child in path.glob("*.parquet")]
        frames = [frame for frame in frames if not frame.empty]
        return pd.concat(frames, ignore_index=True).drop_duplicates().sort_values("date") if frames else pd.DataFrame(columns=["date"])
    try:
        frame = pd.read_parquet(path, columns=list(date_columns))
    except Exception:
        try:
            frame = pd.read_parquet(path)
        except Exception:
            return pd.DataFrame(columns=["date"])
    for column in date_columns:
        if column in frame.columns:
            dates = pd.to_datetime(frame[column], errors="coerce").dropna().dt.normalize()
            if not dates.empty:
                return pd.DataFrame({"date": dates.drop_duplicates().sort_values().dt.strftime("%Y-%m-%d")})
    return pd.DataFrame(columns=["date"])


def _feature_max_date() -> tuple[pd.Timestamp | None, str]:
    snapshot = resolve_path("data/features/latest_feature_snapshot.parquet")
    if snapshot.exists():
        date = _max_date_from_parquet(snapshot)
        if date is not None:
            return date, "data/features/latest_feature_snapshot.parquet"
    daily_dir = resolve_path("data/features/daily_features")
    date = _max_date_from_parquet(daily_dir)
    return date, "data/features/daily_features"


def _feature_dates() -> tuple[pd.Series, str]:
    snapshot = resolve_path("data/features/latest_feature_snapshot.parquet")
    if snapshot.exists():
        frame = _date_frame_from_parquet(snapshot)
        if not frame.empty:
            return pd.to_datetime(frame["date"], errors="coerce").dropna().dt.normalize(), "data/features/latest_feature_snapshot.parquet"
    daily_dir = resolve_path("data/features/daily_features")
    frame = _date_frame_from_parquet(daily_dir)
    return pd.to_datetime(frame["date"], errors="coerce").dropna().dt.normalize(), "data/features/daily_features"


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


def _closed_dates(obs_cfg: dict, market: str) -> set[pd.Timestamp]:
    configured = set(str(item) for item in obs_cfg.get("a_share_known_closed_dates", []) or [])
    if market == "A_SHARE":
        configured |= A_SHARE_DEFAULT_CLOSED_DATES
    dates = {_parse_date(item) for item in configured}
    return {date for date in dates if date is not None}


def _calendar_dates(obs_cfg: dict) -> tuple[pd.Series, str]:
    preferred = str(obs_cfg.get("trading_calendar_source", "auto"))
    calendar_path = resolve_path("data/curated/trade_calendar.parquet")
    if preferred in {"auto", "project", "project_trade_calendar"} and calendar_path.exists():
        frame = _date_frame_from_parquet(calendar_path)
        dates = pd.to_datetime(frame["date"], errors="coerce").dropna().dt.normalize()
        if not dates.empty:
            return dates.drop_duplicates().sort_values(), "project_trade_calendar"
    if preferred in {"auto", "benchmark", "inferred_from_benchmark"}:
        frame = _date_frame_from_parquet("data/raw/benchmark_daily.parquet")
        dates = pd.to_datetime(frame["date"], errors="coerce").dropna().dt.normalize()
        if not dates.empty:
            return dates.drop_duplicates().sort_values(), "inferred_from_benchmark"
    if preferred in {"auto", "features", "inferred_from_features"}:
        dates, source = _feature_dates()
        if not dates.empty:
            return dates.drop_duplicates().sort_values(), "inferred_from_features" if "features" in source else source
    return pd.Series(dtype="datetime64[ns]"), "unresolved"


def _extend_calendar_dates(dates: pd.Series, requested: pd.Timestamp, closed: set[pd.Timestamp]) -> tuple[pd.Series, bool]:
    if dates.empty:
        return dates, False
    normalized = pd.to_datetime(dates, errors="coerce").dropna().dt.normalize().drop_duplicates().sort_values()
    max_date = normalized.max()
    if requested <= max_date:
        return normalized, False
    additions: list[pd.Timestamp] = []
    current = max_date + timedelta(days=1)
    while current <= requested:
        if current.weekday() < 5 and current.normalize() not in closed:
            additions.append(current.normalize())
        current += timedelta(days=1)
    if additions:
        normalized = pd.concat([normalized, pd.Series(additions)], ignore_index=True).drop_duplicates().sort_values()
    return normalized, bool(additions)


def resolve_target_trading_date(
    as_of_date: str,
    market: str = "A_SHARE",
    observation_config: dict | None = None,
    target_trading_date: str | None = None,
) -> dict:
    obs_cfg = observation_config or {}
    requested = _parse_date(as_of_date)
    if requested is None:
        raise ValueError(f"invalid as_of_date: {as_of_date}")
    dates, source = _calendar_dates(obs_cfg)
    closed = _closed_dates(obs_cfg, market)
    dates, extended = _extend_calendar_dates(dates, requested, closed)
    if extended:
        source = f"{source}+a_share_weekday_holiday_overrides"
    if dates.empty:
        return {
            "requested_as_of_date": _date_str(requested),
            "requested_as_of_is_trading_day": False,
            "target_trading_date": "",
            "calendar_source": source,
            "calendar_min_date": "",
            "calendar_max_date": "",
            "calendar_market": market,
        }
    dates = pd.to_datetime(dates, errors="coerce").dropna().dt.normalize().drop_duplicates().sort_values()
    requested_is_trading = bool((dates == requested).any())
    if target_trading_date:
        target = _parse_date(target_trading_date)
        if target is None:
            raise ValueError(f"invalid target_trading_date: {target_trading_date}")
        target_is_trading = bool((dates == target).any())
    else:
        eligible = dates[dates <= requested]
        target = eligible.max() if not eligible.empty else None
        target_is_trading = target is not None
    return {
        "requested_as_of_date": _date_str(requested),
        "requested_as_of_is_trading_day": requested_is_trading,
        "target_trading_date": _date_str(target),
        "target_trading_date_is_valid": bool(target_is_trading),
        "calendar_source": source,
        "calendar_min_date": _date_str(dates.min()),
        "calendar_max_date": _date_str(dates.max()),
        "calendar_market": market,
    }


def trading_dates_between(
    start_exclusive: str | pd.Timestamp | None,
    end_inclusive: str | pd.Timestamp | None,
    market: str = "A_SHARE",
    observation_config: dict | None = None,
) -> list[str]:
    start = _parse_date(start_exclusive)
    end = _parse_date(end_inclusive)
    if start is None or end is None:
        return []
    obs_cfg = observation_config or {}
    dates, _source = _calendar_dates(obs_cfg)
    dates, _extended = _extend_calendar_dates(dates, end, _closed_dates(obs_cfg, market))
    if dates.empty:
        return []
    dates = pd.to_datetime(dates, errors="coerce").dropna().dt.normalize().drop_duplicates().sort_values()
    window = dates[(dates > start) & (dates <= end)]
    return [_date_str(date) for date in window]


def build_data_freshness_report(
    as_of_date: str,
    max_stale_calendar_days: int | None = None,
    max_stale_trading_days: int | None = None,
    target_trading_date: str | None = None,
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
    max_stale_trading = int(
        max_stale_trading_days
        if max_stale_trading_days is not None
        else obs_cfg.get("max_stale_trading_days_for_daily_report", 0)
    )
    require_target_ge = bool(obs_cfg.get("require_data_max_date_ge_target_trading_date", obs_cfg.get("require_data_max_date_ge_as_of_date", True)))
    market = str(obs_cfg.get("calendar_market", "A_SHARE"))
    target_info = resolve_target_trading_date(
        as_of_date,
        market=market,
        observation_config=obs_cfg,
        target_trading_date=target_trading_date,
    )
    target_date = _parse_date(target_info.get("target_trading_date"))

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
    if target_date is None:
        blocking.append("TARGET_TRADING_DATE_UNRESOLVED")
    elif not bool(target_info.get("target_trading_date_is_valid", bool(target_info.get("target_trading_date")))):
        blocking.append("TARGET_TRADING_DATE_UNRESOLVED")
    if data_max_date is None:
        blocking.append("MISSING_DATA_MAX_DATE")
    elif require_target_ge and target_date is not None and data_max_date < target_date:
        blocking.append("DATA_MAX_DATE_BEFORE_TARGET_TRADING_DATE")
    if feature_date is not None and require_target_ge and target_date is not None and feature_date < target_date:
        blocking.append("FEATURE_MAX_DATE_BEFORE_TARGET_TRADING_DATE")
    if benchmark_date is not None and require_target_ge and target_date is not None and benchmark_date < target_date:
        blocking.append("BENCHMARK_MAX_DATE_BEFORE_TARGET_TRADING_DATE")
    stale_days = None if data_max_date is None else int((requested - data_max_date).days)
    gap_trading_dates = trading_dates_between(data_max_date, target_date, market=market, observation_config=obs_cfg)
    stale_trading_days = None if data_max_date is None or target_date is None else len(gap_trading_dates)
    if stale_days is not None and stale_days > max_stale:
        blocking.append("STALE_CALENDAR_DAYS_EXCEED_LIMIT")
    if stale_trading_days is not None and stale_trading_days > max_stale_trading:
        blocking.append("STALE_TRADING_DAYS_EXCEED_LIMIT")

    is_current = not blocking
    allowed = "observation_report_allowed" if is_current else "historical_review_only"
    report = {
        **target_info,
        "data_max_date": _date_str(data_max_date),
        "feature_max_date": _date_str(feature_date),
        "feature_source": feature_source,
        "benchmark_max_date": _date_str(benchmark_date),
        "universe_max_effective_date": _date_str(universe_date),
        "provider_health_date": _date_str(provider_date),
        "data_quality_date": _date_str(quality_date),
        "rc_manifest_data_max_date": _date_str(manifest_data_date),
        "stale_calendar_days": stale_days,
        "stale_trading_days": stale_trading_days,
        "missing_trading_dates": gap_trading_dates,
        "max_stale_calendar_days": max_stale,
        "max_stale_trading_days": max_stale_trading,
        "require_data_max_date_ge_target_trading_date": require_target_ge,
        "is_data_current_for_target_trading_date": is_current,
        "is_data_current": is_current,
        "blocking_reason": "NONE" if is_current else "|".join(dict.fromkeys(blocking)),
        "warnings": warnings,
        "allowed_actions": allowed,
        "market_closed_as_of_date": not bool(target_info.get("requested_as_of_is_trading_day")),
        "non_trading_day_action": obs_cfg.get("non_trading_day_action", "OBSERVATION_ONLY_NEXT_TRADING_DAY_REVIEW")
        if not bool(target_info.get("requested_as_of_is_trading_day"))
        else "",
    }
    if write_report:
        base = resolve_path(output_dir or Path(str(manual_cfg.get("observation_report_dir", "reports/observation"))) / _date_str(requested))
        base.mkdir(parents=True, exist_ok=True)
        (base / "data_freshness_report.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines = [
            "# 数据新鲜度检查",
            "",
            f"- requested_as_of_date: {report['requested_as_of_date']}",
            f"- requested_as_of_is_trading_day: {str(report['requested_as_of_is_trading_day']).lower()}",
            f"- target_trading_date: {report['target_trading_date'] or '无法解析'}",
            f"- calendar_source: {report['calendar_source']}",
            f"- data_max_date: {report['data_max_date']}",
            f"- feature_max_date: {report['feature_max_date']}",
            f"- benchmark_max_date: {report['benchmark_max_date']}",
            f"- universe_max_effective_date: {report['universe_max_effective_date']}",
            f"- provider_health_date: {report['provider_health_date'] or '缺失'}",
            f"- data_quality_date: {report['data_quality_date'] or '缺失'}",
            f"- stale_calendar_days: {report['stale_calendar_days']}",
            f"- stale_trading_days: {report['stale_trading_days']}",
            f"- require_data_max_date_ge_target_trading_date: {str(report['require_data_max_date_ge_target_trading_date']).lower()}",
            f"- is_data_current_for_target_trading_date: {str(report['is_data_current_for_target_trading_date']).lower()}",
            f"- blocking_reason: {report['blocking_reason']}",
            f"- allowed_actions: {report['allowed_actions']}",
            "",
        ]
        if is_current:
            lines.append("数据新鲜度允许生成观察报告，但仍禁止自动下单。")
            if report["market_closed_as_of_date"]:
                lines.append("MARKET_CLOSED_AS_OF_DATE：仅允许为下一交易日进行人工复盘，不得写成当日实盘执行。")
        else:
            lines.append("STALE_DATA_BLOCKED：只能历史复盘，不允许生成实盘观察日报或手工订单清单。")
        if gap_trading_dates:
            lines.extend(["", "## 缺口交易日", ""])
            lines.extend([f"- {date}" for date in gap_trading_dates])
        if warnings:
            lines.extend(["", "## WARN", ""])
            lines.extend([f"- {warning}" for warning in warnings])
        (base / "data_freshness_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check whether local data are fresh enough for observation daily reports.")
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--target-trading-date", default="")
    parser.add_argument("--max-stale-calendar-days", type=int, default=None)
    parser.add_argument("--max-stale-trading-days", type=int, default=None)
    parser.add_argument("--write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    build_data_freshness_report(
        args.as_of_date,
        args.max_stale_calendar_days,
        args.max_stale_trading_days,
        target_trading_date=args.target_trading_date or None,
        write_report=args.write_report,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
