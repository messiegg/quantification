#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.config import resolve_path


DEFAULT_SCAN_GLOBS = [
    "reports/backtest/audit/*.md",
    "reports/backtest/attribution/*.md",
    "reports/backtest/controls/*.md",
    "reports/backtest/v2_1/*.md",
    "reports/backtest/release/*.md",
]
DEFAULT_CSV = "reports/backtest/audit/stale_report_check.csv"
DEFAULT_MD = "reports/backtest/audit/stale_report_check.md"
EXCLUDED_NAMES = {"stale_report_check.md", "release_sync_consistency_check.md"}

OLD_RATING_PATTERNS = [
    "最终评级: WARN",
    "lookahead: WARN",
    "旧 9.14%/83 笔已被 PIT 严格口径废弃；当前审计不再要求复现 legacy 指标",
    "最大风险点 - lookahead 审计仍有非确认前视的 WARN",
]
OLD_ATTRIBUTION_PATTERNS = [
    "signal BUY_1: 成交 39，已实现 0.00",
    "signal BUY_2: 成交 4，已实现 0.00",
    "regime neutral: 成交",
    "regime risk_off: 成交",
    "regime risk_on: 成交",
]
REQUIRED_ATTRIBUTION_SECTIONS = [
    "entry signal attribution",
    "exit signal attribution",
    "entry-exit pair attribution",
    "trade realization regime attribution",
    "daily MTM regime attribution",
]
RELEASE_SYNC_STALE_PATTERNS = [
    "ADD_TO_GIT: 25",
    "tracked=False | 发布和复现所需文件",
    "当前未跟踪，需要 git add",
    "报告生成时尚未提交",
    "报告生成时尚未 push",
    "存在 untracked 文件: True",
    "存在未暂存修改: True",
    "当前 HEAD commit: 6d16a186",
]


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _is_legacy_superseded(text: str) -> bool:
    header = "\n".join(text.splitlines()[:8])
    return "LEGACY_SUPERSEDED" in header


def _row(file_path: str, check_name: str, status: str, matched_text: str, recommendation: str) -> dict:
    return {
        "file_path": file_path,
        "check_name": check_name,
        "status": status,
        "matched_text": matched_text,
        "recommendation": recommendation,
    }


def _scan_files(scan_globs: list[str]) -> list[Path]:
    files: list[Path] = []
    for pattern in scan_globs:
        raw = Path(pattern)
        iterator = raw.parent.glob(raw.name) if raw.is_absolute() else resolve_path(".").glob(pattern)
        for path in iterator:
            if path.name in EXCLUDED_NAMES:
                continue
            if path.is_file():
                files.append(path)
    return sorted(set(files))


def build_report_freshness_check(
    scan_globs: list[str] | None = None,
    output_csv: str | Path = DEFAULT_CSV,
    output_md: str | Path = DEFAULT_MD,
    write_report: bool = True,
) -> pd.DataFrame:
    globs = scan_globs or DEFAULT_SCAN_GLOBS
    rows: list[dict] = []
    rating_matches = 0
    attribution_matches = 0
    release_sync_matches = 0
    files = _scan_files(globs)

    for path in files:
        text = path.read_text(encoding="utf-8")
        rel = _relative(path)
        is_legacy = _is_legacy_superseded(text)
        for pattern in OLD_RATING_PATTERNS:
            if pattern in text:
                rating_matches += 1
                rows.append(
                    _row(
                        rel,
                        "old_rating_residue",
                        "PASS" if is_legacy else "FAIL",
                        pattern,
                        "legacy 文件已在顶部标记 LEGACY_SUPERSEDED；当前主报告不得保留旧 WARN 或旧口径句子。"
                        if is_legacy
                        else "刷新当前报告，或仅在明确 LEGACY_SUPERSEDED 的历史文件中保留。",
                    )
                )
        for pattern in OLD_ATTRIBUTION_PATTERNS:
            if pattern in text:
                attribution_matches += 1
                rows.append(
                    _row(
                        rel,
                        "old_attribution_residue",
                        "PASS" if is_legacy else "FAIL",
                        pattern,
                        "legacy 文件已隔离；当前 attribution / regime 主报告不得出现旧 realized-only 行。"
                        if is_legacy
                        else "刷新归因报告，使用 entry/exit/pair 和 daily MTM regime 口径。",
                    )
                )
        if path.name in {"observation_sync_check.md", "observation_release_sync_summary.md"}:
            for pattern in RELEASE_SYNC_STALE_PATTERNS:
                if pattern in text:
                    release_sync_matches += 1
                    rows.append(
                        _row(
                            rel,
                            "release_sync_stale_residue",
                            "FAIL",
                            pattern,
                            "刷新 release sync 报告，禁止把提交前 tracked/untracked/push 状态作为发布结论。",
                        )
                    )

    if rating_matches == 0:
        rows.append(_row("", "old_rating_residue_absent", "PASS", "", "未发现未隔离的旧 WARN 或旧评级句子。"))
    if attribution_matches == 0:
        rows.append(_row("", "old_attribution_residue_absent", "PASS", "", "未发现旧 signal/regime attribution 行。"))
    if release_sync_matches == 0:
        rows.append(_row("", "release_sync_stale_residue_absent", "PASS", "", "未发现 release sync 提交前状态残留。"))

    attribution_path = resolve_path("reports/backtest/attribution/combined_v2_attribution_report.md")
    if attribution_path.exists():
        text = attribution_path.read_text(encoding="utf-8")
        lower = text.lower()
        for section in REQUIRED_ATTRIBUTION_SECTIONS:
            rows.append(
                _row(
                    _relative(attribution_path),
                    f"required_section:{section}",
                    "PASS" if section.lower() in lower else "FAIL",
                    section if section.lower() in lower else "",
                    "combined_v2_attribution_report.md 必须保留新版归因章节。",
                )
            )
    else:
        rows.append(
            _row(
                "reports/backtest/attribution/combined_v2_attribution_report.md",
                "required_section_file",
                "FAIL",
                "",
                "缺少 combined_v2_attribution_report.md，无法确认新版归因章节。",
            )
        )

    prior_fail = any(row["status"] == "FAIL" for row in rows)
    summary_path = resolve_path("reports/backtest/audit/combined_v2_rc_summary.md")
    if prior_fail and summary_path.exists():
        summary = summary_path.read_text(encoding="utf-8")
        if "最终评级: PASS_CANDIDATE" in summary and not _is_legacy_superseded(summary):
            rows.append(
                _row(
                    _relative(summary_path),
                    "rc_summary_rating_guard",
                    "FAIL",
                    "最终评级: PASS_CANDIDATE",
                    "存在 freshness FAIL 时，RC 总结不得仍显示 PASS_CANDIDATE。",
                )
            )

    frame = pd.DataFrame(rows, columns=["file_path", "check_name", "status", "matched_text", "recommendation"])
    if write_report:
        csv_path = resolve_path(output_csv)
        md_path = resolve_path(output_md)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
        status = "FAIL" if (frame["status"] == "FAIL").any() else "WARN" if (frame["status"] == "WARN").any() else "PASS"
        lines = [
            "# stale report check",
            "",
            f"- overall_status: {status}",
            f"- scanned_files: {len(files)}",
            f"- fail_count: {int((frame['status'] == 'FAIL').sum())}",
            f"- warn_count: {int((frame['status'] == 'WARN').sum())}",
            "",
            "## checks",
            "",
        ]
        for row in frame.to_dict(orient="records"):
            target = row["file_path"] or "GLOBAL"
            matched = f"，matched={row['matched_text']}" if row["matched_text"] else ""
            lines.append(f"- {row['status']} | {target} | {row['check_name']}{matched} | {row['recommendation']}")
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check current backtest reports for stale combined_v2 RC residues.")
    parser.add_argument("--output-csv", default=DEFAULT_CSV)
    parser.add_argument("--output-md", default=DEFAULT_MD)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frame = build_report_freshness_check(output_csv=args.output_csv, output_md=args.output_md)
    return 1 if (frame["status"] == "FAIL").any() else 0


if __name__ == "__main__":
    raise SystemExit(main())
