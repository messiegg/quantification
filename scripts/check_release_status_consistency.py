#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.report_metadata import metadata_header, write_json
from src.utils.config import resolve_path


OUT_JSON = "reports/backtest/release/release_status_consistency.json"
OUT_MD = "reports/backtest/release/release_status_consistency.md"
MANIFEST_JSON = "reports/backtest/release/combined_v2_rc_manifest.json"
MANIFEST_MD = "reports/backtest/release/combined_v2_rc_manifest.md"
RELEASE_GUARD_MD = "reports/backtest/release/release_guard_report.md"
STATUS_VALUES = {"FAIL", "WARN", "PASS_CANDIDATE", "PASS"}
FORBIDDEN_POSITIVE_PHRASES = (
    "automatic trading ready",
    "live trading approved",
    "auto_trading_approved=true",
    "broker_integration_enabled=true",
    "llm_decision_allowed=true",
)


def _read_json(path_like: str | Path) -> dict[str, Any]:
    path = resolve_path(path_like)
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def _read_text(path_like: str | Path) -> str:
    path = resolve_path(path_like)
    return path.read_text(encoding="utf-8") if path.exists() else ""


def _line_status(text: str, keys: tuple[str, ...]) -> str | None:
    for line in text.splitlines():
        stripped = line.strip()
        for key in keys:
            match = re.match(rf"^-?\s*{re.escape(key)}\s*:\s*`?([A-Z_]+)`?", stripped)
            if match and match.group(1) in STATUS_VALUES:
                return match.group(1)
    return None


def _latest_project_status_doc() -> str | None:
    docs = sorted(resolve_path("docs").glob("project_status_*.md"))
    current_docs = []
    for path in docs:
        text = path.read_text(encoding="utf-8")
        if "历史快照" in text.splitlines()[:5]:
            continue
        current_docs.append(path)
    if not current_docs:
        return None
    try:
        return str(current_docs[-1].relative_to(ROOT))
    except ValueError:
        return str(current_docs[-1])


def _expected_status() -> tuple[str, list[dict[str, Any]]]:
    reasons: list[dict[str, Any]] = []
    current_audits = {
        "config_consistency": _read_json("reports/audit/config_consistency.json"),
        "data_freshness": _read_json("reports/audit/data_freshness.json"),
    }
    failed_current = {key: value.get("status") for key, value in current_audits.items() if str(value.get("status", "")).upper() == "FAIL"}
    if failed_current:
        reasons.append({"code": "CORE_AUDIT_FAIL", "actual": failed_current})
        return "FAIL", reasons

    universe = _read_json("reports/audit/universe_integrity.json")
    selected = universe.get("selected_count")
    target = universe.get("target_size")
    if selected is not None and target is not None and int(selected) < int(target):
        reasons.append({"code": "UNIVERSE_BELOW_TARGET", "selected_count": selected, "target_size": target})

    account = _read_json("reports/backtest/account_constraints_report.json")
    for warning in account.get("warnings", []) or []:
        if warning.get("code") == "ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION":
            reasons.append({"code": "ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION", "actual": warning.get("actual")})

    comparison = _read_json("reports/backtest/account_profiles/account_profile_comparison.json")
    retail = next((item for item in comparison.get("profiles", []) or [] if item.get("profile") == "actual_50k_retail"), {})
    retail_ratio = retail.get("executable_raw_buy_ratio")
    if comparison and str(comparison.get("status", "")).upper() == "FAIL":
        reasons.append({"code": "ACCOUNT_PROFILE_COMPARISON_FAIL", "actual": comparison.get("status")})
        return "FAIL", reasons
    if retail_ratio is not None and float(retail_ratio) < 0.25:
        reasons.append({"code": "RETAIL_50K_EXECUTION_RATIO_BELOW_25", "actual": retail_ratio})

    sensitivity = _read_json("reports/backtest/robustness/sensitivity_report.json")
    non_binding = sensitivity.get("non_binding_parameters") or []
    if non_binding:
        reasons.append({"code": "CORE_SENSITIVITY_NON_BINDING", "parameters": non_binding})

    baseline = _read_json("reports/backtest/controls/baseline_comparison.json")
    drags = [
        row.get("comparison_id")
        for row in baseline.get("comparisons", []) or []
        if row.get("module_flag") == "MODULE_MAY_BE_DRAG"
    ]
    if drags:
        reasons.append({"code": "MODULE_MAY_BE_DRAG", "modules": drags})

    evidence = _read_json("reports/observation/2026-05-04/evidence_chain.json")
    if str(evidence.get("status", "")).upper() == "WARN":
        reasons.append({"code": "EVIDENCE_CHAIN_WARN", "actual": "WARN"})

    readiness = _read_json("reports/observation/readiness_report.json")
    if str(readiness.get("status", "")).upper() == "NOT_READY":
        reasons.append({"code": "OBSERVATION_READINESS_NOT_READY", "actual": "NOT_READY"})

    if reasons:
        return "WARN", reasons
    return "PASS_CANDIDATE", reasons


def _check_forbidden_positive_wording(paths: list[str]) -> list[dict[str, Any]]:
    violations: list[dict[str, Any]] = []
    for path in paths:
        text = _read_text(path)
        for line_no, line in enumerate(text.splitlines(), start=1):
            lower = line.lower()
            if "production ready" in lower and "not production ready" not in lower:
                violations.append({"code": "FORBIDDEN_PRODUCTION_READY_WORDING", "path": path, "line": line_no, "text": line.strip()})
            for phrase in FORBIDDEN_POSITIVE_PHRASES:
                if phrase in lower:
                    violations.append({"code": "FORBIDDEN_RELEASE_APPROVAL_WORDING", "path": path, "line": line_no, "phrase": phrase})
    return violations


def build_release_status_consistency_report(write_report: bool = True) -> dict[str, Any]:
    manifest = _read_json(MANIFEST_JSON)
    expected, reasons = _expected_status()
    checked_files = [
        MANIFEST_JSON,
        MANIFEST_MD,
        RELEASE_GUARD_MD,
        "README.md",
    ]
    latest_doc = _latest_project_status_doc()
    if latest_doc:
        checked_files.append(latest_doc)

    observed: list[dict[str, Any]] = []
    manifest_status = str(manifest.get("status", "MISSING")).upper()
    observed.append({"path": MANIFEST_JSON, "field": "status", "status": manifest_status})
    md_status = _line_status(_read_text(MANIFEST_MD), ("status",))
    observed.append({"path": MANIFEST_MD, "field": "status", "status": md_status or "MISSING"})
    guard_status = _line_status(_read_text(RELEASE_GUARD_MD), ("overall_status",))
    observed.append({"path": RELEASE_GUARD_MD, "field": "overall_status", "status": guard_status or "MISSING"})

    readme_status = _line_status(_read_text("README.md"), ("current_release_status", "current release status"))
    if readme_status:
        observed.append({"path": "README.md", "field": "current_release_status", "status": readme_status})
    if latest_doc:
        doc_status = _line_status(_read_text(latest_doc), ("current_release_status", "current release status"))
        if doc_status:
            observed.append({"path": latest_doc, "field": "current_release_status", "status": doc_status})

    violations = []
    for item in observed:
        status = item["status"]
        if status == "PASS":
            status = "PASS_CANDIDATE"
        if status == "MISSING":
            violations.append({"code": "STATUS_FIELD_MISSING", **item})
        elif status != expected:
            violations.append({"code": "STATUS_MISMATCH", "expected": expected, **item})
    violations.extend(_check_forbidden_positive_wording(checked_files))
    payload = {
        **metadata_header(),
        "status": "FAIL" if violations else "PASS",
        "expected_current_release_status": expected,
        "expected_status_reasons": reasons,
        "observed_statuses": observed,
        "violations": violations,
        "checked_files": checked_files,
    }
    if write_report:
        write_json(OUT_JSON, payload)
        _write_md(payload)
    return payload


def _write_md(payload: dict[str, Any]) -> None:
    lines = [
        "# release status consistency",
        "",
        f"- status: {payload['status']}",
        f"- expected_current_release_status: {payload['expected_current_release_status']}",
        f"- generated_at: {payload['generated_at']}",
        "",
        "## observed statuses",
        "",
    ]
    for item in payload["observed_statuses"]:
        lines.append(f"- {item['path']} `{item['field']}`: {item['status']}")
    lines.extend(["", "## expected status reasons", ""])
    lines.extend([f"- {item['code']}: {item}" for item in payload.get("expected_status_reasons", [])] or ["- none"])
    lines.extend(["", "## violations", ""])
    lines.extend([f"- {item['code']}: {item}" for item in payload.get("violations", [])] or ["- none"])
    resolve_path(OUT_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description="Check that release status wording is consistent across public reports.")
    parser.add_argument("--no-write-report", action="store_true")
    args = parser.parse_args()
    payload = build_release_status_consistency_report(write_report=not args.no_write_report)
    return 1 if payload["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
