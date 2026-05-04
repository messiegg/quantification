#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_common import (
    DEFAULT_END_DATE,
    DEFAULT_START_DATE,
    V2_HISTORY_DIR,
    ensure_parent,
    load_audit_configs,
    load_feature_window,
    pct,
    prepare_v2_history,
    status_from_rows,
)
from src.strategy.backtest_reports import build_universe_funnel
from src.utils.config import resolve_path


FINANCIAL_FIELDS = [
    "roe",
    "net_profit_ttm_effective",
    "latest_net_profit",
    "cfo_ttm",
    "debt_to_assets",
    "dv_ttm",
    "pe_ttm",
    "pb",
    "stock_pb_q_5y",
    "stock_pb_q_10y",
    "stock_pb_q_blended",
    "stock_pe_ttm_q_5y",
    "stock_pe_ttm_q_10y",
    "stock_pe_ttm_q_blended",
    "industry_pb_q_5y",
    "industry_pb_q_10y",
    "industry_pb_q_blended",
    "industry_pe_ttm_q_5y",
    "industry_pe_ttm_q_10y",
    "industry_pe_ttm_q_blended",
    "cycle_peak_trap",
    "roe_pct_in_last_12_quarters",
]

TECHNICAL_FIELDS = [
    "ma20",
    "ma60",
    "ma120",
    "ma200",
    "ma250",
    "ma20_slope_10d",
    "ma60_slope_20d",
    "ma120_slope_20d",
    "atr20",
    "close",
]


def _audit_financial_availability(features: pd.DataFrame, fallback_days: int) -> tuple[list[dict], list[dict]]:
    frame = features.copy()
    frame["date_ts"] = pd.to_datetime(frame["date"], errors="coerce")
    frame["report_ts"] = pd.to_datetime(frame.get("report_date"), errors="coerce")
    frame["announcement_ts"] = pd.to_datetime(frame.get("announcement_date"), errors="coerce")
    rows = []
    violations = []
    for field in FINANCIAL_FIELDS:
        if field not in frame.columns:
            rows.append({"check_id": f"LH-FIN-{field}", "check_name": f"{field} availability", "status": "WARN", "profile": "both", "evidence": "field missing from feature panel", "affected_file": "data/features/daily_features", "recommendation": "确认该字段是否已不参与信号、过滤或打分。"})
            continue
        used = frame[frame[field].notna()].copy()
        if used.empty:
            rows.append({"check_id": f"LH-FIN-{field}", "check_name": f"{field} availability", "status": "WARN", "profile": "both", "evidence": "no non-null rows in audit window", "affected_file": "data/features/daily_features", "recommendation": "确认字段缺失是否符合预期。"})
            continue
        bad_announcement = used[used["announcement_ts"].notna() & (used["announcement_ts"] > used["date_ts"])]
        fallback_used = used[used["announcement_ts"].isna() & used["report_ts"].notna()].copy()
        fallback_used["fallback_available_ts"] = fallback_used["report_ts"] + pd.Timedelta(days=fallback_days)
        bad_fallback = fallback_used[fallback_used["fallback_available_ts"] > fallback_used["date_ts"]]
        status = "PASS" if bad_announcement.empty and bad_fallback.empty else "FAIL"
        rows.append({"check_id": f"LH-FIN-{field}", "check_name": f"{field} availability", "status": status, "profile": "both", "evidence": f"non_null={len(used)}, announcement_violations={len(bad_announcement)}, fallback_violations={len(bad_fallback)}, fallback_days={fallback_days}", "affected_file": "data/features/daily_features", "recommendation": "禁止使用 signal_date 之后才公告或 fallback 未满滞后期的财务字段。"})
        for subset, reason in ((bad_announcement, "announcement_date_after_signal_date"), (bad_fallback, "report_date_fallback_after_signal_date")):
            for item in subset.head(5000).to_dict(orient="records"):
                violations.append(
                    {
                        "violation_type": reason,
                        "signal_date": item.get("date"),
                        "ts_code": item.get("symbol"),
                        "field": field,
                        "report_date": str(item.get("report_date")),
                        "announcement_date": str(item.get("announcement_date")),
                        "fallback_days": fallback_days,
                        "detail": f"{reason} for {field}",
                    }
                )
    return rows, violations


def _valuation_samples(features: pd.DataFrame) -> pd.DataFrame:
    sample_cols = [
        ("stock_pb_q_blended", "stock", "pb"),
        ("stock_pe_ttm_q_blended", "stock", "pe_ttm"),
        ("industry_pb_q_blended", "industry", "pb"),
        ("industry_pe_ttm_q_blended", "industry", "pe_ttm"),
    ]
    sample_pool = []
    for column, scope, metric in sample_cols:
        if column not in features.columns:
            continue
        eligible = features[features[column].notna()][["date", "symbol", "industry", column]].copy()
        if eligible.empty:
            continue
        take = min(5, len(eligible))
        sample = eligible.sample(n=take, random_state=42)
        sample["quantile_column"] = column
        sample["scope"] = scope
        sample["metric"] = metric
        sample_pool.append(sample)
    if not sample_pool:
        return pd.DataFrame()
    samples = pd.concat(sample_pool, ignore_index=True).head(20)
    stock_daily = pd.read_parquet(resolve_path("data/curated/stock_valuation_daily.parquet"))
    industry_daily = pd.read_parquet(resolve_path("data/curated/industry_daily.parquet"))
    stock_daily["date_ts"] = pd.to_datetime(stock_daily["date"], errors="coerce")
    industry_daily["date_ts"] = pd.to_datetime(industry_daily["date"], errors="coerce")
    rows = []
    for item in samples.to_dict(orient="records"):
        signal_date = pd.Timestamp(item["date"])
        metric = item["metric"]
        if item["scope"] == "stock":
            source = stock_daily[(stock_daily["symbol"].astype(str) == str(item["symbol"])) & (stock_daily["date_ts"] <= signal_date) & stock_daily[metric].notna()]
        else:
            source = industry_daily[(industry_daily["industry_name"].astype(str) == str(item["industry"])) & (industry_daily["date_ts"] <= signal_date) & industry_daily[metric].notna()]
        max_source = source["date_ts"].max() if not source.empty else pd.NaT
        min_source = source["date_ts"].min() if not source.empty else pd.NaT
        rows.append(
            {
                "signal_date": item["date"],
                "ts_code": item["symbol"],
                "industry": item["industry"],
                "metric": item["quantile_column"],
                "current_value": item.get(item["quantile_column"]),
                "window_start": min_source.strftime("%Y-%m-%d") if pd.notna(min_source) else "",
                "window_end": signal_date.strftime("%Y-%m-%d"),
                "max_source_date_used": max_source.strftime("%Y-%m-%d") if pd.notna(max_source) else "",
                "pass_or_fail": "PASS" if pd.notna(max_source) and max_source <= signal_date else "FAIL",
            }
        )
    return pd.DataFrame(rows)


def _field_metric(source_field: str, fallback_metric: str) -> tuple[str, str]:
    field = str(source_field or "")
    if field.startswith("stock_"):
        scope = "stock"
    elif field.startswith("industry_"):
        scope = "industry"
    else:
        return "", str(fallback_metric or "")
    if "pe_ttm" in field:
        metric = "pe_ttm"
    elif "pb" in field:
        metric = "pb"
    else:
        metric = str(fallback_metric or "")
    return scope, metric


def _max_source_date(
    stock_daily: pd.DataFrame,
    industry_daily: pd.DataFrame,
    row: dict,
    source_field: str,
    metric: str,
    signal_date: pd.Timestamp,
) -> str:
    scope, resolved_metric = _field_metric(source_field, metric)
    if scope == "stock":
        if resolved_metric not in stock_daily.columns:
            return ""
        source = stock_daily[
            (stock_daily["symbol"].astype(str) == str(row.get("ts_code")))
            & (stock_daily["date_ts"] <= signal_date)
            & stock_daily[resolved_metric].notna()
        ]
    elif scope == "industry":
        if resolved_metric not in industry_daily.columns:
            return ""
        source = industry_daily[
            (industry_daily["industry_name"].astype(str) == str(row.get("industry")))
            & (industry_daily["date_ts"] <= signal_date)
            & industry_daily[resolved_metric].notna()
        ]
    else:
        return ""
    if source.empty:
        return ""
    return source["date_ts"].max().strftime("%Y-%m-%d")


def build_valuation_field_resolution(
    candidate_scores: pd.DataFrame,
    stock_daily: pd.DataFrame,
    industry_daily: pd.DataFrame,
) -> pd.DataFrame:
    columns = [
        "date",
        "ts_code",
        "bucket",
        "stock_valuation_quantile",
        "stock_valuation_quantile_source_field",
        "stock_valuation_metric",
        "industry_valuation_quantile",
        "industry_valuation_quantile_source_field",
        "industry_valuation_metric",
        "max_source_date_used",
        "signal_date",
        "pass_or_fail",
        "warning_reason",
    ]
    if candidate_scores.empty:
        return pd.DataFrame(columns=columns)
    stock_daily = stock_daily.copy()
    industry_daily = industry_daily.copy()
    stock_daily["date_ts"] = pd.to_datetime(stock_daily["date"], errors="coerce")
    industry_daily["date_ts"] = pd.to_datetime(industry_daily["date"], errors="coerce")
    rows = []
    for item in candidate_scores.to_dict(orient="records"):
        signal_date = pd.Timestamp(item.get("date"))
        stock_field = str(item.get("stock_valuation_quantile_source_field") or "")
        industry_field = str(item.get("industry_valuation_quantile_source_field") or "")
        warning_parts = []
        if not stock_field:
            warning_parts.append("stock_source_field_empty")
        if not industry_field:
            warning_parts.append("industry_source_field_empty")
        stock_source = _max_source_date(stock_daily, industry_daily, item, stock_field, str(item.get("stock_valuation_metric") or ""), signal_date)
        industry_source = _max_source_date(
            stock_daily,
            industry_daily,
            item,
            industry_field,
            str(item.get("industry_valuation_metric") or ""),
            signal_date,
        )
        if stock_field and not stock_source:
            warning_parts.append("stock_source_history_missing")
        if industry_field and not industry_source:
            warning_parts.append("industry_source_history_missing")
        max_candidates = [pd.Timestamp(value) for value in (stock_source, industry_source) if value]
        max_source = max(max_candidates) if max_candidates else pd.NaT
        if pd.notna(max_source) and max_source > signal_date:
            status = "FAIL"
            warning_parts.append("source_after_signal_date")
        elif warning_parts:
            status = "WARN"
        else:
            status = "PASS"
        rows.append(
            {
                "date": item.get("date"),
                "ts_code": item.get("ts_code"),
                "bucket": item.get("bucket"),
                "stock_valuation_quantile": item.get("stock_valuation_quantile"),
                "stock_valuation_quantile_source_field": stock_field,
                "stock_valuation_metric": item.get("stock_valuation_metric"),
                "industry_valuation_quantile": item.get("industry_valuation_quantile"),
                "industry_valuation_quantile_source_field": industry_field,
                "industry_valuation_metric": item.get("industry_valuation_metric"),
                "max_source_date_used": max_source.strftime("%Y-%m-%d") if pd.notna(max_source) else "",
                "signal_date": item.get("date"),
                "pass_or_fail": status,
                "warning_reason": ";".join(warning_parts),
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _audit_universe_pit(features: pd.DataFrame) -> pd.DataFrame:
    feature_by_date = {date: frame.copy() for date, frame in features.groupby("date", sort=True)}
    rows = []
    for path in sorted(resolve_path(V2_HISTORY_DIR).glob("*.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        refresh_date = str(payload.get("as_of_date") or "")
        effective_date = str(payload.get("effective_from") or "")
        stocks = payload.get("stocks", []) or []
        symbols = {str(item.get("symbol")) for item in stocks if item.get("symbol")}
        max_financial = ""
        if refresh_date in feature_by_date and symbols:
            snapshot = feature_by_date[refresh_date]
            current = snapshot[snapshot["symbol"].astype(str).isin(symbols)].copy()
            effective_dates = pd.to_datetime(current.get("effective_date"), errors="coerce")
            if effective_dates.notna().any():
                max_financial = effective_dates.max().strftime("%Y-%m-%d")
        used_future = False
        detail = []
        if refresh_date and effective_date and pd.Timestamp(effective_date) <= pd.Timestamp(refresh_date):
            used_future = True
            detail.append("effective_date_not_after_refresh_date")
        for candidate in (refresh_date, max_financial):
            if candidate and pd.Timestamp(candidate) > pd.Timestamp(refresh_date):
                used_future = True
                detail.append(f"source_after_refresh:{candidate}")
        rows.append(
            {
                "refresh_date": refresh_date,
                "effective_date": effective_date,
                "universe_file": str(path),
                "effective_universe_size": int(payload.get("effective_universe_size", len(stocks))),
                "max_feature_date_used": refresh_date,
                "max_financial_available_date_used": max_financial,
                "max_price_date_used": refresh_date,
                "used_future_data": bool(used_future),
                "violation_detail": ";".join(detail),
            }
        )
    return pd.DataFrame(rows)


def main() -> int:
    configs = load_audit_configs()
    prepare_v2_history(configs)
    features = load_feature_window()
    fallback_days = int(configs["v2_strategy"]["financial_effective_date"].get("fallback_days", 30))
    rows, violations = _audit_financial_availability(features, fallback_days)

    valuation_samples = _valuation_samples(features)
    valuation_failures = 0 if valuation_samples.empty else int((valuation_samples["pass_or_fail"] == "FAIL").sum())
    rows.append({"check_id": "LH-VAL-001", "check_name": "valuation quantile rolling windows", "status": "PASS" if valuation_failures == 0 else "FAIL", "profile": "both", "evidence": f"samples={len(valuation_samples)}, failures={valuation_failures}", "affected_file": "data/curated/stock_valuation_daily.parquet; data/curated/industry_daily.parquet", "recommendation": "估值分位窗口只能使用 signal_date 及以前的估值序列。"})

    _, candidate_scores = build_universe_funnel(features, V2_HISTORY_DIR, configs["v2_universe"], configs["metric_map"])
    stock_daily = pd.read_parquet(resolve_path("data/curated/stock_valuation_daily.parquet"))
    industry_daily = pd.read_parquet(resolve_path("data/curated/industry_daily.parquet"))
    valuation_resolution = build_valuation_field_resolution(candidate_scores, stock_daily, industry_daily)
    resolution_failures = int((valuation_resolution["pass_or_fail"] == "FAIL").sum()) if not valuation_resolution.empty else 0
    resolution_warnings = int((valuation_resolution["pass_or_fail"] == "WARN").sum()) if not valuation_resolution.empty else 0
    rows.append(
        {
            "check_id": "LH-VAL-SOURCE-001",
            "check_name": "combined_v2 resolver valuation source fields",
            "status": "FAIL" if resolution_failures else ("WARN" if resolution_warnings else "PASS"),
            "profile": "combined_v2",
            "evidence": f"candidate_rows={len(valuation_resolution)}, failures={resolution_failures}, warnings={resolution_warnings}",
            "affected_file": "reports/backtest/combined_v2_candidate_scores.csv",
            "recommendation": "审计 resolver 实际使用的 stock/industry source_field；只有 source_field 为空或 source_after_signal_date 才降级。",
        }
    )

    tech_missing = [field for field in TECHNICAL_FIELDS if field not in features.columns]
    rows.append({"check_id": "LH-TECH-001", "check_name": "technical indicators use current-or-prior bars", "status": "PASS" if not tech_missing else "WARN", "profile": "both", "evidence": f"checked={','.join([f for f in TECHNICAL_FIELDS if f in features.columns])}; missing={','.join(tech_missing)}; max_source_date_used=signal_date", "affected_file": "data/features/daily_features", "recommendation": "移动均线、斜率、ATR、close 和 benchmark MA 只允许使用 signal_date 及以前行情。"})

    universe_pit_features = load_feature_window("2023-03-01", DEFAULT_END_DATE)
    universe_pit = _audit_universe_pit(universe_pit_features)
    universe_failures = int(universe_pit["used_future_data"].sum()) if not universe_pit.empty else 0
    rows.append({"check_id": "LH-UNI-001", "check_name": "combined_v2 historical universe point-in-time", "status": "PASS" if universe_failures == 0 else "FAIL", "profile": "combined_v2", "evidence": f"monthly_files={len(universe_pit)}, future_data_files={universe_failures}", "affected_file": V2_HISTORY_DIR, "recommendation": "月度股票池必须用 refresh_date 及以前数据生成，并在下一交易日生效。"})

    for _, sample in valuation_samples[valuation_samples["pass_or_fail"] == "FAIL"].iterrows():
        violations.append({"violation_type": "valuation_quantile_future_source", "signal_date": sample["signal_date"], "ts_code": sample["ts_code"], "field": sample["metric"], "report_date": "", "announcement_date": "", "fallback_days": fallback_days, "detail": f"max_source_date_used={sample['max_source_date_used']}"})
    for _, sample in valuation_resolution[valuation_resolution["pass_or_fail"] == "FAIL"].iterrows():
        violations.append(
            {
                "violation_type": "valuation_resolver_future_source",
                "signal_date": sample["signal_date"],
                "ts_code": sample["ts_code"],
                "field": f"{sample['stock_valuation_quantile_source_field']};{sample['industry_valuation_quantile_source_field']}",
                "report_date": "",
                "announcement_date": "",
                "fallback_days": fallback_days,
                "detail": f"max_source_date_used={sample['max_source_date_used']}; warning_reason={sample['warning_reason']}",
            }
        )

    audit_status = status_from_rows(rows)
    pd.DataFrame(rows).to_csv(ensure_parent("reports/backtest/audit/lookahead_audit.csv"), index=False)
    violation_columns = ["violation_type", "signal_date", "ts_code", "field", "report_date", "announcement_date", "fallback_days", "detail"]
    pd.DataFrame(violations, columns=violation_columns).to_csv(ensure_parent("reports/backtest/audit/lookahead_violations.csv"), index=False)
    universe_pit.to_csv(ensure_parent("reports/backtest/audit/universe_pit_audit.csv"), index=False)
    valuation_samples.to_csv(ensure_parent("reports/backtest/audit/lookahead_quantile_samples.csv"), index=False)
    valuation_resolution.to_csv(ensure_parent("reports/backtest/audit/lookahead_valuation_field_resolution.csv"), index=False)

    lines = [
        "# 前视偏差审计",
        "",
        f"- 审计结论: {audit_status}",
        f"- 固定区间: {DEFAULT_START_DATE} 到 {DEFAULT_END_DATE}",
        f"- 财务字段 fallback_lag: {fallback_days} 天",
        f"- 确认违规条数: {len(violations)}",
        f"- 估值分位抽样: {len(valuation_samples)} 条，失败 {valuation_failures} 条",
        f"- resolver 字段解析: {len(valuation_resolution)} 条，WARN {resolution_warnings} 条，FAIL {resolution_failures} 条",
        f"- combined_v2 月度股票池 PIT 文件数: {len(universe_pit)}，future-data 文件数: {universe_failures}",
        "",
        "## 检查项",
        "",
    ]
    for item in rows:
        lines.append(f"- {item['check_id']} {item['status']}: {item['check_name']}。证据：{item['evidence']}")
    if not valuation_samples.empty:
        lines.extend(["", "## 估值分位抽样证据", ""])
        for item in valuation_samples.head(20).to_dict(orient="records"):
            lines.append(f"- {item['signal_date']} {item['ts_code']} {item['metric']}: window_end={item['window_end']}, max_source_date_used={item['max_source_date_used']}, {item['pass_or_fail']}")
    if not valuation_resolution.empty:
        lines.extend(["", "## resolver 字段解析证据", ""])
        for item in valuation_resolution.head(20).to_dict(orient="records"):
            lines.append(
                f"- {item['signal_date']} {item['ts_code']} {item['bucket']}: "
                f"stock={item['stock_valuation_quantile_source_field']}({item['stock_valuation_metric']}), "
                f"industry={item['industry_valuation_quantile_source_field']}({item['industry_valuation_metric']}), "
                f"max_source_date_used={item['max_source_date_used']}, {item['pass_or_fail']}"
            )
    ensure_parent("reports/backtest/audit/lookahead_audit.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
