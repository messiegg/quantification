#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_forbidden_tracked_files import build_forbidden_tracked_files_check
from scripts.check_observation_gate_consistency import FORBIDDEN_ACTIVE_PHRASES, build_observation_gate_consistency_check
from scripts.check_release_sync_consistency import build_release_sync_consistency_check
from scripts.check_report_freshness import build_report_freshness_check
from scripts.check_report_path_sanitization import build_report_path_sanitization_check
from scripts.verify_combined_v2_rc import MANIFEST_PATH, _manifest_hash_map, verify_release_candidate
from src.utils.config import resolve_path


DEFAULT_AS_OF_DATE = "2026-05-04"
DEFAULT_CSV = "reports/backtest/release/release_guard_report.csv"
DEFAULT_MD = "reports/backtest/release/release_guard_report.md"
PAPER_LEDGER_FILES = [
    "data/observation/paper_account.yml",
    "data/observation/paper_trades.csv",
    "data/observation/paper_positions.yml",
]
MANUAL_ORDER_PATTERNS = [
    "reports/observation/*/combined_v2_manual_order_list.csv",
    "reports/observation/*/combined_v2_actions.csv",
    "reports/observation/*/combined_v2_1_risk_guard_actions.csv",
]


def _sha256_path(path_like: str | Path) -> str:
    path = resolve_path(path_like)
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path_like: str | Path) -> dict:
    path = resolve_path(path_like)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _git_stdout(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def _git_tracked_paths(pathspecs: list[str]) -> list[str]:
    output = _git_stdout(["ls-files", "--", *pathspecs])
    return [line.strip() for line in output.splitlines() if line.strip()]


def _frame_status(frame: pd.DataFrame) -> str:
    if frame.empty or "status" not in frame.columns:
        return "FAIL"
    statuses = set(frame["status"].astype(str).str.upper())
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    return "PASS"


def _summarize_frame(frame: pd.DataFrame) -> tuple[str, str]:
    status = _frame_status(frame)
    counts = frame["status"].astype(str).str.upper().value_counts().to_dict() if "status" in frame.columns else {}
    return status, f"PASS={counts.get('PASS', 0)} WARN={counts.get('WARN', 0)} FAIL={counts.get('FAIL', 0)}"


def _row(
    rows: list[dict],
    check_id: str,
    check_name: str,
    status: str,
    expected: object,
    actual: object,
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


def _add_frame_check(
    rows: list[dict],
    check_id: str,
    check_name: str,
    frame: pd.DataFrame,
    evidence: str,
    recommendation: str,
) -> None:
    status, actual = _summarize_frame(frame)
    _row(rows, check_id, check_name, status, "no FAIL", actual, evidence, recommendation)


def _check_config_hashes(rows: list[dict]) -> None:
    manifest = _read_json(MANIFEST_PATH)
    manifest_hashes = _manifest_hash_map(manifest)
    for path in ("config/strategy_v2.yml", "config/universe_rules_v2.yml"):
        expected = manifest_hashes.get(path, "")
        actual = _sha256_path(path)
        _row(
            rows,
            f"CFG-HASH-{Path(path).stem}",
            f"{path} hash matches RC manifest",
            "PASS" if expected and expected == actual else "FAIL",
            expected or "hash recorded in RC manifest",
            actual or "missing",
            path,
            "配置 hash 漂移意味着 RC 口径不再冻结，必须停止发布。",
        )


def _check_tracked_local_artifacts(rows: list[dict]) -> None:
    manual_tracked = _git_tracked_paths(MANUAL_ORDER_PATTERNS)
    _row(
        rows,
        "GIT-MANUAL-001",
        "manual order and action files are not tracked",
        "PASS" if not manual_tracked else "FAIL",
        "no tracked manual_order_list/actions files",
        ";".join(manual_tracked) if manual_tracked else "none",
        "git ls-files reports/observation/* action/manual pathspecs",
        "手工清单和 actions 是本地观察产物，不得进入公开提交。",
    )
    ledger_tracked = _git_tracked_paths(PAPER_LEDGER_FILES)
    _row(
        rows,
        "GIT-LEDGER-001",
        "real paper ledger files are not tracked",
        "PASS" if not ledger_tracked else "FAIL",
        "no tracked real paper ledger files",
        ";".join(ledger_tracked) if ledger_tracked else "none",
        "git ls-files data/observation/paper_*",
        "真实 paper ledger 必须保持本地 ignored，只提交 fixtures/observation 示例模板。",
    )


def _check_observation_state(rows: list[dict], as_of_date: str) -> None:
    obs_dir = resolve_path(Path("reports/observation") / as_of_date)
    freshness = _read_json(obs_dir / "data_freshness_report.json")
    summary_path = obs_dir / "observation_summary.md"
    blocked_path = obs_dir / "observation_blocked.md"
    summary = summary_path.read_text(encoding="utf-8") if summary_path.exists() else ""
    blocked_text = blocked_path.read_text(encoding="utf-8") if blocked_path.exists() else ""
    first_line = blocked_text.splitlines()[:1]
    blocked_current = blocked_path.exists() and not bool(first_line and "LEGACY_SUPERSEDED" in first_line[0])
    allowed = freshness.get("allowed_actions") == "observation_report_allowed"
    conflict = allowed and summary_path.exists() and blocked_current
    _row(
        rows,
        "OBS-CONFLICT-001",
        "observation report does not keep allowed and blocked current reports together",
        "PASS" if not conflict else "FAIL",
        "allowed summary without current observation_blocked.md",
        f"allowed={allowed}; summary_exists={summary_path.exists()}; blocked_current={blocked_current}",
        f"reports/observation/{as_of_date}",
        "freshness 允许观察时，当前主路径不得同时保留 blocked 报告。",
    )
    forbidden = [phrase for phrase in FORBIDDEN_ACTIVE_PHRASES if phrase in summary]
    _row(
        rows,
        "OBS-WORDING-001",
        "observation summary has no active execution wording",
        "PASS" if not forbidden else "FAIL",
        "no live execution or auto-order wording",
        "|".join(forbidden) if forbidden else "none",
        f"reports/observation/{as_of_date}/observation_summary.md",
        "观察报告只能作为手工复核材料，不得写成今日实盘执行或自动下单。",
    )


def build_release_guard_report(
    as_of_date: str = DEFAULT_AS_OF_DATE,
    ci: bool = False,
    strict: bool = False,
    write_report: bool = True,
    output_csv: str | Path = DEFAULT_CSV,
    output_md: str | Path = DEFAULT_MD,
) -> pd.DataFrame:
    rows: list[dict] = []

    _row(
        rows,
        "MODE-001",
        "release guard mode",
        "PASS",
        "ci hash-only checks" if ci else "local release checks",
        "ci hash-only checks" if ci else "local release checks",
        "scripts/run_release_guard.py",
        "CI 模式不重跑完整回测，不写行情数据，不生成真实订单。",
    )

    stale_frame = build_report_freshness_check(write_report=write_report)
    _add_frame_check(rows, "RG-001", "report freshness check", stale_frame, "scripts/check_report_freshness.py", "刷新有旧口径或自相矛盾的报告。")

    sync_frame = build_release_sync_consistency_check(write_report=write_report)
    _add_frame_check(rows, "RG-002", "release sync consistency check", sync_frame, "scripts/check_release_sync_consistency.py", "发布同步报告不得含过期结论。")

    path_frame = build_report_path_sanitization_check(write_report=write_report)
    _add_frame_check(rows, "RG-003", "report path sanitization check", path_frame, "scripts/check_report_path_sanitization.py", "公开报告不得包含本机路径或 secret。")

    gate_frame = build_observation_gate_consistency_check(as_of_date=as_of_date, write_report=write_report)
    _add_frame_check(rows, "RG-004", "observation gate consistency check", gate_frame, "scripts/check_observation_gate_consistency.py", "observation allowed/blocked 状态必须一致。")

    rc_frame = verify_release_candidate(mode="hash-only", write_report=write_report)
    _add_frame_check(rows, "RG-005", "combined_v2 RC hash-only verification", rc_frame, "scripts/verify_combined_v2_rc.py --mode hash-only", "CI 只验证 manifest/hash/已提交小型报告，不重跑完整回测。")

    forbidden_frame = build_forbidden_tracked_files_check(write_report=write_report)
    _add_frame_check(rows, "RG-006", "forbidden tracked files check", forbidden_frame, "scripts/check_forbidden_tracked_files.py", "移除大体量数据、真实账本、订单文件或 secret。")

    _check_tracked_local_artifacts(rows)
    _check_observation_state(rows, as_of_date)
    _check_config_hashes(rows)

    frame = pd.DataFrame(
        rows,
        columns=["check_id", "check_name", "status", "expected", "actual", "evidence", "recommendation"],
    )
    if write_report:
        csv_path = resolve_path(output_csv)
        md_path = resolve_path(output_md)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
        overall = "FAIL" if (frame["status"] == "FAIL").any() else "WARN" if (frame["status"] == "WARN").any() else "PASS"
        lines = [
            "# release guard report",
            "",
            f"- overall_status: {overall}",
            f"- as_of_date: {as_of_date}",
            f"- mode: {'ci' if ci else 'local'}",
            f"- strict: {str(strict).lower()}",
            f"- fail_count: {int((frame['status'] == 'FAIL').sum())}",
            f"- warn_count: {int((frame['status'] == 'WARN').sum())}",
            "",
            "## checks",
            "",
        ]
        for row in frame.to_dict(orient="records"):
            lines.append(
                f"- {row['status']} | {row['check_id']} | {row['check_name']} | actual={row['actual']} | evidence={row['evidence']} | {row['recommendation']}"
            )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run combined_v2 observation release guard checks.")
    parser.add_argument("--ci", action="store_true", help="Run CI-safe hash-only release checks.")
    parser.add_argument("--as-of-date", default=DEFAULT_AS_OF_DATE)
    parser.add_argument("--strict", action="store_true", help="Treat WARN as failing.")
    parser.add_argument("--write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frame = build_release_guard_report(
        as_of_date=args.as_of_date,
        ci=args.ci,
        strict=args.strict,
        write_report=args.write_report,
    )
    if (frame["status"] == "FAIL").any():
        return 1
    if args.strict and (frame["status"] == "WARN").any():
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
