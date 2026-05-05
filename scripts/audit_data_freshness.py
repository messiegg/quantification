#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_data_freshness import _max_date_from_parquet, build_data_freshness_report
from scripts.report_metadata import metadata_header, status_from_children, write_json
from src.utils.config import load_yaml_optional, resolve_path


JSON_PATH = "reports/audit/data_freshness.json"
MD_PATH = "reports/audit/data_freshness.md"
DEFAULT_REQUESTED_DATE = "2026-05-04"


def _date_str(value: object) -> str:
    if value in {None, ""}:
        return ""
    ts = pd.to_datetime(value, errors="coerce")
    if pd.isna(ts):
        return ""
    return pd.Timestamp(ts).strftime("%Y-%m-%d")


def _max_financial_dates() -> dict[str, str]:
    candidates = [
        ("data/curated/financials_effective.parquet", ("report_date", "effective_date")),
        ("data/raw/financials.parquet", ("report_date", "announcement_date")),
    ]
    result = {
        "financial_data_asof": "",
        "effective_financial_date": "",
        "financial_source": "",
    }
    for path_like, columns in candidates:
        path = resolve_path(path_like)
        if not path.exists():
            continue
        try:
            frame = pd.read_parquet(path)
        except Exception:
            continue
        if frame.empty:
            continue
        report_col, effective_col = columns
        report_date = ""
        effective_date = ""
        if report_col in frame.columns:
            report_date = _date_str(pd.to_datetime(frame[report_col], errors="coerce").max())
        if effective_col in frame.columns:
            effective_date = _date_str(pd.to_datetime(frame[effective_col], errors="coerce").max())
        result.update(
            {
                "financial_data_asof": report_date,
                "effective_financial_date": effective_date,
                "financial_source": path_like,
            }
        )
        return result
    return result


def build_audit_data_freshness_report(
    requested_date: str = DEFAULT_REQUESTED_DATE,
    *,
    write_report: bool = True,
    benchmark_unused: bool = False,
    freshness_payload: dict[str, Any] | None = None,
) -> dict[str, Any]:
    base = freshness_payload or build_data_freshness_report(requested_date, write_report=False)
    financial = _max_financial_dates()
    target = _date_str(base.get("target_trading_date"))
    market_asof = _date_str(base.get("data_max_date"))
    feature_asof = _date_str(base.get("feature_max_date"))
    benchmark_asof = _date_str(base.get("benchmark_max_date"))
    warnings: list[dict[str, Any]] = []
    violations: list[dict[str, Any]] = []

    def fail(code: str, message: str, expected: object, actual: object) -> None:
        violations.append({"code": code, "message": message, "expected": expected, "actual": actual})

    def warn(code: str, message: str, expected: object, actual: object) -> None:
        warnings.append({"code": code, "message": message, "expected": expected, "actual": actual})

    if base.get("allowed_actions") != "observation_report_allowed":
        fail("BASE_FRESHNESS_BLOCKED", "base freshness gate blocks observation", "observation_report_allowed", base.get("blocking_reason"))
    if target and market_asof and target > market_asof:
        fail("MARKET_DATA_BEFORE_TARGET", "target_trade_date is later than market_data_asof", f">={target}", market_asof)
    if target and feature_asof and target > feature_asof:
        fail("FEATURE_DATA_BEFORE_TARGET", "target_trade_date is later than feature_data_asof", f">={target}", feature_asof)
    if target and benchmark_asof and target > benchmark_asof and not benchmark_unused:
        fail("BENCHMARK_DATA_BEFORE_TARGET", "benchmark_data_asof is earlier than target_trade_date", f">={target}", benchmark_asof)
    if not benchmark_asof and not benchmark_unused:
        fail("BENCHMARK_DATA_MISSING", "benchmark participates in reports but benchmark_data_asof is missing", "present", "missing")

    financial_asof = financial["financial_data_asof"]
    effective_financial_date = financial["effective_financial_date"]
    if financial_asof and not effective_financial_date:
        warn(
            "FINANCIAL_EFFECTIVE_DATE_MISSING",
            "financial_data_asof exists but effective_financial_date is missing",
            "effective_financial_date present",
            "missing",
        )
    if target and effective_financial_date and effective_financial_date > target:
        fail(
            "FINANCIAL_EFFECTIVE_DATE_AFTER_TARGET",
            "effective financial date is after target trade date",
            f"<={target}",
            effective_financial_date,
        )

    status = status_from_children(["FAIL" if violations else "WARN" if warnings else "PASS"])
    payload = {
        **metadata_header(requested_date=requested_date, target_trade_date=target),
        "status": status,
        "checked_at": metadata_header()["generated_at"],
        "requested_date": _date_str(requested_date),
        "target_trade_date": target,
        "target_trading_date": target,
        "requested_as_of_is_trading_day": base.get("requested_as_of_is_trading_day"),
        "market_data_asof": market_asof,
        "feature_data_asof": feature_asof,
        "benchmark_data_asof": benchmark_asof,
        "benchmark_unused": benchmark_unused,
        "financial_data_asof": financial_asof,
        "effective_financial_date": effective_financial_date,
        "financial_source": financial["financial_source"],
        "base_freshness": base,
        "violations": violations,
        "warnings": warnings,
    }
    if write_report:
        write_json(JSON_PATH, payload)
        _write_md(payload, MD_PATH)
    return payload


def _write_md(payload: dict[str, Any], path_like: str | Path) -> None:
    path = resolve_path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# data freshness audit",
        "",
        f"- status: {payload['status']}",
        f"- checked_at: {payload['checked_at']}",
        f"- git_commit: {payload['git_commit']}",
        f"- config_hash: {payload['config_hash']}",
        f"- requested_date: {payload['requested_date']}",
        f"- target_trade_date: {payload['target_trade_date']}",
        f"- market_data_asof: {payload['market_data_asof']}",
        f"- feature_data_asof: {payload['feature_data_asof']}",
        f"- benchmark_data_asof: {payload['benchmark_data_asof']}",
        f"- benchmark_unused: {str(payload['benchmark_unused']).lower()}",
        f"- financial_data_asof: {payload['financial_data_asof'] or 'unknown'}",
        f"- effective_financial_date: {payload['effective_financial_date'] or 'unknown'}",
        "",
        "## FAIL",
        "",
    ]
    lines.extend([f"- {item['code']}: {item['message']} expected={item['expected']} actual={item['actual']}" for item in payload.get("violations", [])] or ["- 无"])
    lines.extend(["", "## WARN", ""])
    lines.extend([f"- {item['code']}: {item['message']} expected={item['expected']} actual={item['actual']}" for item in payload.get("warnings", [])] or ["- 无"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def parse_args() -> argparse.Namespace:
    observation = load_yaml_optional("config/observation.yml")
    default_date = str((observation.get("observation", {}) or {}).get("default_as_of_date", DEFAULT_REQUESTED_DATE))
    parser = argparse.ArgumentParser(description="Audit date and freshness fields used by release/observation reports.")
    parser.add_argument("--requested-date", "--as-of-date", dest="requested_date", default=default_date)
    parser.add_argument("--benchmark-unused", action="store_true")
    parser.add_argument("--no-write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = build_audit_data_freshness_report(
        args.requested_date,
        benchmark_unused=args.benchmark_unused,
        write_report=not args.no_write_report,
    )
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
