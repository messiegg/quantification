from __future__ import annotations

from pathlib import Path

from scripts import check_post_data_update_worktree as worktree
from scripts import check_report_path_sanitization as sanitize


def test_report_path_sanitization_detects_local_absolute_path(tmp_path: Path) -> None:
    report = tmp_path / "report.md"
    report.write_text("本地文件: /Users/meseg/private.csv\n", encoding="utf-8")
    frame = sanitize.build_report_path_sanitization_check(
        scan_globs=[str(report)],
        output_csv=tmp_path / "san.csv",
        output_md=tmp_path / "san.md",
        write_report=False,
    )
    assert "FAIL" in set(frame["status"])


def test_report_path_sanitization_requires_profile_compare_when_referenced(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "observation" / "2026-05-04"
    report_dir.mkdir(parents=True)
    summary = report_dir / "observation_summary.md"
    summary.write_text("风险限制阻断差异见 profile_compare.md。\n", encoding="utf-8")
    frame = sanitize.build_report_path_sanitization_check(
        scan_globs=[str(summary)],
        output_csv=tmp_path / "san.csv",
        output_md=tmp_path / "san.md",
        write_report=False,
    )
    matched = frame[frame["check_name"] == "profile_compare_reference_exists"]
    assert not matched.empty
    assert set(matched["status"]) == {"FAIL"}


def test_report_path_sanitization_passes_clean_relative_reports(tmp_path: Path) -> None:
    report_dir = tmp_path / "reports" / "observation" / "2026-05-04"
    report_dir.mkdir(parents=True)
    summary = report_dir / "observation_summary.md"
    summary.write_text("本地文件: reports/observation/2026-05-04/combined_v2_manual_order_list.csv\n", encoding="utf-8")
    frame = sanitize.build_report_path_sanitization_check(
        scan_globs=[str(summary)],
        output_csv=tmp_path / "san.csv",
        output_md=tmp_path / "san.md",
        write_report=False,
    )
    assert set(frame["status"]) == {"PASS"}


def test_post_data_update_worktree_classifies_local_only_and_large_files() -> None:
    manual = worktree.classify_path(
        "reports/observation/2026-05-04/combined_v2_manual_order_list.csv",
        status_code="??",
        tracked_by_git=False,
        ignored_by_git=True,
        size_bytes=120,
    )
    parquet = worktree.classify_path(
        "data/raw/price_daily.parquet",
        status_code="??",
        tracked_by_git=False,
        ignored_by_git=False,
        size_bytes=10_000_000,
    )
    assert manual["action"] == "KEEP_IGNORED_LOCAL_ONLY"
    assert manual["should_commit"] is False
    assert parquet["action"] == "ADD_TO_GITIGNORE"
    assert parquet["should_ignore"] is True
