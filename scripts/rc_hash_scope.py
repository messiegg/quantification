from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.utils.config import resolve_path


CODE_HASH_SCOPE_VERSION = "combined_v2_rc_code_scope_v1"

CODE_HASH_FILES = [
    "src/execution/__init__.py",
    "src/execution/models.py",
    "src/execution/sizer.py",
    "src/execution/allocator.py",
    "src/execution/pending.py",
    "src/strategy/signals.py",
    "src/strategy/backtest_engine.py",
    "src/strategy/universe.py",
    "src/strategy/grid.py",
    "src/strategy/valuation_resolution.py",
    "src/strategy/backtest_reports.py",
    "scripts/backtest.py",
    "scripts/run_backtest_compare.py",
    "scripts/run_backtest_execution_compare.py",
    "scripts/run_backtest_attribution.py",
    "scripts/audit_backtest_lookahead.py",
    "scripts/audit_backtest_integrity.py",
    "scripts/build_account_constraints_report.py",
    "scripts/build_account_suitability_report.py",
    "scripts/run_account_profile_backtests.py",
    "scripts/rc_hash_scope.py",
    "scripts/build_combined_v2_release_candidate.py",
    "scripts/check_release_status_consistency.py",
    "scripts/run_release_guard.py",
    "scripts/verify_combined_v2_rc.py",
]

KEY_OUTPUT_HASH_FILES = [
    "config/strategy_v2.yml",
    "config/universe_rules_v2.yml",
    "config/account.yml",
    "config/metric_map.yml",
    "config/observation.yml",
    "config/observation_readiness.yml",
    "reports/backtest/combined_v2_trades_detailed.csv",
    "reports/backtest/combined_v2_signal_funnel.csv",
    "reports/backtest/combined_v2_candidate_scores.csv",
    "reports/backtest/combined_v2_retail_50k_metrics.csv",
    "reports/backtest/audit/lookahead_audit.csv",
    "reports/backtest/audit/integrity_audit.csv",
    "reports/audit/config_consistency.json",
    "reports/audit/universe_integrity.json",
    "reports/audit/data_freshness.json",
    "reports/audit/universe_shortfall.json",
    "reports/observation/2026-05-04/evidence_chain.json",
    "reports/observation/readiness_report.json",
    "reports/backtest/robustness/sensitivity_report.json",
    "reports/backtest/robustness/sensitivity_trigger_coverage.json",
    "reports/backtest/account_constraints_report.json",
    "reports/backtest/account_suitability_report.json",
    "reports/backtest/account_profiles/account_profile_comparison.json",
    "reports/backtest/controls/baseline_comparison.json",
    "reports/backtest/controls/module_contribution_report.json",
]

RESEARCH_ONLY_EXCLUDED_FROM_RC_CODE_HASH = [
    "README.md",
    "docs/**",
    "config/strategy_v2_50k_compact.yml",
    "scripts/run_50k_compact_experiments.py",
    "scripts/run_account_execution_improvement_experiments.py",
    "reports/backtest/50k_compact/**",
    "reports/backtest/account_profiles/executable_raw_experiments/**",
    "reports/backtest/account_profiles/executable_raw_improvement_*",
]

HASH_SCOPE_DESCRIPTION = (
    "combined_v2 RC code hash covers strategy/backtest/release verification code that can change "
    "current default release behavior, metrics, account diagnostics, or RC validation. Research-only "
    "account execution experiments, the combined_v2_50k_compact profile, README/docs, and generated "
    "executable/raw or compact research matrices are excluded from the RC code hash and must not be "
    "used to change release PASS/WARN status."
)


def sha256_path(path_like: str | Path) -> str:
    path = resolve_path(path_like)
    if not path.exists() or not path.is_file():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def file_hash_record(path: str) -> dict[str, Any]:
    resolved = resolve_path(path)
    return {"path": path, "sha256": sha256_path(path), "exists": resolved.exists() and resolved.is_file()}


def key_output_file_hashes() -> list[dict[str, Any]]:
    return [file_hash_record(path) for path in KEY_OUTPUT_HASH_FILES]


def code_hash_manifest() -> dict[str, Any]:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "scope_version": CODE_HASH_SCOPE_VERSION,
        "description": HASH_SCOPE_DESCRIPTION,
        "included_files": CODE_HASH_FILES,
        "research_only_excluded": RESEARCH_ONLY_EXCLUDED_FROM_RC_CODE_HASH,
        "files": [file_hash_record(path) for path in CODE_HASH_FILES],
    }
