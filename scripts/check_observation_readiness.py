#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.report_metadata import git_branch, git_commit, now_utc_iso
from src.utils.config import resolve_path


MANIFEST_PATH = "reports/backtest/release/combined_v2_rc_manifest.json"
VERIFY_CSV_PATH = "reports/backtest/release/combined_v2_rc_verify.csv"
RELEASE_GUARD_CSV_PATH = "reports/backtest/release/release_guard_report.csv"
OUT_JSON = "reports/observation/observation_readiness_check.json"
OUT_MD = "reports/observation/observation_readiness_check.md"
OUT_CSV = "reports/observation/observation_readiness_check.csv"

READY = "READY_FOR_OBSERVATION"
NOT_READY = "NOT_READY"
ALLOWED_MANIFEST_STATUSES = {"WARN", "PASS_CANDIDATE"}
ALLOWED_50K_PROFILES = {"retail_50k_lot_aware", "actual_50k_lot_aware"}
READ_ONLY_INPUTS = [MANIFEST_PATH, VERIFY_CSV_PATH, RELEASE_GUARD_CSV_PATH]


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = resolve_path(path_like)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_csv(path_like: str | Path) -> list[dict[str, Any]]:
    path = resolve_path(path_like)
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write_json(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = resolve_path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")


def _write_csv(path_like: str | Path, rows: list[dict[str, Any]]) -> None:
    path = resolve_path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["check_id", "status", "expected", "actual", "blocking", "recommendation"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{field: row.get(field, "") for field in fields} for row in rows])


def _status_counts(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts = {"PASS": 0, "WARN": 0, "FAIL": 0}
    for row in rows:
        status = str(row.get("status", "")).upper()
        if status in counts:
            counts[status] += 1
    return counts


def _overall_status(rows: list[dict[str, Any]]) -> str:
    counts = _status_counts(rows)
    if counts["FAIL"]:
        return "FAIL"
    if counts["WARN"]:
        return "WARN"
    return "PASS" if rows else "MISSING"


def _drift_rows(rows: list[dict[str, Any]], *, kind: str) -> list[dict[str, Any]]:
    drifted: list[dict[str, Any]] = []
    for row in rows:
        status = str(row.get("status", "")).upper()
        if status == "PASS":
            continue
        check_id = str(row.get("check_id", "")).upper()
        check_name = str(row.get("check_name", "")).lower()
        evidence = str(row.get("evidence", "")).lower()
        if kind == "code" and (check_id.startswith("CODE") or "code hash" in check_name):
            drifted.append(row)
        if kind == "config" and (check_id.startswith("CFG") or evidence.startswith("config/") or "config/" in check_name):
            drifted.append(row)
    return drifted


def _add_check(
    checks: list[dict[str, Any]],
    check_id: str,
    passed: bool,
    expected: Any,
    actual: Any,
    recommendation: str,
    *,
    blocking: bool = True,
) -> None:
    checks.append(
        {
            "check_id": check_id,
            "status": "PASS" if passed else "FAIL",
            "expected": expected,
            "actual": actual,
            "blocking": bool(blocking),
            "recommendation": recommendation,
        }
    )


def build_observation_readiness_check(
    *,
    write_report: bool = True,
    out_json: str | Path = OUT_JSON,
    out_md: str | Path = OUT_MD,
    out_csv: str | Path = OUT_CSV,
) -> dict[str, Any]:
    manifest_path = resolve_path(MANIFEST_PATH)
    verify_path = resolve_path(VERIFY_CSV_PATH)
    guard_path = resolve_path(RELEASE_GUARD_CSV_PATH)
    manifest = _read_json(MANIFEST_PATH)
    verify_rows = _read_csv(VERIFY_CSV_PATH)
    guard_rows = _read_csv(RELEASE_GUARD_CSV_PATH)

    verify_counts = _status_counts(verify_rows)
    guard_counts = _status_counts(guard_rows)
    verify_status = _overall_status(verify_rows)
    guard_status = _overall_status(guard_rows)
    code_drift = _drift_rows(verify_rows, kind="code")
    config_drift = _drift_rows(verify_rows, kind="config")
    manifest_status = str(manifest.get("status", "MISSING")).upper() if manifest else "MISSING"
    account_profile = str(manifest.get("account_profile", "MISSING")) if manifest else "MISSING"

    checks: list[dict[str, Any]] = []
    _add_check(checks, "OBS-FILE-MANIFEST", manifest_path.exists(), "manifest exists", str(manifest_path), "缺少 RC manifest 时暂停 observation。")
    _add_check(checks, "OBS-FILE-VERIFY", verify_path.exists(), "verify csv exists", str(verify_path), "缺少 RC verify 输出时暂停 observation。")
    _add_check(checks, "OBS-FILE-GUARD", guard_path.exists(), "release guard csv exists", str(guard_path), "缺少 release guard 输出时暂停 observation。")
    _add_check(
        checks,
        "OBS-MANIFEST-STATUS",
        manifest_status in ALLOWED_MANIFEST_STATUSES,
        sorted(ALLOWED_MANIFEST_STATUSES),
        manifest_status,
        "manifest status 只能是 WARN 或 PASS_CANDIDATE；未知状态暂停 observation。",
    )
    _add_check(
        checks,
        "OBS-DEFAULT-ACCOUNT",
        account_profile in ALLOWED_50K_PROFILES,
        sorted(ALLOWED_50K_PROFILES),
        account_profile,
        "默认 release/account profile 必须保持 50k lot-aware。",
    )
    _add_check(
        checks,
        "OBS-RC-VERIFY-PASS",
        bool(verify_rows) and verify_status == "PASS",
        "PASS",
        verify_status,
        "RC verify 必须整体 PASS；WARN/FAIL 都需要先解释或重建 RC。",
    )
    _add_check(
        checks,
        "OBS-RC-VERIFY-NO-FAIL",
        verify_counts["FAIL"] == 0,
        0,
        verify_counts["FAIL"],
        "verify FAIL > 0 时暂停 observation。",
    )
    _add_check(
        checks,
        "OBS-RELEASE-GUARD-NO-FAIL",
        bool(guard_rows) and guard_counts["FAIL"] == 0,
        0,
        guard_counts["FAIL"],
        "release guard FAIL > 0 时暂停 observation；WARN 可保留但必须解释。",
    )
    _add_check(
        checks,
        "OBS-CODE-HASH-DRIFT",
        not code_drift,
        "no code drift",
        [row.get("check_id") for row in code_drift] or "none",
        "存在 CODE drift 时暂停 observation，先重建 RC。",
    )
    _add_check(
        checks,
        "OBS-CONFIG-HASH-DRIFT",
        not config_drift,
        "no config drift",
        [row.get("check_id") for row in config_drift] or "none",
        "存在 CONFIG drift 时暂停 observation，先重建 RC。",
    )
    _add_check(
        checks,
        "OBS-SAFETY-BOUNDARY",
        manifest.get("auto_trading_approved") is False
        and manifest.get("broker_integration_enabled") is False
        and manifest.get("llm_decision_allowed") is False,
        "manual-only; no broker; no LLM decisions",
        {
            "auto_trading_approved": manifest.get("auto_trading_approved"),
            "broker_integration_enabled": manifest.get("broker_integration_enabled"),
            "llm_decision_allowed": manifest.get("llm_decision_allowed"),
        },
        "observation smoke check 不能被解释为自动交易批准。",
    )

    blocking_failures = [row for row in checks if row["blocking"] and row["status"] == "FAIL"]
    status = READY if not blocking_failures else NOT_READY
    payload = {
        "generated_at": now_utc_iso(),
        "git_commit": git_commit(),
        "branch": git_branch(),
        "status": status,
        "ready_for_observation": status == READY,
        "release_pass_approved": False,
        "manifest_path": MANIFEST_PATH,
        "verify_csv_path": VERIFY_CSV_PATH,
        "release_guard_csv_path": RELEASE_GUARD_CSV_PATH,
        "manifest_status": manifest_status,
        "default_account_profile": account_profile,
        "rc_verify_status": verify_status,
        "rc_verify_fail_count": verify_counts["FAIL"],
        "release_guard_status": guard_status,
        "release_guard_fail_count": guard_counts["FAIL"],
        "code_hash_drift": bool(code_drift),
        "config_hash_drift": bool(config_drift),
        "checks": checks,
        "not_ready_reasons": blocking_failures,
        "manual_review_required": True,
        "paper_trading_only": True,
        "reads_real_account": False,
        "generates_real_orders": False,
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
        "read_only_inputs": READ_ONLY_INPUTS,
    }
    if write_report:
        _write_json(out_json, payload)
        _write_csv(out_csv, checks)
        _write_md(out_md, payload)
    return payload


def _write_md(path_like: str | Path, payload: dict[str, Any]) -> None:
    path = resolve_path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [
        "# observation readiness smoke check",
        "",
        f"- status: {payload['status']}",
        f"- manifest_status: {payload['manifest_status']}",
        f"- default_account_profile: {payload['default_account_profile']}",
        f"- rc_verify_status: {payload['rc_verify_status']}",
        f"- rc_verify_fail_count: {payload['rc_verify_fail_count']}",
        f"- release_guard_status: {payload['release_guard_status']}",
        f"- release_guard_fail_count: {payload['release_guard_fail_count']}",
        f"- code_hash_drift: {str(payload['code_hash_drift']).lower()}",
        f"- config_hash_drift: {str(payload['config_hash_drift']).lower()}",
        "- manual_review_required: true",
        "- paper_trading_only: true",
        "- release_pass_approved: false",
        "- auto_trading_approved: false",
        "- broker_integration_enabled: false",
        "- llm_decision_allowed: false",
        "",
        "READY_FOR_OBSERVATION only means the existing reports are internally consistent enough for manual observation/paper trading. It is not release PASS and not live-trading approval.",
        "",
        "## checks",
        "",
    ]
    for row in payload["checks"]:
        lines.append(f"- {row['status']} | {row['check_id']} | expected={row['expected']} | actual={row['actual']}")
    lines.extend(["", "## not ready reasons", ""])
    lines.extend([f"- {row['check_id']}: actual={row['actual']}" for row in payload["not_ready_reasons"]] or ["- none"])
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check whether existing combined_v2 reports are ready for manual observation/paper trading.")
    parser.add_argument("--no-write-report", action="store_true")
    args = parser.parse_args()
    payload = build_observation_readiness_check(write_report=not args.no_write_report)
    return 0 if payload["status"] == READY else 1


if __name__ == "__main__":
    raise SystemExit(main())
