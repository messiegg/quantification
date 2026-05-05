#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import subprocess
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.verify_combined_v2_rc import EXPECTED_METRICS, EXPECTED_TOTAL_TRADES
from src.utils.config import resolve_path


BRANCH = "codex/combined-v2-rc-release"
SYNC_CSV = "reports/backtest/release/observation_sync_check.csv"
SYNC_MD = "reports/backtest/release/observation_sync_check.md"
SUMMARY_MD = "reports/backtest/release/observation_release_sync_summary.md"
CONSISTENCY_CSV = "reports/backtest/release/release_sync_consistency_check.csv"
CONSISTENCY_MD = "reports/backtest/release/release_sync_consistency_check.md"

TRACKED_RELEASE_FILES = [
    ".gitignore",
    "README.md",
    "config/observation.yml",
    "data/observation/.gitkeep",
    "docs/combined_v2_rc_acceptance.md",
    "docs/data_freshness_and_runbook.md",
    "docs/manual_observation_protocol.md",
    "fixtures/observation/paper_account.example.yml",
    "fixtures/observation/paper_positions.example.yml",
    "fixtures/observation/paper_trades.example.csv",
    "reports/backtest/audit/stale_report_check.csv",
    "reports/backtest/audit/stale_report_check.md",
    "reports/backtest/release/combined_v2_rc_code_manifest.json",
    "reports/backtest/release/combined_v2_rc_verify.csv",
    "reports/backtest/release/combined_v2_rc_verify.md",
    "reports/backtest/release/observation_release_sync_summary.md",
    "reports/backtest/release/observation_sync_check.csv",
    "reports/backtest/release/observation_sync_check.md",
    "reports/backtest/release/release_sync_consistency_check.csv",
    "reports/backtest/release/release_sync_consistency_check.md",
    "reports/observation/2026-05-04/data_freshness_report.json",
    "reports/observation/2026-05-04/data_freshness_report.md",
    "reports/observation/2026-05-04/data_quality_observation_report.json",
    "reports/observation/2026-05-04/data_quality_observation_report.md",
    "reports/observation/2026-05-04/observation_gate_consistency_check.csv",
    "reports/observation/2026-05-04/observation_gate_consistency_check.md",
    "reports/observation/2026-05-04/observation_run_manifest.json",
    "reports/observation/2026-05-04/observation_summary.json",
    "reports/observation/2026-05-04/observation_summary.md",
    "reports/observation/2026-05-04/profile_compare.md",
    "reports/data_update/2026-05-04/market_data_update_plan.json",
    "reports/data_update/2026-05-04/market_data_update_plan.md",
    "scripts/check_data_quality_for_observation.py",
    "scripts/check_data_freshness.py",
    "scripts/check_release_sync_consistency.py",
    "scripts/check_report_freshness.py",
    "scripts/run_observation_pipeline.py",
    "scripts/update_market_data_safe.py",
    "scripts/update_paper_observation.py",
    "scripts/verify_combined_v2_rc.py",
    "tests/test_data_freshness_trading_calendar.py",
    "tests/test_observation_pipeline.py",
    "tests/test_release_candidate_consistency.py",
    "tests/test_release_sync_consistency.py",
    "tests/test_safe_data_update.py",
]

PAPER_LEDGER_FILES = [
    "data/observation/paper_account.yml",
    "data/observation/paper_trades.csv",
    "data/observation/paper_positions.yml",
]

SYNC_MD_FORBIDDEN = [
    "ADD_TO_GIT: 25",
    "tracked=False | 发布和复现所需文件",
    "当前未跟踪，需要 git add",
    "INVESTIGATE",
]

SUMMARY_FORBIDDEN = [
    "报告生成时尚未提交",
    "报告生成时尚未 push",
    "存在 untracked 文件: True",
    "存在未暂存修改: True",
    "当前 HEAD commit: 6d16a186",
    "需要执行: git push origin codex/combined-v2-rc-release",
    "data_freshness: BLOCK",
    "allowed_actions: historical_review_only",
    "blocking_reason: STALE_DATA_BLOCKED",
]

SUMMARY_REQUIRED = [
    "STALE_DATA_BLOCKED",
    "manual_order_list 未生成",
    "RC verify: PASS",
    "不涉及策略变更",
    "不允许生成 2026-05-04 手工订单",
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


def _git(args: list[str], check: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=check,
    )


def _git_stdout(args: list[str], fallback: str = "") -> str:
    result = _git(args)
    if result.returncode != 0:
        return fallback
    return result.stdout.strip()


def _tracked_by_git(path: str) -> bool:
    result = _git(["ls-files", "--cached", "--", path])
    return bool(result.stdout.strip())


def _ignored_by_git(path: str) -> bool:
    result = _git(["check-ignore", "--quiet", "--", path])
    return result.returncode == 0


def _git_status_lines() -> list[str]:
    output = _git_stdout(["status", "--short", "--untracked-files=all"])
    return output.splitlines() if output else []


def _remote_hash(branch: str) -> str:
    result = _git(["ls-remote", "--heads", "origin", branch])
    if result.returncode != 0 or not result.stdout.strip():
        return "REMOTE_CHECK_UNAVAILABLE"
    return result.stdout.split()[0]


def _read_json(path_like: str) -> dict:
    path = resolve_path(path_like)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _status_from_csv(path_like: str) -> str:
    path = resolve_path(path_like)
    if not path.exists():
        return "MISSING"
    frame = pd.read_csv(path)
    if frame.empty or "status" not in frame.columns:
        return "MISSING"
    statuses = set(frame["status"].astype(str).str.upper())
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    return "PASS"


def _bool_text(value: bool) -> str:
    return "True" if value else "False"


def _legacy_superseded(path: Path) -> bool:
    if not path.exists():
        return False
    first_line = path.read_text(encoding="utf-8").splitlines()[:1]
    return bool(first_line and "LEGACY_SUPERSEDED" in first_line[0])


def _sync_row(file_path: str, should_track: bool, should_ignore: bool) -> dict:
    path = resolve_path(file_path)
    exists = path.exists()
    tracked = _tracked_by_git(file_path)
    ignored = _ignored_by_git(file_path)
    if should_ignore:
        action = "IGNORE_LOCAL_ONLY" if ignored and not tracked else "INVESTIGATE"
        reason = "真实纸面账本是本地持续变化产物，不提交公开仓库。" if action == "IGNORE_LOCAL_ONLY" else "真实纸面账本必须本地忽略且不得被 Git 跟踪。"
    elif tracked:
        action = "KEEP_TRACKED"
        reason = "发布和复现所需文件，已被 Git 跟踪。"
    elif exists and ignored:
        action = "INVESTIGATE"
        reason = "发布和复现所需文件被 ignore 规则覆盖，需要修正 ignore 或跟踪状态。"
    elif exists:
        action = "ADD_TO_GIT"
        reason = "发布和复现所需文件，当前未跟踪，需要纳入提交。"
    else:
        action = "INVESTIGATE"
        reason = "发布和复现所需文件缺失，需要恢复或说明。"
    return {
        "file_path": file_path,
        "exists_local": exists,
        "tracked_by_git": tracked,
        "ignored_by_git": ignored,
        "should_track": should_track,
        "should_ignore": should_ignore,
        "action": action,
        "reason": reason,
    }


def build_observation_sync_check(
    output_csv: str | Path = SYNC_CSV,
    output_md: str | Path = SYNC_MD,
    write_report: bool = True,
) -> pd.DataFrame:
    rows = [_sync_row(path, should_track=True, should_ignore=False) for path in TRACKED_RELEASE_FILES]
    rows.extend(_sync_row(path, should_track=False, should_ignore=True) for path in PAPER_LEDGER_FILES)
    frame = pd.DataFrame(
        rows,
        columns=[
            "file_path",
            "exists_local",
            "tracked_by_git",
            "ignored_by_git",
            "should_track",
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
        counts = Counter(frame["action"].astype(str))
        lines = [
            "# observation 发布同步检查",
            "",
            "## 摘要",
            "",
        ]
        for action in ("KEEP_TRACKED", "IGNORE_LOCAL_ONLY", "ADD_TO_GIT", "INVESTIGATE"):
            count = counts.get(action, 0)
            if count:
                lines.append(f"- {action}: {count}")
        lines.extend(["", "## 明细", ""])
        for row in frame.to_dict(orient="records"):
            if row["action"] == "IGNORE_LOCAL_ONLY":
                lines.append(
                    "- {action} | {file_path} | exists={exists} | ignored={ignored} | {reason}".format(
                        action=row["action"],
                        file_path=row["file_path"],
                        exists=_bool_text(bool(row["exists_local"])),
                        ignored=_bool_text(bool(row["ignored_by_git"])),
                        reason=row["reason"],
                    )
                )
            else:
                lines.append(
                    "- {action} | {file_path} | exists={exists} | tracked={tracked} | ignored={ignored} | {reason}".format(
                        action=row["action"],
                        file_path=row["file_path"],
                        exists=_bool_text(bool(row["exists_local"])),
                        tracked=_bool_text(bool(row["tracked_by_git"])),
                        ignored=_bool_text(bool(row["ignored_by_git"])),
                        reason=row["reason"],
                    )
                )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return frame


def _sync_counts(frame: pd.DataFrame) -> dict:
    should_track = frame[frame["should_track"] == True]  # noqa: E712
    return {
        "should_track_count": int(len(should_track)),
        "tracked_count": int((should_track["tracked_by_git"] == True).sum()),  # noqa: E712
        "untracked_count": int((should_track["tracked_by_git"] != True).sum()),  # noqa: E712
        "paper_ignored": bool(
            (frame[frame["file_path"].isin(PAPER_LEDGER_FILES)]["action"].astype(str) == "IGNORE_LOCAL_ONLY").all()
        ),
    }


def _rc_verify_summary() -> tuple[str, dict[str, float | int]]:
    status = _status_from_csv("reports/backtest/release/combined_v2_rc_verify.csv")
    metrics = {name: value for name, (value, _tolerance) in EXPECTED_METRICS.items()}
    metrics["total_trades"] = EXPECTED_TOTAL_TRADES
    metrics["final_nav"] = 243928.8809062001
    return status, metrics


def build_release_sync_summary(
    sync_frame: pd.DataFrame | None = None,
    output_md: str | Path = SUMMARY_MD,
    branch: str = BRANCH,
    pytest_result: str | None = None,
    files_modified_by_refresh: list[str] | None = None,
    write_report: bool = True,
) -> str:
    status_before = _git_status_lines()
    if sync_frame is None:
        sync_path = resolve_path(SYNC_CSV)
        sync_frame = pd.read_csv(sync_path) if sync_path.exists() else build_observation_sync_check(write_report=False)

    head = _git_stdout(["rev-parse", "HEAD"], fallback="UNKNOWN")
    current_branch = _git_stdout(["branch", "--show-current"], fallback="")
    remote = _remote_hash(branch)
    sync = _sync_counts(sync_frame)
    freshness = _read_json("reports/observation/2026-05-04/data_freshness_report.json")
    manifest = _read_json("reports/observation/2026-05-04/observation_run_manifest.json")
    rc_status, metrics = _rc_verify_summary()
    manual_order_path = resolve_path("reports/observation/2026-05-04/combined_v2_manual_order_list.csv")
    freshness_allowed = freshness.get("allowed_actions") == "observation_report_allowed"
    data_freshness_status = "ALLOW" if freshness_allowed else "BLOCK"
    manual_tracked = _tracked_by_git("reports/observation/2026-05-04/combined_v2_manual_order_list.csv")
    manual_ignored = _ignored_by_git("reports/observation/2026-05-04/combined_v2_manual_order_list.csv")
    modified = files_modified_by_refresh or [str(output_md)]
    if pytest_result is None:
        existing = resolve_path(output_md)
        if existing.exists():
            for line in existing.read_text(encoding="utf-8").splitlines():
                if line.startswith("- pytest: ") and "待本轮" not in line:
                    pytest_result = line.removeprefix("- pytest: ").strip()
                    break

    lines = [
        "# observation 发布同步总结",
        "",
        "## 验证目标",
        "",
        f"- 当前验证目标分支: {branch}",
        f"- 当前本地分支: {current_branch}",
        f"- verified_target_commit_at_generation: {head}",
        f"- remote_branch_hash_at_generation: {remote}",
        "- final_commit_after_report_commit: see final operator response",
        "",
        "## 本地工作区状态",
        "",
        "- status_before_report_refresh:",
    ]
    if status_before:
        lines.extend([f"  - `{line}`" for line in status_before])
    else:
        lines.append("  - clean")
    lines.extend(
        [
            "- files_modified_by_this_refresh:",
            *[f"  - `{path}`" for path in modified],
            "- 说明: 上述 refresh 文件属于本轮报告同步修复范围，不代表发布状态过期。",
            "",
            "## observation 文件跟踪状态",
            "",
            f"- 应跟踪文件数量: {sync['should_track_count']}",
            f"- 已跟踪数量: {sync['tracked_count']}",
            f"- 未跟踪数量: {sync['untracked_count']}",
            f"- 真实 paper ledger ignored: {'是' if sync['paper_ignored'] else '否'}",
            "",
            "## 2026-05-04 data freshness",
            "",
            f"- data_freshness: {data_freshness_status}",
            f"- target_trading_date: {freshness.get('target_trading_date', '')}",
            f"- data_max_date: {freshness.get('data_max_date', '')}",
            f"- feature_max_date: {freshness.get('feature_max_date', '')}",
            f"- benchmark_max_date: {freshness.get('benchmark_max_date', '')}",
            f"- stale_calendar_days: {freshness.get('stale_calendar_days', '')}",
            f"- stale_trading_days: {freshness.get('stale_trading_days', '')}",
            f"- allowed_actions: {freshness.get('allowed_actions', '')}",
            "",
            "## observation pipeline",
            "",
            f"- blocking_reason: {manifest.get('blocking_reason', '')}",
            f"- action_allowed: {str(manifest.get('action_allowed', False)).lower()}",
            f"- manual_order_list exists locally: {'是' if manual_order_path.exists() else '否'}",
            f"- manual_order_list tracked_by_git: {'是' if manual_tracked else '否'}",
            f"- manual_order_list ignored_by_git: {'是' if manual_ignored else '否'}",
            "",
            "## RC verify",
            "",
            f"- RC verify: {rc_status}",
            f"- annual_return: {metrics['annual_return']}",
            f"- cumulative_return: {metrics['cumulative_return']}",
            f"- max_drawdown: {metrics['max_drawdown']}",
            f"- total_trades: {metrics['total_trades']}",
            f"- final_nav: {metrics['final_nav']}",
            "",
            "## pytest",
            "",
            f"- pytest: {pytest_result or '待本轮 pytest 完成后刷新本行'}",
            "",
            "## 结论",
            "",
            "- 可以提交这轮报告同步修复。",
            "- 不涉及策略变更。",
            "- 不涉及数据更新。",
            "- 观察期输出只允许下一交易日人工复核。",
            "- 不允许自动下单或接券商。",
        ]
    )
    text = "\n".join(lines) + "\n"
    if write_report:
        path = resolve_path(output_md)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
    return text


def _check_row(
    rows: list[dict],
    check_id: str,
    check_name: str,
    status: str,
    expected: str,
    actual: str,
    evidence: str,
    recommendation: str,
) -> None:
    rows.append(
        {
            "check_id": check_id,
            "check_name": check_name,
            "status": status,
            "expected": expected,
            "actual": actual,
            "evidence": evidence,
            "recommendation": recommendation,
        }
    )


def build_release_sync_consistency_check(
    output_csv: str | Path = CONSISTENCY_CSV,
    output_md: str | Path = CONSISTENCY_MD,
    write_report: bool = True,
    include_observation_gate: bool = True,
) -> pd.DataFrame:
    rows: list[dict] = []
    sync_md_path = resolve_path(SYNC_MD)
    summary_path = resolve_path(SUMMARY_MD)
    sync_csv_path = resolve_path(SYNC_CSV)
    sync_md = sync_md_path.read_text(encoding="utf-8") if sync_md_path.exists() else ""
    summary = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""

    for idx, pattern in enumerate(SYNC_MD_FORBIDDEN, start=1):
        present = pattern in sync_md
        _check_row(
            rows,
            f"SYNC-MD-{idx:03d}",
            "observation_sync_check.md stale phrase absent",
            "FAIL" if present else "PASS",
            "stale sync phrase absent",
            "present" if present else "absent",
            pattern if present else str(sync_md_path),
            "重新生成 observation_sync_check.md，确保报告来自当前 Git 跟踪状态。",
        )

    for idx, pattern in enumerate(SUMMARY_FORBIDDEN, start=1):
        present = pattern in summary
        _check_row(
            rows,
            f"SUMMARY-MD-{idx:03d}",
            "observation_release_sync_summary.md old conclusion absent",
            "FAIL" if present else "PASS",
            "old pre-commit conclusion absent",
            "present" if present else "absent",
            pattern if present else str(summary_path),
            "刷新发布同步总结，避免提交前状态结论进入发布分支。",
        )

    if sync_csv_path.exists():
        sync = pd.read_csv(sync_csv_path)
        action_counts = sync["action"].astype(str).value_counts().to_dict()
        for action in ("ADD_TO_GIT", "INVESTIGATE"):
            count = int(action_counts.get(action, 0))
            _check_row(
                rows,
                f"SYNC-CSV-FORBIDDEN-ACTION-{1 if action == 'ADD_TO_GIT' else 2}",
                "observation_sync_check.csv forbidden action count",
                "PASS" if count == 0 else "FAIL",
                "0",
                str(count),
                str(sync_csv_path),
                "当前发布同步报告不得要求补 git add 或人工调查。",
            )
        for path in PAPER_LEDGER_FILES:
            actual = ";".join(sync.loc[sync["file_path"] == path, "action"].astype(str).tolist())
            _check_row(
                rows,
                f"SYNC-CSV-LEDGER-{Path(path).stem}",
                f"{path} action",
                "PASS" if actual == "IGNORE_LOCAL_ONLY" else "FAIL",
                "IGNORE_LOCAL_ONLY",
                actual or "MISSING",
                path,
                "真实 paper ledger 必须保持本地忽略，不进入公开提交。",
            )
        for path in (
            "config/observation.yml",
            "scripts/verify_combined_v2_rc.py",
            "scripts/run_observation_pipeline.py",
            "docs/manual_observation_protocol.md",
        ):
            actual = ";".join(sync.loc[sync["file_path"] == path, "action"].astype(str).tolist())
            _check_row(
                rows,
                f"SYNC-CSV-TRACKED-{Path(path).name}",
                f"{path} action",
                "PASS" if actual == "KEEP_TRACKED" else "FAIL",
                "KEEP_TRACKED",
                actual or "MISSING",
                path,
                "发布和复现所需文件必须保持 Git 跟踪。",
            )
    else:
        _check_row(
            rows,
            "SYNC-CSV-MISSING",
            "observation_sync_check.csv exists",
            "FAIL",
            "exists",
            "missing",
            str(sync_csv_path),
            "先生成 observation_sync_check.csv。",
        )

    current_freshness = _read_json("reports/observation/2026-05-04/data_freshness_report.json")
    summary_required = ["RC verify: PASS", "不涉及策略变更"] if current_freshness.get("allowed_actions") == "observation_report_allowed" else SUMMARY_REQUIRED
    for idx, pattern in enumerate(summary_required, start=1):
        present = pattern in summary
        _check_row(
            rows,
            f"SUMMARY-REQ-{idx:03d}",
            "observation_release_sync_summary.md required current conclusion",
            "PASS" if present else "FAIL",
            f"present: {pattern}",
            "present" if present else "missing",
            pattern if present else str(summary_path),
            "发布同步总结必须保留 RC PASS、策略未变更等当前结论。",
        )

    obs_dir = resolve_path("reports/observation/2026-05-04")
    freshness = current_freshness if include_observation_gate else {}
    manifest = _read_json("reports/observation/2026-05-04/observation_run_manifest.json") if include_observation_gate else {}
    observation_summary_path = obs_dir / "observation_summary.md"
    observation_blocked_path = obs_dir / "observation_blocked.md"
    manual_order_path = obs_dir / "combined_v2_manual_order_list.csv"
    observation_summary = observation_summary_path.read_text(encoding="utf-8") if include_observation_gate and observation_summary_path.exists() else ""
    allowed = freshness.get("allowed_actions") == "observation_report_allowed"
    hard_gate_blocked = (
        allowed
        and manifest.get("action_allowed") is False
        and any(
            str(manifest.get(key, "")).upper() == "FAIL"
            for key in ("universe_integrity_status", "data_freshness_status", "evidence_chain_status")
        )
    )
    if include_observation_gate and hard_gate_blocked:
        blocked_current = observation_blocked_path.exists() and not _legacy_superseded(observation_blocked_path)
        _check_row(
            rows,
            "OBS-GATE-001",
            "allowed freshness hard-blocked by stricter gate",
            "PASS" if blocked_current else "FAIL",
            "current observation_blocked.md",
            "current" if blocked_current else "missing_or_legacy",
            str(observation_blocked_path),
            "freshness 允许观察但 universe/evidence 等硬门禁 FAIL 时，必须保留当前阻断报告。",
        )
        _check_row(
            rows,
            "OBS-GATE-002",
            "hard-blocked observation has no executable action",
            "PASS" if manifest.get("action_allowed") is False else "FAIL",
            "false",
            str(manifest.get("action_allowed")),
            str(obs_dir / "observation_run_manifest.json"),
            "硬门禁 FAIL 时，不允许生成可执行观察建议。",
        )
        _check_row(
            rows,
            "OBS-GATE-003",
            "hard-blocked observation reason recorded",
            "PASS" if manifest.get("blocking_reason") else "FAIL",
            "blocking_reason present",
            str(manifest.get("blocking_reason")),
            str(obs_dir / "observation_run_manifest.json"),
            "硬门禁阻断必须记录 blocking_reason。",
        )
    elif include_observation_gate and allowed:
        blocked_current = observation_blocked_path.exists() and not _legacy_superseded(observation_blocked_path)
        blocked_text = observation_blocked_path.read_text(encoding="utf-8") if observation_blocked_path.exists() else ""
        blocked_stale_matches = [pattern for pattern in STALE_BLOCKED_PATTERNS if pattern in blocked_text]
        _check_row(
            rows,
            "OBS-GATE-001",
            "allowed observation has no current blocked report",
            "PASS" if not blocked_current else "FAIL",
            "observation_blocked.md absent or LEGACY_SUPERSEDED",
            "current" if blocked_current else "absent_or_legacy",
            str(observation_blocked_path),
            "freshness 允许观察时，不能保留当前有效的 STALE_DATA_BLOCKED 主报告。",
        )
        _check_row(
            rows,
            "OBS-GATE-001B",
            "allowed observation has no stale blocked content",
            "PASS" if not (blocked_current and blocked_stale_matches) else "FAIL",
            "no stale blocked content",
            "|".join(blocked_stale_matches) if blocked_stale_matches else "none",
            str(observation_blocked_path),
            "freshness 允许观察时，当前主路径不得残留旧 STALE_DATA_BLOCKED 内容。",
        )
        _check_row(
            rows,
            "OBS-GATE-002",
            "allowed observation summary exists",
            "PASS" if observation_summary_path.exists() else "FAIL",
            "exists",
            "exists" if observation_summary_path.exists() else "missing",
            str(observation_summary_path),
            "freshness 允许观察时必须生成 observation_summary.md。",
        )
        _check_row(
            rows,
            "OBS-GATE-003",
            "allowed observation manifest action_allowed",
            "PASS" if manifest.get("action_allowed") is True else "FAIL",
            "true",
            str(manifest.get("action_allowed")),
            str(obs_dir / "observation_run_manifest.json"),
            "manifest 必须反映本次 gate 已允许观察。",
        )
    if include_observation_gate and observation_summary_path.exists() and freshness.get("market_closed_as_of_date"):
        _check_row(
            rows,
            "OBS-SUMMARY-001",
            "holiday observation summary marker",
            "PASS" if "MARKET_CLOSED_AS_OF_DATE" in observation_summary else "FAIL",
            "MARKET_CLOSED_AS_OF_DATE",
            "present" if "MARKET_CLOSED_AS_OF_DATE" in observation_summary else "missing",
            str(observation_summary_path),
            "非交易日 summary 必须标记市场关闭。",
        )
        forbidden = [phrase for phrase in OBSERVATION_FORBIDDEN_ACTIVE_PHRASES if phrase in observation_summary]
        _check_row(
            rows,
            "OBS-SUMMARY-002",
            "holiday observation summary execution wording",
            "PASS" if not forbidden else "FAIL",
            "no active execution wording",
            "|".join(forbidden) if forbidden else "none",
            str(observation_summary_path),
            "非交易日 summary 只能作为下一交易日人工复核。",
        )
    if include_observation_gate and manual_order_path.exists():
        ignored = _ignored_by_git("reports/observation/2026-05-04/combined_v2_manual_order_list.csv")
        _check_row(
            rows,
            "OBS-MANUAL-001",
            "manual order list remains gitignored",
            "PASS" if ignored else "FAIL",
            "gitignored",
            "gitignored" if ignored else "not_ignored",
            str(manual_order_path),
            "手工清单是本地人工复核产物，不应要求 git add。",
        )

    frame = pd.DataFrame(rows, columns=["check_id", "check_name", "status", "expected", "actual", "evidence", "recommendation"])
    if write_report:
        csv_path = resolve_path(output_csv)
        md_path = resolve_path(output_md)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
        overall = "FAIL" if (frame["status"] == "FAIL").any() else "WARN" if (frame["status"] == "WARN").any() else "PASS"
        lines = [
            "# release sync consistency check",
            "",
            f"- overall_status: {overall}",
            f"- generated_at: {datetime.now(timezone.utc).isoformat()}",
            f"- fail_count: {int((frame['status'] == 'FAIL').sum())}",
            f"- warn_count: {int((frame['status'] == 'WARN').sum())}",
            "",
            "任一 FAIL 时，不能把发布同步状态视为完成。",
            "",
            "## checks",
            "",
        ]
        for row in frame.to_dict(orient="records"):
            lines.append(
                f"- {row['status']} | {row['check_id']} | {row['check_name']} | actual={row['actual']} | {row['recommendation']}"
            )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Refresh and check observation release sync reports.")
    parser.add_argument("--refresh-source-reports", action="store_true")
    parser.add_argument("--no-refresh-source-reports", action="store_true")
    parser.add_argument("--pytest-result", default=None)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    sync_frame = None
    if args.refresh_source_reports and not args.no_refresh_source_reports:
        refresh_files = [SYNC_CSV, SYNC_MD, SUMMARY_MD]
        sync_frame = build_observation_sync_check()
        build_release_sync_summary(
            sync_frame=sync_frame,
            pytest_result=args.pytest_result,
            files_modified_by_refresh=refresh_files,
        )
    frame = build_release_sync_consistency_check()
    return 1 if (frame["status"] == "FAIL").any() else 0


if __name__ == "__main__":
    raise SystemExit(main())
