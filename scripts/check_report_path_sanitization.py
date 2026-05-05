#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path
from glob import glob

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.config import resolve_path


DEFAULT_SCAN_GLOBS = [
    "reports/observation/2026-05-04/*.md",
    "reports/observation/2026-05-04/*.json",
    "reports/backtest/audit/*.md",
    "reports/backtest/release/*.md",
    "reports/data_update/**/*.md",
    "reports/data_update/**/*.json",
]
DEFAULT_CSV = "reports/backtest/audit/report_path_sanitization_check.csv"
DEFAULT_MD = "reports/backtest/audit/report_path_sanitization_check.md"

LOCAL_PATH_PATTERNS = [
    ("/Users/", "local macOS user path"),
    ("/private/", "local private path"),
    ("C:\\Users\\", "local Windows user path"),
]
SECRET_PATTERN = re.compile(
    r"(?i)(token|secret|password|api[_-]?key)\s*[:=]\s*['\"]?(?!false\b|true\b|null\b|missing\b|redacted\b|present\b)[A-Za-z0-9_\-]{20,}"
)


def _relative(path: Path) -> str:
    try:
        return path.relative_to(ROOT).as_posix()
    except ValueError:
        return path.as_posix()


def _scan_files(scan_globs: list[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in scan_globs:
        raw = Path(pattern)
        if raw.is_absolute():
            matches = [Path(item) for item in glob(pattern, recursive=True)]
        else:
            matches = list(resolve_path(".").glob(pattern))
        files.extend(path for path in matches if path.is_file())
    return sorted(set(files))


def _row(file_path: str, check_name: str, status: str, matched_text: str, recommendation: str) -> dict:
    return {
        "file_path": file_path,
        "check_name": check_name,
        "status": status,
        "matched_text": matched_text,
        "recommendation": recommendation,
    }


def _redact_secret_evidence(text: str) -> str:
    return re.sub(r"([:=]\s*['\"]?).*", r"\1<REDACTED>", text)


def build_report_path_sanitization_check(
    scan_globs: list[str] | None = None,
    output_csv: str | Path = DEFAULT_CSV,
    output_md: str | Path = DEFAULT_MD,
    write_report: bool = True,
) -> pd.DataFrame:
    rows: list[dict] = []
    files = _scan_files(scan_globs or DEFAULT_SCAN_GLOBS)
    for path in files:
        rel = _relative(path)
        text = path.read_text(encoding="utf-8", errors="replace")
        failures = 0
        for needle, name in LOCAL_PATH_PATTERNS:
            if needle in text:
                failures += 1
                rows.append(
                    _row(
                        rel,
                        name,
                        "FAIL",
                        needle,
                        "公开报告使用 repo-relative path，不得包含本机绝对路径。",
                    )
                )
        for match in SECRET_PATTERN.finditer(text):
            failures += 1
            rows.append(
                _row(
                    rel,
                    "token-like secret pattern",
                    "FAIL",
                    _redact_secret_evidence(match.group(0)[:64]),
                    "报告不得包含 token、password、secret 或 API key 原文。",
                )
            )
        if path.name == "observation_summary.md" and "profile_compare.md" in text:
            compare_path = path.parent / "profile_compare.md"
            if compare_path.exists():
                rows.append(
                    _row(
                        rel,
                        "profile_compare_reference_exists",
                        "PASS",
                        "profile_compare.md",
                        "summary 引用的 profile_compare.md 已存在。",
                    )
                )
            else:
                failures += 1
                rows.append(
                    _row(
                        rel,
                        "profile_compare_reference_exists",
                        "FAIL",
                        "profile_compare.md",
                        "summary 不得引用未提交或不存在的 profile_compare.md。",
                    )
                )
        if failures == 0:
            rows.append(_row(rel, "path_and_secret_sanitized", "PASS", "", "未发现本地绝对路径或疑似 secret。"))

    frame = pd.DataFrame(rows, columns=["file_path", "check_name", "status", "matched_text", "recommendation"])
    if write_report:
        csv_path = resolve_path(output_csv)
        md_path = resolve_path(output_md)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
        overall = "FAIL" if (frame["status"] == "FAIL").any() else "PASS"
        lines = [
            "# report path sanitization check",
            "",
            f"- overall_status: {overall}",
            f"- scanned_files: {len(files)}",
            f"- fail_count: {int((frame['status'] == 'FAIL').sum())}",
            "",
            "## checks",
            "",
        ]
        for row in frame.to_dict(orient="records"):
            lines.append(
                f"- {row['status']} | {row['file_path']} | {row['check_name']} | matched={row['matched_text'] or 'none'} | {row['recommendation']}"
            )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check committed reports for local absolute paths and obvious secrets.")
    parser.add_argument("--write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frame = build_report_path_sanitization_check(write_report=args.write_report)
    return 1 if (frame["status"] == "FAIL").any() else 0


if __name__ == "__main__":
    raise SystemExit(main())
