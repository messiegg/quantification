#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.generate_50k_core_traces import DEFAULT_OUTPUT_DIR, _safe_float
from src.utils.config import resolve_path


def _read_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame()
    return pd.read_csv(path)


def _read_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _pct(value: Any) -> str:
    return f"{_safe_float(value):.2%}"


def _safe_markdown(frame: pd.DataFrame, *, limit: int = 20) -> str:
    if frame.empty:
        return "No rows."
    return frame.head(limit).to_markdown(index=False)


def _top_losses(drawdown: pd.DataFrame, by: str) -> pd.DataFrame:
    if drawdown.empty or by not in drawdown.columns or "pnl_contribution_during_drawdown" not in drawdown.columns:
        return pd.DataFrame()
    return (
        drawdown.groupby(by, dropna=False)["pnl_contribution_during_drawdown"]
        .sum()
        .sort_values()
        .reset_index()
        .head(10)
    )


def _drawdown_questions(drawdown: pd.DataFrame, daily: pd.DataFrame, exit_trace: pd.DataFrame, replacement: pd.DataFrame) -> list[str]:
    if drawdown.empty:
        return ["- drawdown attribution: missing"]
    first = drawdown.iloc[0]
    start = str(first.get("start_date", ""))
    trough = str(first.get("trough_date", ""))
    recovery = str(first.get("recovery_date", ""))
    dates = set(pd.date_range(start, trough).strftime("%Y-%m-%d")) if start and trough else set()
    dd_daily = daily[daily["date"].astype(str).isin(dates)] if not daily.empty else pd.DataFrame()
    dd_exit = exit_trace[exit_trace["date"].astype(str).isin(dates)] if not exit_trace.empty else pd.DataFrame()
    dd_repl = replacement[replacement["date"].astype(str).isin(dates)] if not replacement.empty else pd.DataFrame()
    risk_on_ratio = float((dd_daily.get("market_regime", pd.Series(dtype=str)).astype(str) == "risk_on").mean()) if not dd_daily.empty else 0.0
    avg_exposure = float(pd.to_numeric(dd_daily.get("gross_exposure", pd.Series(dtype=float)), errors="coerce").mean()) if not dd_daily.empty else 0.0
    exit_missed = bool(dd_exit.get("missed_exit_candidate", pd.Series(dtype=bool)).astype(bool).any()) if not dd_exit.empty else False
    repl_missed = bool((dd_repl.get("replacement_triggered", pd.Series(dtype=bool)).astype(bool) == False).any()) if not dd_repl.empty else False
    return [
        f"- max_drawdown_window: {start} to {trough}; recovery={recovery or 'not recovered in trace'}; max_drawdown={_pct(first.get('max_drawdown'))}",
        f"- market_regime: risk_on_days_ratio={risk_on_ratio:.2f}",
        f"- average_exposure_during_drawdown: {_pct(avg_exposure)}",
        f"- exit_lag_supported: {'yes' if exit_missed else 'no clear missed exit in trace'}",
        f"- replacement_missed_supported: {'yes' if repl_missed else 'no clear missed replacement in trace'}",
    ]


def write_drawdown_summary(out_dir: Path, drawdown: pd.DataFrame, daily: pd.DataFrame, exit_trace: pd.DataFrame, replacement: pd.DataFrame) -> None:
    lines = ["# drawdown attribution summary", ""]
    lines.extend(_drawdown_questions(drawdown, daily, exit_trace, replacement))
    lines.extend(["", "## top loss symbols", "", _safe_markdown(_top_losses(drawdown, "symbol"))])
    lines.extend(["", "## top loss industries", "", _safe_markdown(_top_losses(drawdown, "industry"))])
    lines.extend(["", "## bucket loss distribution", "", _safe_markdown(_top_losses(drawdown, "bucket"))])
    lines.extend(
        [
            "",
            "## confidence",
            "",
            "Position-level attribution is supported by daily_position_pnl. Cost basis remains FIFO_APPROX_AVG_COST, so exact lot tax accounting is partial rather than broker-grade.",
        ]
    )
    (out_dir / "drawdown_attribution_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_risk_cash_summary(out_dir: Path, risk_cash: pd.DataFrame) -> None:
    lines = ["# risk-on cash trace summary", ""]
    if risk_cash.empty:
        lines.append("No risk-on cash rows.")
    else:
        counts = risk_cash["reason_cash_not_deployed"].value_counts().to_dict()
        high = risk_cash[pd.to_numeric(risk_cash["cash_gap_to_target"], errors="coerce") > 0]
        lines.extend(
            [
                f"- risk_on_days: {len(risk_cash)}",
                f"- high_cash_days_above_target: {len(high)}",
                f"- reason_counts: {counts}",
                f"- avg_cash_gap_to_target: {_pct(pd.to_numeric(high.get('cash_gap_to_target', pd.Series(dtype=float)), errors='coerce').mean() if not high.empty else 0.0)}",
                "",
                "## answers",
                "",
                "- NO_RAW_SIGNAL is now computed from signal_execution_trace rows. It means no raw buy intent was generated in the effective trace scope for that date.",
                "- PORTFOLIO_FULL with high cash means positions_count reached max_positions while position weights remained below the desired risk-on exposure; this is an allocation granularity issue, not a broker execution failure.",
                "- Replacement did not release enough cash because triggered candidate rows remained sparse and most portfolio-full rows did not become executable switch pairs.",
                "- Cash sleeve remains a research direction, but stock execution trace should be improved first only if it can create valid replacement/exit candidates without using future returns.",
            ]
        )
    (out_dir / "risk_on_cash_trace_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_no_trade_summary(out_dir: Path, intervals: pd.DataFrame) -> None:
    lines = ["# no-trade interval summary", ""]
    if intervals.empty:
        lines.append("No no-trade intervals.")
    else:
        longest = intervals.sort_values("trading_days", ascending=False).iloc[0]
        lines.extend(
            [
                f"- interval_count: {len(intervals)}",
                f"- longest_interval: {longest.get('start_date')} to {longest.get('end_date')}",
                f"- longest_trading_days: {int(longest.get('trading_days'))}",
                f"- months_covered: {int(longest.get('months_covered'))}",
                f"- dominant_market_regime: {longest.get('dominant_market_regime')}",
                f"- avg_cash_ratio: {_pct(longest.get('avg_cash_ratio'))}",
                f"- raw_buy_days: {int(longest.get('raw_buy_days'))}",
                f"- account_actionable_days: {int(longest.get('account_actionable_days'))}",
                f"- replacement_candidate_days: {int(longest.get('replacement_candidate_days'))}",
                f"- reason_no_trade_summary: {longest.get('reason_no_trade_summary')}",
                "",
                "No-trade intervals are now traceable to raw signal presence, account actionability, replacement candidate availability, and portfolio-full blockers.",
            ]
        )
    (out_dir / "no_trade_interval_summary.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_trace_diagnostic_report(out_dir: Path) -> None:
    daily = _read_csv(out_dir / "daily_portfolio_ledger.csv")
    position = _read_csv(out_dir / "daily_position_pnl.csv")
    trades = _read_csv(out_dir / "trade_ledger.csv")
    signal = _read_csv(out_dir / "signal_execution_trace.csv")
    exit_trace = _read_csv(out_dir / "exit_rule_trace.csv")
    replacement = _read_csv(out_dir / "replacement_candidate_trace.csv")
    drawdown = _read_csv(out_dir / "drawdown_attribution_trace.csv")
    risk_cash = _read_csv(out_dir / "risk_on_cash_trace.csv")
    intervals = _read_csv(out_dir / "no_trade_interval_trace.csv")
    missing = _read_json(out_dir / "trace_missing_fields.json")

    write_drawdown_summary(out_dir, drawdown, daily, exit_trace, replacement)
    write_risk_cash_summary(out_dir, risk_cash)
    write_no_trade_summary(out_dir, intervals)

    nav_recon_ok = False
    pnl_recon = None
    if not daily.empty:
        calc = pd.to_numeric(daily["nav"], errors="coerce") / pd.to_numeric(daily["previous_nav"], errors="coerce") - 1.0
        diff = (calc - pd.to_numeric(daily["daily_return"], errors="coerce")).abs().max()
        nav_recon_ok = bool(diff < 1e-10)
    if not position.empty and not daily.empty:
        pos_sum = position.groupby("date")["total_pnl_today"].sum()
        day = daily.set_index("date")["total_pnl_today"]
        common = pos_sum.index.intersection(day.index)
        pnl_recon = float((pos_sum.loc[common] - day.loc[common]).abs().median()) if len(common) else None

    top_symbol_losses = _top_losses(drawdown, "symbol")
    top_industry_losses = _top_losses(drawdown, "industry")
    top_bucket_losses = _top_losses(drawdown, "bucket")
    risk_counts = risk_cash["reason_cash_not_deployed"].value_counts().to_dict() if not risk_cash.empty else {}
    longest = intervals.sort_values("trading_days", ascending=False).iloc[0].to_dict() if not intervals.empty else {}

    lines = [
        "# trace diagnostic report",
        "",
        "## 1. Trace coverage summary",
        "",
        f"- daily_portfolio_ledger rows: {len(daily)}",
        f"- daily_position_pnl rows: {len(position)}",
        f"- trade_ledger rows: {len(trades)}",
        f"- signal_execution_trace rows: {len(signal)}",
        f"- exit_rule_trace rows: {len(exit_trace)}",
        f"- replacement_candidate_trace rows: {len(replacement)}",
        "",
        "## 2. Data quality limitations",
        "",
        f"- critical_missing: {missing.get('critical_missing', [])}",
    ]
    lines.extend(f"- {item}" for item in missing.get("partial_limitations", []))
    lines.extend(
        [
            "",
            "## 3. Portfolio daily ledger reconciliation",
            "",
            f"- nav_return_reconciliation_ok: {nav_recon_ok}",
            f"- median_position_vs_portfolio_pnl_abs_diff: {pnl_recon}",
            "",
            "## 4. Position-level PnL attribution",
            "",
            _safe_markdown(top_symbol_losses),
            "",
            "## 5. Max drawdown attribution",
            "",
        ]
    )
    lines.extend(_drawdown_questions(drawdown, daily, exit_trace, replacement))
    lines.extend(["", "Top industries:", "", _safe_markdown(top_industry_losses), "", "Top buckets:", "", _safe_markdown(top_bucket_losses)])
    lines.extend(
        [
            "",
            "## 6. Exit rule timing analysis",
            "",
            f"- missed_exit_candidates: {int(exit_trace.get('missed_exit_candidate', pd.Series(dtype=bool)).astype(bool).sum()) if not exit_trace.empty else 0}",
            f"- would_have_triggered_trend_stop: {int(exit_trace.get('would_have_triggered_trend_stop', pd.Series(dtype=bool)).astype(bool).sum()) if not exit_trace.empty else 0}",
            "",
            "## 7. Replacement candidate analysis",
            "",
            f"- replacement_candidate_rows: {len(replacement)}",
            f"- replacement_triggered_rows: {int(replacement.get('replacement_triggered', pd.Series(dtype=bool)).astype(bool).sum()) if not replacement.empty else 0}",
            "- diagnostic future returns remain diagnostic_only and are not present in signal_execution_trace.",
            "",
            "## 8. Risk-on cash drag analysis",
            "",
            f"- reason_counts: {risk_counts}",
            "",
            "## 9. No-trade interval analysis",
            "",
            f"- longest_interval: {longest.get('start_date')} to {longest.get('end_date')} ({longest.get('trading_days')} trading days)",
            f"- reason_no_trade_summary: {longest.get('reason_no_trade_summary')}",
            "",
            "## 10. Updated diagnosis vs phase2",
            "",
            "- Phase2 could only infer drawdown from portfolio NAV and global attribution. Trace now supports symbol/industry/bucket attribution with daily_position_pnl, but exact lot-level accounting is still approximate.",
            "- Risk-on cash reasons are now derived from signal_execution_trace rather than only daily funnel counts.",
            "- Replacement opportunity cost remains offline diagnostic-only and cannot be used as a rule input.",
            "",
            "## 11. What can now be concluded",
            "",
            "- Daily NAV, cash ratio, exposure, trade counts, signal blockers, exit-rule flags, and replacement comparisons are auditable by date.",
            "- Drawdown attribution can be traced to symbols, industries, and buckets within the available average-cost ledger.",
            "",
            "## 12. What still cannot be concluded",
            "",
            "- Broker-grade lot-level realized PnL cannot be concluded because the trace uses FIFO_APPROX_AVG_COST.",
            "- Live fill behavior cannot be concluded because all trades are research-only simulated next-bar fills.",
            "",
            "## 13. Recommended next engineering step",
            "",
            "- Before another repair search, add exact lot inventory accounting if broker-grade realized/unrealized decomposition is required; otherwise use this trace base to test a small cash-sleeve research interface separately.",
            "",
            "## 14. Safety statement",
            "",
            "research_only=true; auto_trading_approved=false; broker_integration_enabled=false; llm_decision_allowed=false; writes_real_trades=false; release_profile_replacement=false.",
        ]
    )
    (out_dir / "trace_diagnostic_report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Diagnose generated combined_v2_50k_core trace ledgers.")
    parser.add_argument("--trace-dir", default=DEFAULT_OUTPUT_DIR)
    args = parser.parse_args(argv)
    out_dir = resolve_path(args.trace_dir)
    write_trace_diagnostic_report(out_dir)
    print(json.dumps({"trace_dir": str(out_dir), "report": str(out_dir / "trace_diagnostic_report.md")}, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
