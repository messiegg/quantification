from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.backtest import load_backtest_features
from scripts.run_backtest_compare import _benchmark_metrics, _generate_v2_history, _history_generation_start
from src.pipeline.strict_data import clean_benchmark_frame
from src.strategy.backtest_engine import BacktestEngine, BacktestResult
from src.strategy.backtest_reports import build_universe_funnel, write_diagnostic_outputs
from src.utils.config import load_yaml, load_yaml_optional, resolve_path


DEFAULT_START_DATE = "2023-04-03"
DEFAULT_END_DATE = "2026-04-03"
DEFAULT_FEATURES_FILE = "data/features/daily_features"
DEFAULT_BENCHMARK_FILE = "data/raw/benchmark_daily.parquet"
BASELINE_HISTORY_DIR = "data/curated/universe_history"
V2_HISTORY_DIR = "reports/backtest/combined_v2_universe_history"


def load_audit_configs() -> dict:
    return {
        "account": load_yaml_optional("config/account.yml"),
        "metric_map": load_yaml("config/metric_map.yml"),
        "baseline_strategy": load_yaml("config/strategy.yml"),
        "baseline_universe": load_yaml("config/universe_rules.yml"),
        "v2_strategy": load_yaml("config/strategy_v2.yml"),
        "v2_universe": load_yaml("config/universe_rules_v2.yml"),
    }


def load_feature_window(
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    features_file: str = DEFAULT_FEATURES_FILE,
) -> pd.DataFrame:
    return load_backtest_features(features_file, start_date, end_date)


def load_benchmark_window(
    start_date: str = DEFAULT_START_DATE,
    end_date: str = DEFAULT_END_DATE,
    benchmark_file: str = DEFAULT_BENCHMARK_FILE,
) -> pd.DataFrame:
    benchmark = clean_benchmark_frame(pd.read_parquet(resolve_path(benchmark_file)))
    return benchmark[(benchmark["date"] >= start_date) & (benchmark["date"] <= end_date)].copy()


def prepare_v2_history(
    configs: dict,
    end_date: str = DEFAULT_END_DATE,
    features_file: str = DEFAULT_FEATURES_FILE,
    baseline_history_dir: str = BASELINE_HISTORY_DIR,
    v2_history_dir: str = V2_HISTORY_DIR,
    start_date: str = DEFAULT_START_DATE,
) -> None:
    generation_start = _history_generation_start(baseline_history_dir, start_date, end_date)
    features = load_feature_window(generation_start, end_date, features_file)
    _generate_v2_history(
        features,
        baseline_history_dir,
        v2_history_dir,
        configs["v2_universe"],
        configs["metric_map"],
    )


def run_profile(
    profile: str,
    features: pd.DataFrame,
    benchmark: pd.DataFrame,
    configs: dict,
    execution_mode: str = "next_bar",
    historical_universe_dir: str | Path | None = None,
    strategy_cfg: dict | None = None,
    universe_cfg: dict | None = None,
    account_cfg: dict | None = None,
) -> BacktestResult:
    if profile == "baseline":
        strategy = copy.deepcopy(strategy_cfg or configs["baseline_strategy"])
        universe = copy.deepcopy(universe_cfg or configs["baseline_universe"])
        history_dir = historical_universe_dir or BASELINE_HISTORY_DIR
    elif profile.startswith("combined_v2"):
        strategy = copy.deepcopy(strategy_cfg or configs["v2_strategy"])
        universe = copy.deepcopy(universe_cfg or configs["v2_universe"])
        history_dir = historical_universe_dir or V2_HISTORY_DIR
    else:
        raise ValueError(f"unknown profile: {profile}")
    engine = BacktestEngine(
        strategy,
        universe_rules_cfg=universe,
        account_cfg=copy.deepcopy(account_cfg or configs["account"]),
        historical_universe_dir=history_dir,
        execution_mode=execution_mode,
    )
    return engine.run(features=features.copy(), benchmark=benchmark.copy(), bucket="combined")


def metrics_row(profile: str, execution_mode: str, result: BacktestResult, benchmark: pd.DataFrame) -> dict:
    bm = _benchmark_metrics(benchmark)
    metrics = result.metrics
    detailed = result.trades_detailed if result.trades_detailed is not None else pd.DataFrame()
    defensive = detailed[detailed.get("bucket", pd.Series(dtype=object)) == "defensive_dividend"] if not detailed.empty else pd.DataFrame()
    cyclical = detailed[detailed.get("bucket", pd.Series(dtype=object)) == "cyclical_rotation"] if not detailed.empty else pd.DataFrame()
    final_positions = result.final_positions if result.final_positions is not None else pd.DataFrame()
    final_bucket = final_positions.get("bucket", pd.Series(dtype=object)) if not final_positions.empty else pd.Series(dtype=object)
    defensive_unrealized = (
        float(final_positions.loc[final_bucket == "defensive_dividend", "unrealized_pnl"].sum())
        if not final_positions.empty and "unrealized_pnl" in final_positions
        else 0.0
    )
    cyclical_unrealized = (
        float(final_positions.loc[final_bucket == "cyclical_rotation", "unrealized_pnl"].sum())
        if not final_positions.empty and "unrealized_pnl" in final_positions
        else 0.0
    )
    defensive_realized = float(defensive.get("realized_pnl", pd.Series(dtype=float)).sum()) if not defensive.empty else 0.0
    cyclical_realized = float(cyclical.get("realized_pnl", pd.Series(dtype=float)).sum()) if not cyclical.empty else 0.0
    return {
        "profile": profile,
        "execution_mode": execution_mode,
        "annual_return": metrics.get("annual_return", 0.0),
        "cumulative_return": metrics.get("cumulative_return", 0.0),
        "max_drawdown": metrics.get("max_drawdown", 0.0),
        "sharpe": metrics.get("sharpe", 0.0),
        "calmar": metrics.get("calmar", 0.0),
        "volatility": metrics.get("volatility", 0.0),
        "total_trades": metrics.get("total_trades", 0),
        "buy_trades": metrics.get("buy_trades", 0),
        "sell_trades": metrics.get("sell_trades", 0),
        "avg_daily_exposure": metrics.get("avg_daily_exposure", 0.0),
        "max_daily_exposure": metrics.get("max_daily_exposure", 0.0),
        "avg_positions": metrics.get("avg_positions", 0.0),
        "max_positions": metrics.get("max_positions", 0),
        "turnover": metrics.get("turnover", 0.0),
        "total_fees": metrics.get("total_fees", 0.0),
        "total_tax": metrics.get("total_tax", 0.0),
        "total_slippage": metrics.get("total_slippage", 0.0),
        "realized_pnl": metrics.get("realized_pnl", 0.0),
        "unrealized_pnl": metrics.get("unrealized_pnl", 0.0),
        "benchmark_annual_return": bm["benchmark_annual_return"],
        "excess_annual_return": metrics.get("annual_return", 0.0) - bm["benchmark_annual_return"],
        "defensive_pnl": defensive_realized + defensive_unrealized,
        "cyclical_pnl": cyclical_realized + cyclical_unrealized,
        "defensive_trade_count": int(len(defensive)),
        "cyclical_trade_count": int(len(cyclical)),
    }


def write_profile_diagnostics(prefix: str, result: BacktestResult, features: pd.DataFrame, configs: dict, history_dir: str | Path) -> None:
    universe_cfg = configs["v2_universe"] if prefix == "combined_v2" else configs["baseline_universe"]
    universe, scores = build_universe_funnel(features, history_dir, universe_cfg, configs["metric_map"])
    write_diagnostic_outputs(prefix, result, universe, output_dir="reports/backtest", candidate_scores=scores if prefix == "combined_v2" else None)


def ensure_parent(path: str | Path) -> Path:
    resolved = resolve_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def read_json(path: str | Path) -> dict:
    return json.loads(resolve_path(path).read_text(encoding="utf-8"))


def status_from_rows(rows: list[dict]) -> str:
    statuses = {str(row.get("status", "")).upper() for row in rows}
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    return "PASS"


def pct(value: float) -> str:
    return f"{float(value):.2%}"
