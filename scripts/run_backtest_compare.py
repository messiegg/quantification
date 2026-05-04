#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from math import sqrt
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest import load_backtest_features
from src.pipeline.strict_data import clean_benchmark_frame
from src.strategy.backtest_engine import BacktestEngine
from src.strategy.backtest_reports import build_universe_funnel, write_diagnostic_outputs
from src.strategy.universe import build_candidate_pool, build_effective_universe, serialize_universe_payload, universe_report_payload
from src.utils.config import load_yaml, load_yaml_optional, resolve_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run baseline combined vs combined_v2 backtest comparison.")
    parser.add_argument("--start-date", default="2023-04-03")
    parser.add_argument("--end-date", default="2026-04-03")
    parser.add_argument("--features-file", default="data/features/daily_features")
    parser.add_argument("--benchmark-file", default="data/raw/benchmark_daily.parquet")
    parser.add_argument("--baseline-strategy-config", default="config/strategy.yml")
    parser.add_argument("--baseline-universe-config", default="config/universe_rules.yml")
    parser.add_argument("--v2-strategy-config", default="config/strategy_v2.yml")
    parser.add_argument("--v2-universe-config", default="config/universe_rules_v2.yml")
    parser.add_argument("--account-config", default="config/account.yml")
    parser.add_argument("--metric-map-config", default="config/metric_map.yml")
    parser.add_argument("--baseline-historical-universe-dir", default="data/curated/universe_history")
    parser.add_argument("--v2-historical-universe-dir", default="reports/backtest/combined_v2_universe_history")
    parser.add_argument("--execution-mode", default="next_bar", choices=["next_bar", "same_close"])
    return parser.parse_args()


def _benchmark_metrics(benchmark: pd.DataFrame) -> dict:
    if benchmark.empty:
        return {"benchmark_annual_return": 0.0, "benchmark_max_drawdown": 0.0}
    close = pd.to_numeric(benchmark["close"], errors="coerce").dropna()
    years = max(len(close) / 252, 1 / 252)
    annual = (close.iloc[-1] / close.iloc[0]) ** (1 / years) - 1
    drawdown = close / close.cummax() - 1
    return {"benchmark_annual_return": float(annual), "benchmark_max_drawdown": float(drawdown.min())}


def _generate_v2_history(
    features: pd.DataFrame,
    baseline_history_dir: str | Path,
    v2_history_dir: str | Path,
    universe_rules_cfg: dict,
    metric_map_cfg: dict,
) -> None:
    source_dir = resolve_path(baseline_history_dir)
    target_dir = resolve_path(v2_history_dir)
    target_dir.mkdir(parents=True, exist_ok=True)
    for old_file in target_dir.glob("*.json"):
        old_file.unlink()
    previous_payload: dict = {"stocks": []}
    empty_holdings = pd.DataFrame(columns=["symbol"])
    feature_dates = set(features["date"].astype(str).unique())
    for source in sorted(source_dir.glob("*.json")):
        source_payload = json.loads(source.read_text(encoding="utf-8"))
        as_of_date = str(source_payload.get("as_of_date") or source.stem)
        effective_from = str(source_payload.get("effective_from") or as_of_date)
        effective_to = str(source_payload.get("effective_to") or "")
        if as_of_date not in feature_dates:
            continue
        snapshot = features[features["date"].astype(str) == as_of_date].copy()
        candidate_pool = build_candidate_pool(snapshot, universe_rules_cfg, metric_map_cfg, as_of_date)
        selected, changes = build_effective_universe(candidate_pool, previous_payload, empty_holdings, universe_rules_cfg)
        payload = serialize_universe_payload(
            selected=selected,
            changes=changes,
            as_of_date=as_of_date,
            effective_from=effective_from,
            effective_to=effective_to,
            frequency=universe_rules_cfg.get("rebalance_frequency", "monthly"),
            methodology_version=universe_rules_cfg["methodology_version"],
            rebalance_day=True,
        )
        report_payload = universe_report_payload(candidate_pool, selected, changes, payload)
        (target_dir / f"{effective_from}.json").write_text(json.dumps(report_payload, ensure_ascii=False, indent=2), encoding="utf-8")
        previous_payload = payload


def _history_generation_start(history_dir: str | Path, start_date: str, end_date: str) -> str:
    start = pd.Timestamp(start_date)
    end = pd.Timestamp(end_date)
    source_dir = resolve_path(history_dir)
    candidates = [start]
    for source in source_dir.glob("*.json"):
        try:
            payload = json.loads(source.read_text(encoding="utf-8"))
        except Exception:
            continue
        effective_from = pd.Timestamp(payload.get("effective_from") or payload.get("as_of_date") or source.stem)
        as_of_date = pd.Timestamp(payload.get("as_of_date") or source.stem)
        if effective_from >= start and effective_from <= end:
            candidates.append(as_of_date)
    return min(candidates).strftime("%Y-%m-%d")


def _metrics_row(label: str, result, benchmark_metrics: dict) -> dict:
    metrics = dict(result.metrics)
    detailed = result.trades_detailed if result.trades_detailed is not None else pd.DataFrame()
    defensive = detailed[detailed.get("bucket", pd.Series(dtype=object)) == "defensive_dividend"] if not detailed.empty else pd.DataFrame()
    cyclical = detailed[detailed.get("bucket", pd.Series(dtype=object)) == "cyclical_rotation"] if not detailed.empty else pd.DataFrame()
    row = {
        "strategy": label,
        "execution_mode": metrics.get("execution_mode", ""),
        "start_date": "",
        "end_date": "",
        "annual_return": metrics.get("annual_return", metrics.get("cagr", 0.0)),
        "cumulative_return": metrics.get("cumulative_return", 0.0),
        "max_drawdown": metrics.get("max_drawdown", 0.0),
        "sharpe": metrics.get("sharpe", 0.0),
        "calmar": metrics.get("calmar", 0.0),
        "volatility": metrics.get("volatility", 0.0),
        "win_rate": metrics.get("win_rate", 0.0),
        "profit_factor": metrics.get("profit_factor", 0.0),
        "total_trades": metrics.get("total_trades", 0),
        "buy_trades": metrics.get("buy_trades", 0),
        "sell_trades": metrics.get("sell_trades", 0),
        "avg_holding_days": metrics.get("avg_holding_days", 0.0),
        "median_holding_days": metrics.get("median_holding_days", 0.0),
        "avg_daily_exposure": metrics.get("avg_daily_exposure", 0.0),
        "max_daily_exposure": metrics.get("max_daily_exposure", 0.0),
        "exposure_active_days_ratio": metrics.get("exposure_active_days_ratio", 0.0),
        "avg_positions": metrics.get("avg_positions", 0.0),
        "max_positions": metrics.get("max_positions", 0),
        "turnover": metrics.get("turnover", 0.0),
        "total_fees": metrics.get("total_fees", 0.0),
        "total_tax": metrics.get("total_tax", 0.0),
        "realized_pnl": metrics.get("realized_pnl", 0.0),
        "unrealized_pnl": metrics.get("unrealized_pnl", 0.0),
        "benchmark_annual_return": benchmark_metrics["benchmark_annual_return"],
        "excess_annual_return": metrics.get("annual_return", metrics.get("cagr", 0.0)) - benchmark_metrics["benchmark_annual_return"],
        "benchmark_max_drawdown": benchmark_metrics["benchmark_max_drawdown"],
        "information_ratio": 0.0,
        "defensive_trade_count": int(len(defensive)),
        "cyclical_trade_count": int(len(cyclical)),
        "defensive_pnl": float(defensive.get("realized_pnl", pd.Series(dtype=float)).sum()) if not defensive.empty else 0.0,
        "cyclical_pnl": float(cyclical.get("realized_pnl", pd.Series(dtype=float)).sum()) if not cyclical.empty else 0.0,
    }
    return row


def _write_compare_report(metrics_frame: pd.DataFrame, output_dir: Path) -> None:
    lines = ["# combined vs combined_v2 三年回测对比", ""]
    for row in metrics_frame.to_dict(orient="records"):
        lines.extend(
            [
                f"## {row['strategy']}",
                "",
                f"- 年化收益: {row['annual_return']:.2%}",
                f"- 累计收益: {row['cumulative_return']:.2%}",
                f"- 最大回撤: {row['max_drawdown']:.2%}",
                f"- 夏普: {row['sharpe']:.2f}",
                f"- 成交: {int(row['total_trades'])} 笔，买入 {int(row['buy_trades'])}，卖出 {int(row['sell_trades'])}",
                f"- 平均日仓位: {row['avg_daily_exposure']:.2%}",
                f"- 活跃暴露天数占比: {row['exposure_active_days_ratio']:.2%}",
                f"- 平均持仓数量: {row['avg_positions']:.2f}",
                "",
            ]
        )
    v2 = metrics_frame[metrics_frame["strategy"] == "combined_v2"]
    if not v2.empty:
        item = v2.iloc[0]
        passed = bool(
            item["total_trades"] >= 25
            and item["buy_trades"] >= 12
            and item["avg_daily_exposure"] >= 0.15
            and item["exposure_active_days_ratio"] >= 0.30
            and item["avg_positions"] >= 2
        )
        lines.extend(["## combined_v2 最低验收", ""])
        lines.append(f"- 交易密度验收: {'通过' if passed else '未通过'}")
        lines.append(f"- total_trades >= 25: {int(item['total_trades'])}")
        lines.append(f"- buy_trades >= 12: {int(item['buy_trades'])}")
        lines.append(f"- avg_daily_exposure >= 15%: {item['avg_daily_exposure']:.2%}")
        lines.append(f"- exposure_active_days_ratio >= 30%: {item['exposure_active_days_ratio']:.2%}")
        lines.append(f"- avg_positions >= 2: {item['avg_positions']:.2f}")
        if item["max_drawdown"] < -0.18:
            lines.append(f"- **最大回撤 {item['max_drawdown']:.2%} 超过 -18%，需要逐笔拆解。**")
    (output_dir / "compare_combined_vs_v2.md").write_text("\n".join(lines).strip() + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    features = load_backtest_features(args.features_file, args.start_date, args.end_date)
    generation_start = _history_generation_start(args.baseline_historical_universe_dir, args.start_date, args.end_date)
    generation_features = load_backtest_features(args.features_file, generation_start, args.end_date)
    benchmark = clean_benchmark_frame(pd.read_parquet(resolve_path(args.benchmark_file)))
    benchmark = benchmark[(benchmark["date"] >= args.start_date) & (benchmark["date"] <= args.end_date)].copy()
    account_cfg = load_yaml_optional(args.account_config)
    metric_map_cfg = load_yaml(args.metric_map_config)
    baseline_strategy = load_yaml(args.baseline_strategy_config)
    baseline_universe_rules = load_yaml(args.baseline_universe_config)
    v2_strategy = load_yaml(args.v2_strategy_config)
    v2_universe_rules = load_yaml(args.v2_universe_config)
    _generate_v2_history(generation_features, args.baseline_historical_universe_dir, args.v2_historical_universe_dir, v2_universe_rules, metric_map_cfg)

    baseline_engine = BacktestEngine(
        baseline_strategy,
        universe_rules_cfg=baseline_universe_rules,
        account_cfg=account_cfg,
        historical_universe_dir=args.baseline_historical_universe_dir,
        execution_mode=args.execution_mode,
    )
    v2_engine = BacktestEngine(
        v2_strategy,
        universe_rules_cfg=v2_universe_rules,
        account_cfg=account_cfg,
        historical_universe_dir=args.v2_historical_universe_dir,
        execution_mode=args.execution_mode,
    )
    baseline_result = baseline_engine.run(features=features, benchmark=benchmark, bucket="combined")
    v2_result = v2_engine.run(features=features, benchmark=benchmark, bucket="combined")

    baseline_universe, _ = build_universe_funnel(features, args.baseline_historical_universe_dir, baseline_universe_rules, metric_map_cfg)
    v2_universe, v2_scores = build_universe_funnel(features, args.v2_historical_universe_dir, v2_universe_rules, metric_map_cfg)
    output_dir = resolve_path("reports/backtest")
    output_dir.mkdir(parents=True, exist_ok=True)
    write_diagnostic_outputs("baseline", baseline_result, baseline_universe, output_dir=output_dir)
    write_diagnostic_outputs("combined_v2", v2_result, v2_universe, output_dir=output_dir, candidate_scores=v2_scores)

    bm = _benchmark_metrics(benchmark)
    rows = [_metrics_row("baseline", baseline_result, bm), _metrics_row("combined_v2", v2_result, bm)]
    for row in rows:
        row["start_date"] = args.start_date
        row["end_date"] = args.end_date
    metrics_frame = pd.DataFrame(rows)
    metrics_frame.to_csv(output_dir / "compare_combined_vs_v2_metrics.csv", index=False)
    _write_compare_report(metrics_frame, output_dir)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
