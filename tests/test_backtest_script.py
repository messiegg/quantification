from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.backtest import load_backtest_features


def test_load_backtest_features_reads_only_requested_year_partitions(tmp_path: Path) -> None:
    feature_dir = tmp_path / "daily_features"
    feature_dir.mkdir(parents=True, exist_ok=True)

    pd.DataFrame(
        {
            "symbol": ["000001.sz"],
            "date": ["2020-12-31"],
            "stock_q_blended": [None],
        }
    ).to_parquet(feature_dir / "2020.parquet", index=False)

    pd.DataFrame(
        {
            "symbol": ["000001.sz", "000001.sz"],
            "date": ["2021-01-04", "2021-01-05"],
            "stock_q_blended": [10.0, 11.0],
        }
    ).to_parquet(feature_dir / "2021.parquet", index=False)

    loaded = load_backtest_features(str(feature_dir), "2021-01-04", "2021-01-05")

    assert len(loaded) == 2
    assert loaded["date"].tolist() == ["2021-01-04", "2021-01-05"]
    assert loaded["stock_q_blended"].dtype.kind in {"f", "i"}
