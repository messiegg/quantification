#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
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
OBSERVATION_FORBIDDEN_ACTIVE_PHRASES = [
    "今日实盘执行",
    "今日下单",
    "允许自动下单",
    "自动下单: 允许",
    "自动下单：允许",
    "auto_order_allowed: true",
    "真实订单已生成",
]
STALE_BLOCKED_PATTERNS = [
    "STALE_DATA_BLOCKED",
    "data_max_date: 2026-04-03",
    '"data_max_date": "2026-04-03"',
    "stale_trading_days: 18",
    '"stale_trading_days": 18',
    "action_allowed: false",
    '"action_allowed": false',
]


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(ROOT))
    except ValueError:
        return str(path)


def _is_legacy_superseded(text: str) -> bool:
    first_line = text.splitlines()[:1]
    return bool(first_line and "LEGACY_SUPERSEDED" in first_line[0])


def _row(file_path: str, check_name: str, status: str, matched_text: str, recommendation: str) -> dict:
    return {
        "file_path": file_path,
        "check_name": check_name,
        "status": status,
        "matched_text": matched_text,
        "recommendation": recommendation,
    }


def _json_optional(path_like: str | Path) -> dict:
    path = resolve_path(path_like)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _git_ignored(path_like: str | Path) -> bool:
    rel = _relative(resolve_path(path_like))
    import subprocess

    result = subprocess.run(["git", "check-ignore", "--quiet", "--", rel], cwd=resolve_path("."), check=False)
    return result.returncode == 0


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
    include_observation_gate: bool = True,
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

    if include_observation_gate:
        obs_dir = resolve_path("reports/observation/2026-05-04")
        freshness = _json_optional(obs_dir / "data_freshness_report.json")
        manifest = _json_optional(obs_dir / "observation_run_manifest.json")
        summary_path = obs_dir / "observation_summary.md"
        blocked_path = obs_dir / "observation_blocked.md"
        manual_path = obs_dir / "combined_v2_manual_order_list.csv"
    else:
        freshness = {}
        manifest = {}
        summary_path = resolve_path("reports/observation/2026-05-04/observation_summary.md")
        blocked_path = resolve_path("reports/observation/2026-05-04/observation_blocked.md")
        manual_path = resolve_path("reports/observation/2026-05-04/combined_v2_manual_order_list.csv")
    if include_observation_gate and freshness:
        allowed = freshness.get("allowed_actions") == "observation_report_allowed"
        historical_only = freshness.get("allowed_actions") == "historical_review_only"
        blocked_text = blocked_path.read_text(encoding="utf-8") if blocked_path.exists() else ""
        blocked_legacy = _is_legacy_superseded(blocked_text) if blocked_text else False
        blocked_current = blocked_path.exists() and not blocked_legacy
        stale_blocked_matches = [pattern for pattern in STALE_BLOCKED_PATTERNS if pattern in blocked_text]
        if allowed:
            rows.append(
                _row(
                    _relative(blocked_path),
                    "observation_gate_allowed_no_current_blocked",
                    "FAIL" if blocked_current else "PASS",
                    "observation_blocked.md current" if blocked_current else "",
                    "freshness 允许观察时，不得保留未标记 legacy 的 STALE_DATA_BLOCKED 主报告。",
                )
            )
            rows.append(
                _row(
                    _relative(blocked_path),
                    "observation_gate_allowed_no_stale_blocked_content",
                    "FAIL" if blocked_current and stale_blocked_matches else "PASS",
                    "|".join(stale_blocked_matches) if stale_blocked_matches else "",
                    "freshness 允许观察时，当前主路径不得残留旧 blocked 内容；历史文件必须第一行标记 LEGACY_SUPERSEDED。",
                )
            )
            rows.append(
                _row(
                    _relative(summary_path),
                    "observation_gate_allowed_summary_exists",
                    "PASS" if summary_path.exists() else "FAIL",
                    "summary missing" if not summary_path.exists() else "",
                    "freshness 允许观察时必须生成 observation_summary.md。",
                )
            )
            rows.append(
                _row(
                    _relative(obs_dir / "observation_run_manifest.json"),
                    "observation_gate_allowed_manifest",
                    "PASS" if manifest.get("action_allowed") is True else "FAIL",
                    str(manifest.get("action_allowed")),
                    "manifest 必须以本次允许观察结果为准。",
                )
            )
        elif historical_only:
            rows.append(
                _row(
                    _relative(summary_path),
                    "observation_gate_blocked_summary_absent",
                    "PASS" if not summary_path.exists() else "FAIL",
                    "summary exists" if summary_path.exists() else "",
                    "freshness 阻断时不得保留当前 observation_summary.md。",
                )
            )
            rows.append(
                _row(
                    _relative(blocked_path),
                    "observation_gate_blocked_report_exists",
                    "PASS" if blocked_path.exists() else "FAIL",
                    "blocked missing" if not blocked_path.exists() else "",
                    "freshness 阻断时必须生成 observation_blocked.md。",
                )
            )
            rows.append(
                _row(
                    _relative(manual_path),
                    "observation_gate_blocked_manual_absent",
                    "PASS" if not manual_path.exists() else "FAIL",
                    "manual exists" if manual_path.exists() else "",
                    "freshness 阻断时不得生成手工清单。",
                )
            )
    if include_observation_gate and summary_path.exists():
        summary = summary_path.read_text(encoding="utf-8")
        market_closed = bool(freshness.get("market_closed_as_of_date")) if freshness else False
        if market_closed:
            rows.append(
                _row(
                    _relative(summary_path),
                    "observation_summary_market_closed_marker",
                    "PASS" if "MARKET_CLOSED_AS_OF_DATE" in summary else "FAIL",
                    "MARKET_CLOSED_AS_OF_DATE" if "MARKET_CLOSED_AS_OF_DATE" in summary else "",
                    "非交易日 observation_summary.md 必须显式标记市场关闭。",
                )
            )
        for phrase in OBSERVATION_FORBIDDEN_ACTIVE_PHRASES:
            if phrase in summary:
                rows.append(
                    _row(
                        _relative(summary_path),
                        "observation_summary_active_execution_phrase",
                        "FAIL",
                        phrase,
                        "观察报告不得包含实盘执行或自动执行措辞。",
                    )
                )
    if include_observation_gate and manual_path.exists():
        rows.append(
            _row(
                _relative(manual_path),
                "observation_manual_list_gitignored",
                "PASS" if _git_ignored(manual_path) else "FAIL",
                "" if _git_ignored(manual_path) else "not ignored",
                "manual_order_list 是本地人工复核产物，必须保持 gitignored。",
            )
        )

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
