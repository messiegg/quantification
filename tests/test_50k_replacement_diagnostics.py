from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts import diagnose_50k_core_failures as diag


def test_replacement_future_returns_are_diagnostic_only(tmp_path: Path) -> None:
    replacements = pd.DataFrame(
        [
            {
                "date": "2024-01-02",
                "buy_symbol": "000001.sz",
                "sell_symbol": "600000.sh",
                "candidate_score": 80,
                "weakest_holding_score": 60,
                "score_gap": 20,
            }
        ]
    )
    features = pd.DataFrame(
        [
            {"date": "2024-01-02", "symbol": "000001.sz", "close": 10},
            {"date": "2024-02-01", "symbol": "000001.sz", "close": 11},
            {"date": "2024-04-02", "symbol": "000001.sz", "close": 12},
            {"date": "2024-01-02", "symbol": "600000.sh", "close": 10},
            {"date": "2024-02-01", "symbol": "600000.sh", "close": 9},
            {"date": "2024-04-02", "symbol": "600000.sh", "close": 8},
        ]
    )

    result = diag.build_replacement_effectiveness(replacements, features)

    assert result.loc[0, "diagnostic_only"] is True
    assert result.loc[0, "opportunity_cost_20d"] > 0
    assert "candidate_future_return_20d" in result.columns
