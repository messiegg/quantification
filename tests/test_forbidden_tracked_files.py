from __future__ import annotations

from pathlib import Path

import pandas as pd

from scripts.check_forbidden_tracked_files import build_forbidden_tracked_files_check


def test_check_forbidden_tracked_files_detects_data_db_ledger_and_manual_files(tmp_path: Path) -> None:
    frame = build_forbidden_tracked_files_check(
        tracked_files=[
            "data/raw/price_daily.parquet",
            "research.duckdb",
            "data/observation/paper_account.yml",
            "reports/observation/2026-05-04/combined_v2_manual_order_list.csv",
            "reports/observation/2026-05-04/combined_v2_actions.csv",
            ".env",
        ],
        allowlist_path=tmp_path / "missing.yml",
        write_report=False,
    )
    failures = frame[frame["status"] == "FAIL"]
    assert set(failures["actual"]) >= {
        "data/raw/price_daily.parquet",
        "research.duckdb",
        "data/observation/paper_account.yml",
        "reports/observation/2026-05-04/combined_v2_manual_order_list.csv",
        "reports/observation/2026-05-04/combined_v2_actions.csv",
        ".env",
    }


def test_check_forbidden_tracked_files_allows_small_demo_parquet_allowlist() -> None:
    frame = build_forbidden_tracked_files_check(
        tracked_files=[
            "data/demo_case/benchmark_daily.parquet",
            "data/demo_case/daily_features.parquet",
            "data/demo_case/financials_effective.parquet",
        ],
        write_report=False,
    )
    assert frame[frame["status"] == "FAIL"].empty
    allowed = frame[frame["check_name"] == "forbidden pattern allowed by release allowlist"]
    assert len(allowed) == 3


def test_check_forbidden_tracked_files_detects_token_like_secret(tmp_path: Path) -> None:
    secret_file = tmp_path / "provider_config.yml"
    secret_file.write_text("api" + "_key: " + "abcdefghijklmnopqrstuvwxyz" + "123456\n", encoding="utf-8")
    allowlist = tmp_path / "allowlist.yml"
    allowlist.write_text("allowlist: []\n", encoding="utf-8")
    frame = build_forbidden_tracked_files_check(
        tracked_files=[str(secret_file)],
        allowlist_path=allowlist,
        write_report=False,
    )
    failures = frame[frame["status"] == "FAIL"]
    assert "tracked text contains token-like secret" in set(failures["check_name"])


def test_current_forbidden_tracked_files_check_passes() -> None:
    frame = build_forbidden_tracked_files_check(write_report=False)
    assert frame[frame["status"] == "FAIL"].empty


def test_manual_order_list_is_not_tracked_in_current_repo() -> None:
    frame = build_forbidden_tracked_files_check(write_report=False)
    actual = set(frame.get("actual", pd.Series(dtype=str)).astype(str))
    assert "reports/observation/2026-05-04/combined_v2_manual_order_list.csv" not in actual
