#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_data_freshness import build_data_freshness_report
from scripts.check_data_quality_for_observation import build_data_quality_observation_report
from scripts.check_release_sync_consistency import build_release_sync_consistency_check
from scripts.check_report_freshness import build_report_freshness_check
from scripts.update_paper_observation import ensure_paper_observation_files
from scripts.verify_combined_v2_rc import verify_release_candidate
from src.utils.config import load_yaml, resolve_path


GENERATED_ACTION_FILES = [
    "combined_v2_actions.csv",
    "combined_v2_blocked_signals.csv",
    "combined_v2_manual_order_list.csv",
    "combined_v2_1_risk_guard_actions.csv",
    "profile_compare.md",
    "observation_summary.md",
    "observation_summary.json",
]


def _status_from_frame(frame: pd.DataFrame) -> str:
    if frame.empty:
        return "FAIL"
    statuses = set(frame["status"].astype(str).str.upper())
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    return "PASS"


def _parse_bool(value: object) -> bool:
    return str(value).strip().lower() in {"1", "true", "yes", "y"}


def _read_csv_optional(path_like: str | Path) -> pd.DataFrame:
    path = resolve_path(path_like)
    if not path.exists():
        return pd.DataFrame()
    try:
        return pd.read_csv(path)
    except pd.errors.EmptyDataError:
        return pd.DataFrame()


def _repo_relative(path_like: str | Path) -> str:
    path = resolve_path(path_like)
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _latest_row(frame: pd.DataFrame, as_of_date: str) -> dict:
    if frame.empty or "date" not in frame.columns:
        return {}
    work = frame.copy()
    work["date"] = work["date"].astype(str)
    work = work[work["date"] <= as_of_date].sort_values("date")
    return work.iloc[-1].to_dict() if not work.empty else {}


def _date_rows(frame: pd.DataFrame, as_of_date: str) -> pd.DataFrame:
    if frame.empty or "date" not in frame.columns:
        return pd.DataFrame()
    return frame[frame["date"].astype(str) == as_of_date].copy()


def _blocking_status(freshness: dict) -> str:
    allowed = str(freshness.get("allowed_actions", ""))
    return "PASS" if allowed == "observation_report_allowed" else "FAIL"


def _remove_action_outputs(out_dir: Path) -> None:
    for filename in GENERATED_ACTION_FILES:
        path = out_dir / filename
        if path.exists():
            path.unlink()


def _write_blocked(
    out_dir: Path,
    as_of_date: str,
    reason: str,
    freshness: dict | None = None,
    data_quality: dict | None = None,
) -> None:
    lines = [
        "# 观察期运行被阻断",
        "",
        f"- as_of_date: {as_of_date}",
        f"- blocking_reason: {reason}",
        "- action_allowed: false",
        "- 只允许历史复盘，不允许生成实盘观察日报或手工订单清单。",
        "- 禁止自动下单，禁止连接券商，禁止把 LLM 输出用于 action_enum。",
    ]
    if freshness:
        lines.extend(
            [
                "",
                "## 数据状态",
                "",
                f"- target_trading_date: {freshness.get('target_trading_date', '')}",
                f"- requested_as_of_is_trading_day: {str(freshness.get('requested_as_of_is_trading_day', '')).lower()}",
                f"- data_max_date: {freshness.get('data_max_date', '')}",
                f"- feature_max_date: {freshness.get('feature_max_date', '')}",
                f"- benchmark_max_date: {freshness.get('benchmark_max_date', '')}",
                f"- stale_calendar_days: {freshness.get('stale_calendar_days', '')}",
                f"- stale_trading_days: {freshness.get('stale_trading_days', '')}",
                f"- freshness_blocking_reason: {freshness.get('blocking_reason', '')}",
            ]
        )
    if data_quality:
        lines.extend(["", "## 数据质量", "", f"- data_quality_status: {data_quality.get('status', '')}"])
    (out_dir / "observation_blocked.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def _manual_order_list(actions: pd.DataFrame, as_of_date: str, profile: str, non_trading_day: bool) -> pd.DataFrame:
    columns = [
        "date",
        "as_of_date",
        "profile",
        "ts_code",
        "name",
        "side",
        "action",
        "signal_level",
        "shares",
        "price",
        "next_bar_price",
        "amount",
        "human_required",
        "requires_human_review",
        "review_scope",
        "execution_scope",
        "next_trading_day_manual_review_only",
        "market_closed_as_of_date",
        "auto_order_allowed",
        "broker_connected",
        "source",
        "notes",
    ]
    if actions.empty:
        return pd.DataFrame(columns=columns)
    rows = []
    for row in actions.to_dict(orient="records"):
        rows.append(
            {
                "date": row.get("date", as_of_date),
                "as_of_date": as_of_date,
                "profile": profile,
                "ts_code": row.get("ts_code", ""),
                "name": row.get("name", ""),
                "side": row.get("side", ""),
                "action": row.get("action", ""),
                "signal_level": row.get("signal_level", ""),
                "shares": row.get("shares", 0),
                "price": row.get("price", 0),
                "next_bar_price": row.get("price", 0),
                "amount": row.get("amount", 0),
                "human_required": True,
                "requires_human_review": True,
                "review_scope": "next_trading_day_manual_review_only" if non_trading_day else "manual_review_only",
                "execution_scope": "NEXT_TRADING_DAY_MANUAL_REVIEW_ONLY" if non_trading_day else "MANUAL_REVIEW_ONLY",
                "next_trading_day_manual_review_only": bool(non_trading_day),
                "market_closed_as_of_date": bool(non_trading_day),
                "auto_order_allowed": False,
                "broker_connected": False,
                "source": "paper_observation_only",
                "notes": "MARKET_CLOSED_AS_OF_DATE；仅作为下一交易日人工复盘，不连接券商、不自动下单。"
                if non_trading_day
                else "需要人工检查和人工执行；本仓库不连接券商、不自动下单。",
            }
        )
    return pd.DataFrame(rows, columns=columns)


def _paper_state() -> tuple[float, int, float]:
    paths = ensure_paper_observation_files()
    import yaml

    account = yaml.safe_load(paths["account"].read_text(encoding="utf-8")) or {}
    paper_account = account.get("paper_account", {})
    cash = float(paper_account.get("current_cash", paper_account.get("initial_capital", 200000)))
    positions = yaml.safe_load(paths["positions"].read_text(encoding="utf-8")) or {}
    paper_positions = positions.get("paper_positions", []) or []
    market_value = sum(float(item.get("market_value", 0.0) or 0.0) for item in paper_positions)
    return cash, len(paper_positions), market_value


def _generate_allowed_outputs(
    out_dir: Path,
    as_of_date: str,
    profile: str,
    conservative_profile: str,
    compare_conservative: bool,
    freshness: dict,
    data_quality: dict,
    allow_manual_order_list: bool,
) -> list[str]:
    generated: list[str] = []
    target_trading_date = str(freshness.get("target_trading_date") or as_of_date)
    non_trading_day = not bool(freshness.get("requested_as_of_is_trading_day", True))
    funnel = _read_csv_optional("reports/backtest/combined_v2_signal_funnel.csv")
    blocked = _read_csv_optional("reports/backtest/combined_v2_blocked_signals.csv")
    actions = _date_rows(_read_csv_optional("reports/backtest/combined_v2_trades_detailed.csv"), target_trading_date)
    guard_actions = _date_rows(_read_csv_optional("reports/backtest/v2_1/combined_v2_1_risk_guard_trades_detailed.csv"), target_trading_date)
    latest = _latest_row(funnel, target_trading_date)
    blocked_day = _date_rows(blocked, target_trading_date)
    blocked_counts = (
        blocked_day["reason_code"].value_counts().rename_axis("reason_code").reset_index(name="count")
        if not blocked_day.empty and "reason_code" in blocked_day.columns
        else pd.DataFrame(columns=["reason_code", "count"])
    )
    manual_orders = _manual_order_list(actions, as_of_date, profile, non_trading_day)

    action_path = out_dir / f"{profile}_actions.csv"
    blocked_path = out_dir / f"{profile}_blocked_signals.csv"
    manual_path = out_dir / f"{profile}_manual_order_list.csv"
    guard_path = out_dir / f"{conservative_profile}_actions.csv"
    actions.to_csv(action_path, index=False)
    blocked_day.to_csv(blocked_path, index=False)
    generated.extend([_repo_relative(action_path), _repo_relative(blocked_path)])
    if allow_manual_order_list:
        manual_orders.to_csv(manual_path, index=False)
        generated.append(_repo_relative(manual_path))
    if compare_conservative:
        guard_actions.to_csv(guard_path, index=False)
        generated.append(_repo_relative(guard_path))

    compare_lines = [
        "# combined_v2 vs combined_v2_1_risk_guard 观察对照",
        "",
        "- combined_v2 仍是 primary_profile。",
        "- combined_v2_1_risk_guard 只作为 conservative_profile 输出，不替换主候选。",
        "- 非交易日仅用于 next trading day manual review。",
        "- auto_order_allowed: false。",
        "- broker_connected: false。",
        f"- combined_v2 当日动作数: {len(actions)}",
        f"- combined_v2_1_risk_guard 当日动作数: {len(guard_actions)}",
    ]
    if compare_conservative and not actions.empty and not guard_actions.empty:
        main_keys = set(actions["ts_code"].astype(str) + ":" + actions["side"].astype(str))
        guard_keys = set(guard_actions["ts_code"].astype(str) + ":" + guard_actions["side"].astype(str))
        compare_lines.append(f"- 不同动作数: {len(main_keys.symmetric_difference(guard_keys))}")
        compare_lines.append(f"- v2_1 是否更保守: {'是' if len(guard_actions) <= len(actions) else '否'}")
    else:
        compare_lines.append("- v2_1 是否更保守: 当日无足够动作差异，继续观察。")
    compare_path = out_dir / "profile_compare.md"
    compare_path.write_text("\n".join(compare_lines) + "\n", encoding="utf-8")
    generated.append(_repo_relative(compare_path))

    cash, holdings_count, paper_market_value = _paper_state()
    blocked_summary = blocked_counts.to_dict(orient="records")
    quality_warnings = [
        row
        for row in data_quality.get("checks", [])
        if isinstance(row, dict) and str(row.get("status", "")).upper() == "WARN"
    ]
    summary = {
        "as_of_date": as_of_date,
        "profile": profile,
        "conservative_profile": conservative_profile,
        "action_allowed": True,
        "auto_order_allowed": False,
        "data": freshness,
        "data_quality": data_quality,
        "target_trading_date": target_trading_date,
        "market_closed_as_of_date": non_trading_day,
        "market_regime": latest.get("market_regime", ""),
        "max_total_exposure": latest.get("max_total_exposure", ""),
        "current_paper_exposure": paper_market_value / max(cash + paper_market_value, 1e-9),
        "cash": cash,
        "holdings_count": holdings_count,
        "effective_universe_size": latest.get("effective_universe_size", ""),
        "raw_buy_signals": latest.get("raw_buy_signal_count", ""),
        "raw_sell_signals": latest.get("raw_sell_signal_count", ""),
        "executable_actions": len(actions),
        "blocked_reasons": blocked_summary,
        "data_quality_warning_count": len(quality_warnings),
        "data_quality_warnings": quality_warnings,
        "manual_order_list": _repo_relative(manual_path) if allow_manual_order_list else "",
    }
    (out_dir / "observation_summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    generated.append(_repo_relative(out_dir / "observation_summary.json"))

    lines = [
        "# 每日人工观察报告",
        "",
        "## 结论区",
        "",
        "- 允许生成观察日报: 是。",
        "- 数据 stale 阻断: 否。",
        "- RC verify: PASS。",
        "- report freshness: PASS。",
        "- release sync consistency: PASS。",
        "- data freshness: PASS。",
        f"- data quality: {data_quality.get('status', '')}。",
        "- 禁止自动下单。",
        "- broker_connected: false。",
        "- auto_order_allowed: false。",
    ]
    if non_trading_day:
        lines.extend(
            [
                "- MARKET_CLOSED_AS_OF_DATE。",
                "- 所有动作只作为 next trading day manual review。",
            ]
        )
    lines.extend(
        [
            "",
            "## 数据状态",
            "",
            f"- requested_as_of_date: {freshness.get('requested_as_of_date')}",
            f"- requested_as_of_is_trading_day: {str(freshness.get('requested_as_of_is_trading_day')).lower()}",
            f"- target_trading_date: {freshness.get('target_trading_date')}",
            f"- data_max_date: {freshness.get('data_max_date')}",
            f"- feature_max_date: {freshness.get('feature_max_date')}",
            f"- benchmark_max_date: {freshness.get('benchmark_max_date')}",
            f"- stale_calendar_days: {freshness.get('stale_calendar_days')}",
            f"- stale_trading_days: {freshness.get('stale_trading_days')}",
            f"- blocking_reason: {freshness.get('blocking_reason')}",
            "",
            "## 数据质量",
            "",
            f"- data_quality_status: {data_quality.get('status', '')}",
            f"- feature_rows_on_target_date: {data_quality.get('feature_rows_on_target_date', '')}",
            f"- unique_stocks_on_target_date: {data_quality.get('unique_stocks_on_target_date', '')}",
            f"- benchmark_row_exists_on_target_trading_date: {data_quality.get('benchmark_row_exists_on_target_trading_date', '')}",
            "",
        ]
    )
    if quality_warnings:
        lines.extend(
            [
                "### 数据质量 WARN 摘要",
                "",
                "- WARN 不等于禁止观察；本报告仍要求人工复核。",
            ]
        )
        for row in quality_warnings:
            lines.append(
                f"- {row.get('check_id', '')} | {row.get('check_name', '')} | actual={row.get('actual', '')} | {row.get('recommendation', '')}"
            )
        lines.append("")
    lines.extend(
        [
        "## combined_v2 当前状态",
        "",
        f"- market_regime: {summary['market_regime']}",
        f"- max_total_exposure: {summary['max_total_exposure']}",
        f"- current paper exposure: {summary['current_paper_exposure']:.2%}",
        f"- cash: {summary['cash']:.2f}",
        f"- holdings_count: {summary['holdings_count']}",
        f"- effective_universe_size: {summary['effective_universe_size']}",
        f"- raw buy / sell signals: {summary['raw_buy_signals']} / {summary['raw_sell_signals']}",
        f"- executable actions: {summary['executable_actions']}",
        "- blocked reasons: "
        + ("; ".join(f"{item['reason_code']}={item['count']}" for item in blocked_summary) if blocked_summary else "无"),
        "",
        "## 手工动作清单",
        "",
        "- 只输出建议，需要人工判断和人工执行。",
        "- 不连接券商，禁止自动下单，不生成实盘委托。",
        f"- 本地文件: {_repo_relative(manual_path) if allow_manual_order_list else '未生成'}",
        "- 该文件为 ignored local artifact，不提交公开仓库。" if allow_manual_order_list else "- 未生成手工动作清单。",
        "- auto_order_allowed: false。",
        "- broker_connected: false。",
        "- requires_human_review: true。",
        "- review_scope: next_trading_day_manual_review_only。" if non_trading_day else "- review_scope: manual_review_only。",
        "- execution_scope: NEXT_TRADING_DAY_MANUAL_REVIEW_ONLY。" if non_trading_day else "- execution_scope: MANUAL_REVIEW_ONLY。",
        "",
        "## combined_v2_1_risk_guard 对照",
        "",
        "- combined_v2_1_risk_guard 只作为 conservative_profile 输出，不替换 combined_v2。",
        "- 风险限制阻断差异见 profile_compare.md。",
        "- 是否更保守需要持续观察，不能自动替换主候选。",
        "",
        "## 风险提示",
        "",
        "- 数据当前通过 freshness gate。",
        "- 当前策略仍只有三年回测，样本偏短。",
        "- risk_off daily MTM 损失仍明显。",
        "- A 股风格切换可能削弱当前估值和 bucket 逻辑。",
        "- 手工观察期不得扩大仓位。",
        ]
    )
    summary_path = out_dir / "observation_summary.md"
    summary_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    generated.append(_repo_relative(summary_path))
    return generated


def run_observation_pipeline(
    as_of_date: str,
    profile: str = "combined_v2",
    mode: str = "paper",
    compare_conservative: bool = True,
    force_historical_review: bool = False,
    rerun_rc_verify: bool = True,
) -> dict:
    cfg = load_yaml("config/observation.yml")
    obs = cfg.get("observation", {})
    manual = cfg.get("manual_observation", {})
    conservative_profile = str(obs.get("conservative_profile", "combined_v2_1_risk_guard"))
    out_dir = resolve_path(Path(str(manual.get("observation_report_dir", "reports/observation"))) / as_of_date)
    out_dir.mkdir(parents=True, exist_ok=True)
    ensure_paper_observation_files()

    rc = verify_release_candidate(rerun_backtest=rerun_rc_verify)
    rc_status = _status_from_frame(rc)
    stale = build_report_freshness_check(include_observation_gate=False)
    stale_status = _status_from_frame(stale)
    release_sync = build_release_sync_consistency_check(write_report=False, include_observation_gate=False)
    release_sync_status = _status_from_frame(release_sync)
    freshness = build_data_freshness_report(as_of_date, write_report=True)
    data_status = _blocking_status(freshness)
    data_quality: dict = {}
    data_quality_status = "SKIPPED"
    if data_status == "PASS":
        data_quality = build_data_quality_observation_report(as_of_date, write_report=True)
        data_quality_status = str(data_quality.get("status", "FAIL"))

    generated: list[str] = []
    blocking_reason = "NONE"
    action_allowed = True
    if rc_status == "FAIL":
        blocking_reason = "RC_VERIFY_FAIL"
        action_allowed = False
    elif stale_status == "FAIL":
        blocking_reason = "REPORT_STALE_OR_CONFLICTING"
        action_allowed = False
    elif release_sync_status == "FAIL":
        blocking_reason = "RELEASE_SYNC_CONSISTENCY_FAIL"
        action_allowed = False
    elif data_status == "FAIL" and not force_historical_review:
        blocking_reason = "STALE_DATA_BLOCKED"
        action_allowed = False
    elif data_quality_status == "FAIL":
        blocking_reason = "DATA_QUALITY_FAIL"
        action_allowed = False

    if not action_allowed:
        _remove_action_outputs(out_dir)
        _write_blocked(out_dir, as_of_date, blocking_reason, freshness, data_quality)
        generated.append(_repo_relative(out_dir / "observation_blocked.md"))
    else:
        blocked_path = out_dir / "observation_blocked.md"
        if blocked_path.exists():
            blocked_path.unlink()
        allow_manual_order_list = bool(
            obs.get("generate_manual_order_list", True)
            and obs.get("generate_manual_order_list_only_when_market_data_current", True)
            and data_status == "PASS"
            and data_quality_status in {"PASS", "WARN"}
        )
        generated.extend(
            _generate_allowed_outputs(
                out_dir,
                as_of_date,
                profile,
                conservative_profile,
                compare_conservative,
                freshness,
                data_quality,
                allow_manual_order_list,
            )
        )

    manifest = {
        "as_of_date": as_of_date,
        "run_time": datetime.now(timezone.utc).isoformat(),
        "profile": profile,
        "mode": mode,
        "conservative_profile": conservative_profile,
        "data_freshness_status": data_status,
        "rc_verify_status": rc_status,
        "stale_report_check_status": stale_status,
        "release_sync_consistency_status": release_sync_status,
        "data_quality_status": data_quality_status,
        "action_allowed": action_allowed,
        "target_trading_date": freshness.get("target_trading_date", ""),
        "requested_as_of_is_trading_day": freshness.get("requested_as_of_is_trading_day", None),
        "generated_files": generated + [_repo_relative(out_dir / "data_freshness_report.md")],
        "blocking_reason": blocking_reason,
        "broker_connected": False,
        "auto_order_enabled": False,
        "llm_decision_allowed": False,
    }
    manifest_path = out_dir / "observation_run_manifest.json"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run paper-only combined_v2 observation pipeline.")
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--profile", default="combined_v2")
    parser.add_argument("--mode", default="paper")
    parser.add_argument("--compare-conservative", default="true")
    parser.add_argument("--force-historical-review", default="false")
    parser.add_argument("--skip-rc-rerun", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    run_observation_pipeline(
        as_of_date=args.as_of_date,
        profile=args.profile,
        mode=args.mode,
        compare_conservative=_parse_bool(args.compare_conservative),
        force_historical_review=_parse_bool(args.force_historical_review),
        rerun_rc_verify=not args.skip_rc_rerun,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
