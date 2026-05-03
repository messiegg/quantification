from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pandas as pd
import pytest
import yaml


ROOT = Path(__file__).resolve().parents[1]


def _required_data_ready() -> bool:
    required = [
        ROOT / "data/raw/price_daily.parquet",
        ROOT / "data/raw/benchmark_daily.parquet",
        ROOT / "data/raw/stock_list.parquet",
        ROOT / "data/curated/stock_valuation_daily.parquet",
        ROOT / "data/curated/industry_daily.parquet",
        ROOT / "data/curated/industry_members_effective.parquet",
        ROOT / "data/raw/financials.parquet",
        ROOT / "data/raw/st_flags.parquet",
        ROOT / "data/curated/market_cap_daily.parquet",
    ]
    return all(path.exists() for path in required)


@pytest.mark.skipif(not _required_data_ready(), reason="strict 2026-04-03 smoke test requires local parquet datasets")
def test_strict_2026_04_03_reaches_refresh_universe_and_breaks_old_listed_days_cap() -> None:
    build = subprocess.run(
        [sys.executable, "scripts/build_features.py", "--as-of-date", "2026-04-03"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert build.returncode == 0, build.stderr[-4000:]

    refresh = subprocess.run(
        [sys.executable, "scripts/refresh_universe.py", "--as-of-date", "2026-04-03", "--preview-only"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert refresh.returncode == 0, refresh.stderr[-4000:]

    latest = pd.read_parquet(ROOT / "data/features/latest_feature_snapshot.parquet")
    metric_map_cfg = yaml.safe_load((ROOT / "config/metric_map.yml").read_text(encoding="utf-8"))
    allowed = set(metric_map_cfg.get("industry_bucket_candidates", {}).keys()) | set(metric_map_cfg.get("industry_bucket_map", {}).keys())
    candidate_industries = latest[latest["industry"].isin(allowed)].copy()

    assert not candidate_industries.empty
    assert pd.to_numeric(candidate_industries["listed_days"], errors="coerce").max() > 1500
    assert pd.to_numeric(candidate_industries["listed_days"], errors="coerce").ge(1500).any()
