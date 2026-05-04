#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.config import resolve_path


DEFAULT_CSV = "reports/backtest/release/post_data_update_worktree_check.csv"
DEFAULT_MD = "reports/backtest/release/post_data_update_worktree_check.md"
LARGE_OR_PRIVATE_SUFFIXES = {
    ".parquet",
    ".duckdb",
    ".sqlite",
    ".sqlite3",
    ".db",
    ".cache",
}
LOCAL_ONLY_NAME_FRAGMENTS = [
    "combined_v2_manual_order_list.csv",
    "combined_v2_actions.csv",
    "combined_v2_1_risk_guard_actions.csv",
]
PAPER_LEDGER_FILES = {
    "data/observation/paper_account.yml",
    "data/observation/paper_trades.csv",
    "data/observation/paper_positions.yml",
}


def _git(args: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )


def _status_paths() -> list[tuple[str, str]]:
    result = _git(["status", "--short", "--untracked-files=all"])
    rows: list[tuple[str, str]] = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        status = line[:2]
        path = line[3:]
        if " -> " in path:
            path = path.split(" -> ", 1)[1]
        rows.append((status, path))
    return rows


def _tracked(path: str) -> bool:
    return bool(_git(["ls-files", "--", path]).stdout.strip())


def _ignored(path: str) -> bool:
    return _git(["check-ignore", "--quiet", "--", path]).returncode == 0


def _size(path: str) -> int:
    file_path = resolve_path(path)
    return int(file_path.stat().st_size) if file_path.exists() and file_path.is_file() else 0


def classify_path(path: str, status_code: str | None = None, tracked_by_git: bool | None = None, ignored_by_git: bool | None = None, size_bytes: int | None = None) -> dict:
    tracked = _tracked(path) if tracked_by_git is None else tracked_by_git
    ignored = _ignored(path) if ignored_by_git is None else ignored_by_git
    size = _size(path) if size_bytes is None else int(size_bytes)
    suffix = Path(path).suffix.lower()
    status = status_code or ""

    should_commit = False
    should_ignore = False
    action = "INVESTIGATE"
    reason = "未匹配到安全提交或本地忽略规则，需要人工检查。"

    if path in PAPER_LEDGER_FILES:
        should_ignore = True
        action = "KEEP_IGNORED_LOCAL_ONLY" if ignored else "ADD_TO_GITIGNORE"
        reason = "真实 paper ledger 必须保持本地 ignored，不提交。"
    elif any(fragment in path for fragment in LOCAL_ONLY_NAME_FRAGMENTS):
        should_ignore = True
        action = "KEEP_IGNORED_LOCAL_ONLY" if ignored else "ADD_TO_GITIGNORE"
        reason = "动作清单或明细 CSV 是本地人工复核产物，不提交公开仓库。"
    elif suffix in LARGE_OR_PRIVATE_SUFFIXES or "/cache/" in path or path.startswith(".cache/"):
        should_ignore = True
        action = "KEEP_LOCAL_DATA" if ignored else "ADD_TO_GITIGNORE"
        reason = "大体量行情、数据库或缓存文件不得提交。"
    elif path == "config/data_sources.yml":
        should_ignore = True
        action = "KEEP_LOCAL_CONFIG" if ignored else "ADD_TO_GITIGNORE"
        reason = "真实 provider 配置可能包含私有路径或 token，不提交。"
    elif path.startswith(("scripts/", "tests/", "docs/")) or path in {"README.md", "config/observation.yml", ".gitignore"}:
        should_commit = True
        action = "COMMIT_CODE_OR_DOC"
        reason = "本轮代码、测试或文档变更，应提交。"
    elif path.startswith(("reports/backtest/", "reports/observation/", "reports/data_update/", "reports/data_gaps/", "reports/universe/", "reports/strict/")):
        should_commit = size <= 1_000_000
        action = "COMMIT_SMALL_REPORT" if should_commit else "KEEP_LOCAL_LARGE_REPORT"
        should_ignore = not should_commit
        reason = "小型审计/观察/数据更新报告可提交；超过 1MB 时保留本地。"
    elif path in {"data_quality/latest.json", "provider_health/latest.json"}:
        should_commit = size <= 200_000
        action = "COMMIT_SMALL_AUDIT_STATE" if should_commit else "KEEP_LOCAL_PROVIDER_STATE"
        should_ignore = not should_commit
        reason = "小型 provider/data quality 状态可作为审计证据提交；不得包含 token。"
    elif path == "config/universe.yml" or path.startswith("data/curated/universe_history/") or path.startswith("data/curated/missing_data/"):
        should_commit = tracked and size <= 500_000
        action = "COMMIT_TRACKED_SMALL_GENERATED_DATA" if should_commit else "KEEP_LOCAL_DATA"
        should_ignore = not tracked
        reason = "已跟踪的小型生成数据状态可同步；不包含 parquet/database/cache。"

    return {
        "file_path": path,
        "status_code": status,
        "tracked_by_git": tracked,
        "ignored_by_git": ignored,
        "size_bytes": size,
        "should_commit": should_commit,
        "should_ignore": should_ignore,
        "action": action,
        "reason": reason,
    }


def build_post_data_update_worktree_check(
    output_csv: str | Path = DEFAULT_CSV,
    output_md: str | Path = DEFAULT_MD,
    write_report: bool = True,
) -> pd.DataFrame:
    rows = [classify_path(path, status_code=status) for status, path in _status_paths()]
    frame = pd.DataFrame(
        rows,
        columns=[
            "file_path",
            "status_code",
            "tracked_by_git",
            "ignored_by_git",
            "size_bytes",
            "should_commit",
            "should_ignore",
            "action",
            "reason",
        ],
    )
    if write_report:
        csv_path = resolve_path(output_csv)
        md_path = resolve_path(output_md)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
        investigate = 0 if frame.empty else int((frame["action"] == "INVESTIGATE").sum())
        lines = [
            "# post data update worktree check",
            "",
            f"- file_count: {len(frame)}",
            f"- investigate_count: {investigate}",
            "",
            "## files",
            "",
        ]
        for row in frame.to_dict(orient="records"):
            lines.append(
                f"- {row['action']} | {row['file_path']} | status={row['status_code']} | tracked={row['tracked_by_git']} | ignored={row['ignored_by_git']} | {row['reason']}"
            )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Classify post-data-update dirty worktree files.")
    parser.add_argument("--write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frame = build_post_data_update_worktree_check(write_report=args.write_report)
    return 1 if (not frame.empty and (frame["action"] == "INVESTIGATE").any()) else 0


if __name__ == "__main__":
    raise SystemExit(main())
