#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.config import load_yaml_optional, resolve_path


FORBIDDEN_ACTIVE_PHRASES = [
    "今日实盘执行",
    "今日下单",
    "允许自动下单",
    "自动下单: 允许",
    "自动下单：允许",
    "auto_order_allowed: true",
    "真实订单已生成",
]


def _read_json(path: Path) -> dict:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _legacy_superseded(path: Path) -> bool:
    if not path.exists():
        return False
    header = "\n".join(path.read_text(encoding="utf-8").splitlines()[:8])
    return "LEGACY_SUPERSEDED" in header


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


def build_observation_gate_consistency_check(
    as_of_date: str,
    output_csv: str | Path | None = None,
    output_md: str | Path | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    cfg = load_yaml_optional("config/observation.yml")
    manual_cfg = cfg.get("manual_observation", {}) if isinstance(cfg, dict) else {}
    out_dir = resolve_path(Path(str(manual_cfg.get("observation_report_dir", "reports/observation"))) / as_of_date)
    freshness = _read_json(out_dir / "data_freshness_report.json")
    quality = _read_json(out_dir / "data_quality_observation_report.json")
    manifest = _read_json(out_dir / "observation_run_manifest.json")
    summary_path = out_dir / "observation_summary.md"
    blocked_path = out_dir / "observation_blocked.md"
    manual_path = out_dir / "combined_v2_manual_order_list.csv"
    summary = _text(summary_path)
    manual_text = _text(manual_path)
    rows: list[dict] = []

    allowed = str(freshness.get("allowed_actions", "")) == "observation_report_allowed"
    historical_only = str(freshness.get("allowed_actions", "")) == "historical_review_only"
    blocked_is_current = blocked_path.exists() and not _legacy_superseded(blocked_path)

    if allowed:
        _row(
            rows,
            "GATE-001",
            "allowed freshness has no current blocked report",
            "PASS" if not blocked_is_current else "FAIL",
            "observation_blocked.md absent or LEGACY_SUPERSEDED",
            "current" if blocked_is_current else "absent_or_legacy",
            str(blocked_path),
            "freshness 已允许观察时，旧 blocked 报告不能作为当前主报告存在。",
        )
        _row(rows, "GATE-002", "summary exists when freshness allowed", "PASS" if summary_path.exists() else "FAIL", "exists", summary_path.exists(), str(summary_path), "允许观察时必须生成 observation_summary.md。")
        _row(rows, "GATE-003", "manifest action_allowed true", "PASS" if manifest.get("action_allowed") is True else "FAIL", "true", manifest.get("action_allowed"), str(out_dir / "observation_run_manifest.json"), "manifest 必须反映本次观察已允许。")
    elif historical_only:
        _row(rows, "GATE-004", "blocked report exists when freshness blocks", "PASS" if blocked_path.exists() else "FAIL", "exists", blocked_path.exists(), str(blocked_path), "freshness 阻断时必须生成 blocked 报告。")
        _row(rows, "GATE-005", "summary absent when freshness blocks", "PASS" if not summary_path.exists() else "FAIL", "absent", summary_path.exists(), str(summary_path), "阻断时不得保留当前 observation_summary.md。")
        _row(rows, "GATE-006", "manual list absent when freshness blocks", "PASS" if not manual_path.exists() else "FAIL", "absent", manual_path.exists(), str(manual_path), "阻断时不得生成手工清单。")
    else:
        _row(rows, "GATE-000", "freshness allowed_actions recognized", "FAIL", "observation_report_allowed or historical_review_only", freshness.get("allowed_actions", "missing"), str(out_dir / "data_freshness_report.json"), "先生成有效 data_freshness_report.json。")

    market_closed = bool(freshness.get("market_closed_as_of_date")) and not bool(freshness.get("requested_as_of_is_trading_day", True))
    if market_closed and summary_path.exists():
        _row(rows, "MARKET-001", "holiday summary marks market closed", "PASS" if "MARKET_CLOSED_AS_OF_DATE" in summary else "FAIL", "contains MARKET_CLOSED_AS_OF_DATE", "present" if "MARKET_CLOSED_AS_OF_DATE" in summary else "missing", str(summary_path), "非交易日观察报告必须显式标记市场关闭。")
        forbidden = [phrase for phrase in FORBIDDEN_ACTIVE_PHRASES if phrase in summary]
        _row(rows, "MARKET-002", "holiday summary has no execution wording", "PASS" if not forbidden else "FAIL", "no active execution wording", "|".join(forbidden) if forbidden else "none", str(summary_path), "非交易日报告只能作为下一交易日人工复核。")

    if manual_path.exists():
        try:
            manual_frame = pd.read_csv(manual_path)
        except Exception:
            manual_frame = pd.DataFrame()
        if manual_frame.empty:
            has_next_scope = "execution_scope" in manual_frame.columns and "next_trading_day_manual_review_only" in manual_frame.columns
            has_auto_false = "auto_order_allowed" in manual_frame.columns
            has_human_true = "requires_human_review" in manual_frame.columns
        else:
            has_next_scope = bool(
                "NEXT_TRADING_DAY_MANUAL_REVIEW_ONLY" in set(manual_frame.get("execution_scope", pd.Series(dtype=str)).astype(str))
                or manual_frame.get("next_trading_day_manual_review_only", pd.Series(dtype=bool)).astype(str).str.lower().eq("true").all()
            )
            has_auto_false = bool("auto_order_allowed" in manual_frame.columns and manual_frame["auto_order_allowed"].astype(str).str.lower().eq("false").all())
            has_human_true = bool("requires_human_review" in manual_frame.columns and manual_frame["requires_human_review"].astype(str).str.lower().eq("true").all())
        _row(rows, "MANUAL-001", "manual list marks next trading day review", "PASS" if has_next_scope else "FAIL", "NEXT_TRADING_DAY_MANUAL_REVIEW_ONLY", has_next_scope, str(manual_path), "非交易日手工清单必须限定为下一交易日人工复核。")
        _row(rows, "MANUAL-002", "manual list disables auto order", "PASS" if has_auto_false else "FAIL", "auto_order_allowed=false", has_auto_false, str(manual_path), "手工清单必须明确禁止自动下单。")
        _row(rows, "MANUAL-003", "manual list requires human review", "PASS" if has_human_true else "FAIL", "requires_human_review=true", has_human_true, str(manual_path), "手工清单必须要求人工复核。")

    if str(quality.get("status", "")).upper() == "WARN" and summary_path.exists():
        has_warn = "data_quality_status: WARN" in summary or "data quality: WARN" in summary or "数据质量 WARN" in summary
        _row(rows, "QUALITY-001", "summary includes data quality WARN", "PASS" if has_warn else "FAIL", "WARN summary present", has_warn, str(summary_path), "数据质量 WARN 允许观察，但必须在 summary 中展示。")

    stale_calendar = freshness.get("stale_calendar_days")
    max_stale_calendar = freshness.get("max_stale_calendar_days")
    stale_trading = freshness.get("stale_trading_days")
    if (
        isinstance(stale_calendar, int)
        and isinstance(max_stale_calendar, int)
        and stale_calendar > max_stale_calendar
        and stale_trading == 0
        and market_closed
    ):
        warning_present = "STALE_CALENDAR_DAYS_EXCEED_LIMIT_NON_TRADING_DAY_WARN" in [str(item) for item in freshness.get("warnings", [])]
        _row(rows, "CAL-001", "holiday calendar staleness is warn only", "PASS" if allowed else "FAIL", "not blocking", freshness.get("blocking_reason", ""), str(out_dir / "data_freshness_report.json"), "非交易日且目标交易日数据已覆盖时，calendar staleness 不得阻断。")
        _row(rows, "CAL-002", "holiday calendar staleness warning present", "PASS" if warning_present else "FAIL", "warning present", warning_present, str(out_dir / "data_freshness_report.json"), "calendar-day 超阈值应作为非交易日自然间隔提示。")

    frame = pd.DataFrame(rows, columns=["check_id", "check_name", "status", "expected", "actual", "evidence", "recommendation"])
    if write_report:
        csv_path = resolve_path(output_csv or out_dir / "observation_gate_consistency_check.csv")
        md_path = resolve_path(output_md or out_dir / "observation_gate_consistency_check.md")
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
        overall = "FAIL" if (frame["status"] == "FAIL").any() else "WARN" if (frame["status"] == "WARN").any() else "PASS"
        lines = [
            "# observation gate consistency check",
            "",
            f"- overall_status: {overall}",
            f"- as_of_date: {as_of_date}",
            f"- fail_count: {int((frame['status'] == 'FAIL').sum())}",
            f"- warn_count: {int((frame['status'] == 'WARN').sum())}",
            "",
            "## checks",
            "",
        ]
        for row in frame.to_dict(orient="records"):
            lines.append(f"- {row['status']} | {row['check_id']} | {row['check_name']} | actual={row['actual']} | {row['recommendation']}")
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check observation gate transition consistency.")
    parser.add_argument("--as-of-date", required=True)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frame = build_observation_gate_consistency_check(args.as_of_date)
    return 1 if (frame["status"] == "FAIL").any() else 0


if __name__ == "__main__":
    raise SystemExit(main())
