#!/usr/bin/env python3
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.pipeline.strict_data import clean_benchmark_frame
from src.strategy.backtest_engine import BacktestEngine
from src.utils.cli import write_json
from src.utils.config import load_project_configs, resolve_path
from src.utils.storage import read_dataset_flex


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run point-in-time backtests using next-day-open execution.")
    parser.add_argument("--bucket", default="combined", choices=["defensive_dividend", "cyclical_rotation", "combined"], help="Backtest bucket.")
    parser.add_argument("--start-date", required=True, help="Backtest start date.")
    parser.add_argument("--end-date", required=True, help="Backtest end date.")
    parser.add_argument("--features-file", default="data/features/daily_features", help="Daily feature parquet file or partitioned directory.")
    parser.add_argument("--benchmark-file", default="data/raw/benchmark_daily.parquet", help="Benchmark parquet.")
    parser.add_argument("--historical-universe-dir", default="data/curated/universe_history", help="Historical effective universe directory.")
    parser.add_argument("--output-prefix", default="", help="Backtest output prefix.")
    return parser.parse_args()


def load_backtest_features(path_like: str, start_date: str, end_date: str) -> pd.DataFrame:
    path = resolve_path(path_like)
    start_ts = pd.Timestamp(start_date)
    end_ts = pd.Timestamp(end_date)
    if path.is_dir():
        years = range(start_ts.year, end_ts.year + 1)
        frames: list[pd.DataFrame] = []
        for year in years:
            yearly_path = path / f"{year}.parquet"
            if yearly_path.exists():
                frames.append(pd.read_parquet(yearly_path))
        if not frames:
            features = read_dataset_flex(path)
        else:
            features = pd.concat(frames, ignore_index=True, sort=False)
    else:
        features = pd.read_parquet(path)
    if features.empty:
        return features
    dates = pd.to_datetime(features["date"], errors="coerce")
    return features[(dates >= start_ts) & (dates <= end_ts)].copy()


def main() -> int:
    args = parse_args()
    configs = load_project_configs()
    features = load_backtest_features(args.features_file, args.start_date, args.end_date)
    benchmark = clean_benchmark_frame(pd.read_parquet(resolve_path(args.benchmark_file)))
    benchmark = benchmark[(benchmark["date"] >= args.start_date) & (benchmark["date"] <= args.end_date)].copy()

    engine = BacktestEngine(
        configs["strategy"],
        universe_rules_cfg=configs["universe_rules"],
        account_cfg=configs["account"],
        historical_universe_dir=args.historical_universe_dir,
    )
    result = engine.run(features=features, benchmark=benchmark, bucket=args.bucket)

    prefix = args.output_prefix or f"reports/backtests/{args.bucket}_{args.start_date}_{args.end_date}"
    json_path = f"{prefix}.json"
    md_path = f"{prefix}.md"
    payload = {
        "bucket": args.bucket,
        "start_date": args.start_date,
        "end_date": args.end_date,
        "metrics": result.metrics,
        "trade_list": result.trade_list.to_dict(orient="records"),
        "stock_attribution": result.stock_attribution.to_dict(orient="records"),
        "industry_attribution": result.industry_attribution.to_dict(orient="records"),
        "approximate_backtest": result.approximate_backtest,
    }
    write_json(json_path, payload)
    lines = [
        f"# Backtest {args.bucket}",
        "",
        f"- Start: {args.start_date}",
        f"- End: {args.end_date}",
        f"- CAGR: {result.metrics['cagr']:.2%}",
        f"- Max Drawdown: {result.metrics['max_drawdown']:.2%}",
        f"- Win Rate: {result.metrics['win_rate']:.2%}",
        f"- Sharpe: {result.metrics['sharpe']:.2f}",
        f"- Approximate backtest: {'yes' if result.approximate_backtest else 'no'}",
        "",
        "## Trades",
        "",
    ]
    if result.trade_list.empty:
        lines.append("- No trades")
    else:
        for row in result.trade_list.to_dict(orient="records"):
            lines.append(
                f"- {row['signal_date']} -> {row['fill_date']} | {row['symbol']} | {row['action']} | fill={row['fill_price']:.4f} | pnl={row['realized_pnl']:.2f}"
            )
    md_file = resolve_path(md_path)
    md_file.parent.mkdir(parents=True, exist_ok=True)
    md_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
