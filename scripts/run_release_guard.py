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
from scripts.audit_config_consistency import build_config_consistency_report
from scripts.audit_data_freshness import build_audit_data_freshness_report
from scripts.audit_universe_integrity import build_universe_integrity_report
from scripts.build_account_constraints_report import build_account_constraints_report
from scripts.build_account_suitability_report import build_account_suitability_report
from scripts.build_module_contribution_report import build_module_contribution_report
from scripts.build_observation_evidence_chain import build_observation_evidence_chain
from scripts.build_sensitivity_trigger_coverage_report import build_sensitivity_trigger_coverage_report
from scripts.build_universe_shortfall_report import build_universe_shortfall_report
from scripts.check_release_status_consistency import build_release_status_consistency_report
from scripts.evaluate_observation_readiness import evaluate_observation_readiness
from scripts.report_metadata import config_hash, data_hash, git_branch, git_commit, now_utc_iso, sha256_path, status_from_children, write_json
from scripts.verify_combined_v2_rc import MANIFEST_PATH, _manifest_hash_map, verify_release_candidate
from src.utils.config import resolve_path


DEFAULT_AS_OF_DATE = "2026-05-04"
DEFAULT_CSV = "reports/backtest/release/release_guard_report.csv"
DEFAULT_MD = "reports/backtest/release/release_guard_report.md"
RELEASE_MANIFEST_JSON = "reports/backtest/release/combined_v2_rc_manifest.json"
RELEASE_MANIFEST_MD = "reports/backtest/release/combined_v2_rc_manifest.md"
TEST_STATUS_JSON = "reports/backtest/release/test_status.json"
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


def _status_from_json(path_like: str | Path) -> str:
    payload = _read_json(path_like)
    return str(payload.get("status", "FAIL")).upper() if payload else "FAIL"


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


def _add_payload_check(
    rows: list[dict],
    check_id: str,
    check_name: str,
    payload: dict,
    evidence: str,
    recommendation: str,
    fail_on_warn: bool = False,
) -> None:
    raw_status = str(payload.get("status", "FAIL")).upper()
    status = "FAIL" if fail_on_warn and raw_status == "WARN" else raw_status
    _row(rows, check_id, check_name, status, "PASS/WARN without FAIL", raw_status, evidence, recommendation)


def _check_lookahead_audit(rows: list[dict]) -> None:
    frame = pd.DataFrame()
    path = resolve_path("reports/backtest/audit/lookahead_audit.csv")
    if path.exists():
        try:
            frame = pd.read_csv(path)
        except pd.errors.EmptyDataError:
            frame = pd.DataFrame()
    confirmed = 0
    if not frame.empty:
        if "status" in frame.columns:
            confirmed = int((frame["status"].astype(str).str.upper() == "FAIL").sum())
        if "confirmed_violations" in frame.columns:
            confirmed = max(confirmed, int(pd.to_numeric(frame["confirmed_violations"], errors="coerce").fillna(0).sum()))
    _row(
        rows,
        "RG-LOOKAHEAD-001",
        "lookahead audit has no confirmed violations",
        "PASS" if path.exists() and confirmed == 0 else "FAIL",
        "confirmed violations = 0",
        confirmed if path.exists() else "missing",
        "reports/backtest/audit/lookahead_audit.csv",
        "前视审计缺失或存在 confirmed violation 时，release 必须 FAIL。",
    )


def _check_sensitivity(rows: list[dict]) -> None:
    payload = _read_json("reports/backtest/robustness/sensitivity_report.json")
    status = str(payload.get("status", "FAIL")).upper() if payload else "FAIL"
    mode = str(payload.get("mode", "")).lower() if payload else ""
    non_binding = payload.get("non_binding_parameters", []) if payload else []
    unknown = [
        item
        for item in payload.get("variants", []) if str(item.get("non_binding_reason", "")).upper() == "UNKNOWN"
    ] if payload else []
    errors = [
        item
        for item in payload.get("variants", []) if str(item.get("parameter_binding_status", "")).upper() == "ERROR"
    ] if payload else []
    if mode != "ci":
        status = "FAIL"
    if status != "FAIL" and unknown:
        status = "FAIL"
    if status != "FAIL" and errors:
        status = "FAIL"
    _row(
        rows,
        "RG-SENS-001",
        "sensitivity report binds or classifies core parameters",
        status,
        "ci mode report with no all-core NON_BINDING, ERROR, or UNKNOWN PASS",
        f"status={payload.get('status') if payload else 'missing'}; mode={mode or 'missing'}; non_binding={len(non_binding)}; unknown={len(unknown)}; errors={len(errors)}",
        "reports/backtest/robustness/sensitivity_report.json",
        "release guard 只认可 --mode ci 结果；参数变化未绑定、计算 ERROR 或原因 UNKNOWN 不能计入鲁棒性 PASS。",
    )


def _check_baseline_comparison(rows: list[dict]) -> None:
    payload = _read_json("reports/backtest/controls/baseline_comparison.json")
    _row(
        rows,
        "RG-BASELINE-001",
        "baseline comparison report exists and is not failing",
        str(payload.get("status", "FAIL")).upper() if payload else "FAIL",
        "baseline comparison PASS/WARN",
        payload.get("status", "missing") if payload else "missing",
        "reports/backtest/controls/baseline_comparison.json",
        "必须区分 documented dianjinshu-like baseline、combined_v2 和模块消融。",
    )


def _add_observation_readiness_check(rows: list[dict], payload: dict) -> None:
    raw_status = str(payload.get("status", "NOT_READY")).upper() if payload else "FAIL"
    status = "PASS" if raw_status == "READY" else "WARN" if raw_status == "NOT_READY" else "FAIL"
    _row(
        rows,
        "RG-READY-001",
        "observation readiness policy",
        status,
        "READY for PASS_CANDIDATE consideration",
        raw_status,
        "reports/observation/readiness_report.json",
        "观察期准入未满足时不得进入 PASS_CANDIDATE，只能保持 WARN。",
    )


def _check_tests_status(rows: list[dict]) -> None:
    payload = _read_json(TEST_STATUS_JSON)
    _row(
        rows,
        "RG-TESTS-001",
        "latest pytest status is recorded",
        "PASS" if payload.get("status") == "PASS" else "FAIL",
        "reports/backtest/release/test_status.json status=PASS",
        payload.get("status", "missing") if payload else "missing",
        TEST_STATUS_JSON,
        "release manifest 必须记录本轮自动化测试状态；缺失时 fail closed。",
    )


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


def _release_status_from_rows(frame: pd.DataFrame) -> str:
    if frame.empty or "status" not in frame.columns:
        return "FAIL"
    statuses = set(frame["status"].astype(str).str.upper())
    if "FAIL" in statuses:
        return "FAIL"
    if "WARN" in statuses:
        return "WARN"
    return "PASS_CANDIDATE"


def _write_release_manifest(frame: pd.DataFrame, as_of_date: str, audit_payloads: dict[str, dict]) -> None:
    existing = _read_json(RELEASE_MANIFEST_JSON)
    freshness = audit_payloads.get("data_freshness", {})
    account_constraints = audit_payloads.get("account_constraints", {})
    account_suitability = audit_payloads.get("account_suitability", {})
    universe_shortfall = audit_payloads.get("universe_shortfall", {})
    sensitivity_coverage = audit_payloads.get("sensitivity_trigger_coverage", {})
    module_contribution = audit_payloads.get("module_contribution", {})
    observation_readiness = audit_payloads.get("observation_readiness", {})
    status = _release_status_from_rows(frame)
    key_paths = [
        "config/strategy_v2.yml",
        "config/universe_rules_v2.yml",
        "config/account.yml",
        "config/metric_map.yml",
        "config/observation.yml",
        "reports/backtest/combined_v2_trades_detailed.csv",
        "reports/backtest/combined_v2_signal_funnel.csv",
        "reports/backtest/combined_v2_candidate_scores.csv",
        "reports/backtest/audit/lookahead_audit.csv",
        "reports/backtest/audit/integrity_audit.csv",
        "reports/audit/config_consistency.json",
        "reports/audit/universe_integrity.json",
        "reports/audit/data_freshness.json",
        f"reports/observation/{as_of_date}/evidence_chain.json",
        "reports/backtest/robustness/sensitivity_report.json",
        "reports/backtest/account_constraints_report.json",
        "reports/backtest/account_suitability_report.json",
        "reports/backtest/controls/baseline_comparison.json",
        "reports/backtest/controls/module_contribution_report.json",
        "reports/backtest/robustness/sensitivity_trigger_coverage.json",
        "reports/audit/universe_shortfall.json",
        "reports/observation/readiness_report.json",
        "config/observation_readiness.yml",
    ]
    payload = {
        **existing,
        "status": status,
        "branch": git_branch(),
        "git_commit": git_commit(),
        "generated_at": now_utc_iso(),
        "config_hash": config_hash(),
        "data_hash": data_hash(),
        "requested_date": as_of_date,
        "target_trade_date": freshness.get("target_trade_date", freshness.get("target_trading_date", "")),
        "target_trading_date": freshness.get("target_trade_date", freshness.get("target_trading_date", "")),
        "market_data_asof": freshness.get("market_data_asof", ""),
        "feature_data_asof": freshness.get("feature_data_asof", ""),
        "benchmark_data_asof": freshness.get("benchmark_data_asof", ""),
        "financial_data_asof": freshness.get("financial_data_asof", ""),
        "effective_financial_date": freshness.get("effective_financial_date", ""),
        "manual_review_required": True,
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
        "release_scope": "small_capital_manual_strict_review_observation_candidate",
        "audit_statuses": {
            key: value.get("status", "FAIL")
            for key, value in audit_payloads.items()
        },
        "release_guard_checks": frame.to_dict(orient="records"),
        "risk_section": {
            "account_constraints_status": account_constraints.get("status", "FAIL"),
            "account_constraints_warnings": account_constraints.get("warnings", []),
            "account_suitability_status": account_suitability.get("status", "MISSING"),
            "account_suitability_base_executable_raw_buy_ratio": (account_suitability.get("base_case") or {}).get("executable_raw_buy_ratio"),
            "universe_shortfall_status": universe_shortfall.get("status", "MISSING"),
            "universe_shortfall_to_target": universe_shortfall.get("shortfall_to_target"),
            "sensitivity_trigger_coverage_status": sensitivity_coverage.get("status", "MISSING"),
            "sensitivity_non_binding_classifications": [
                {
                    "param_path": item.get("param_path"),
                    "classification": item.get("classification"),
                    "variant_id": item.get("variant_id"),
                }
                for item in sensitivity_coverage.get("classifications", [])
            ],
            "module_contribution_status": module_contribution.get("status", "MISSING"),
            "module_contribution_classifications": [
                {
                    "module": item.get("module"),
                    "classification": item.get("classification"),
                    "human_review_required": item.get("human_review_required"),
                }
                for item in module_contribution.get("modules", [])
                if item.get("classification") in {"POSSIBLE_DRAG", "INCONCLUSIVE", "COSTLY_RISK_REDUCER", "RISK_REDUCER"}
            ],
            "observation_readiness_status": observation_readiness.get("status", "MISSING"),
            "minimum_backtest_years_warning": "sample is about three years; keep as manual observation candidate only",
            "auto_trading_approved": False,
        },
        "key_output_file_hashes": [
            {"path": path, "sha256": sha256_path(path), "exists": resolve_path(path).exists()}
            for path in key_paths
        ],
    }
    write_json(RELEASE_MANIFEST_JSON, payload)
    lines = [
        "# combined_v2 RC manifest",
        "",
        f"- status: {status}",
        f"- branch: {payload['branch']}",
        f"- git_commit: {payload['git_commit']}",
        f"- generated_at: {payload['generated_at']}",
        f"- config_hash: {payload['config_hash']}",
        f"- data_hash: {payload['data_hash']}",
        f"- requested_date: {payload['requested_date']}",
        f"- target_trade_date: {payload['target_trade_date']}",
        f"- market_data_asof: {payload['market_data_asof']}",
        f"- feature_data_asof: {payload['feature_data_asof']}",
        f"- benchmark_data_asof: {payload['benchmark_data_asof']}",
        "- manual_review_required: true",
        "- auto_trading_approved: false",
        "- broker_integration_enabled: false",
        "- llm_decision_allowed: false",
        "- release_scope: 小资金、手动、严格复核观察/试运行候选；不是自动交易批准。",
        "",
        "## audit statuses",
        "",
    ]
    for key, value in payload["audit_statuses"].items():
        lines.append(f"- {key}: {value}")
    lines.extend(["", "## risk section", ""])
    for warning in account_constraints.get("warnings", []):
        lines.append(f"- {warning.get('code')}: {warning.get('message')} actual={warning.get('actual')}")
    if not account_constraints.get("warnings"):
        lines.append("- account_constraints: no WARN")
    lines.append(f"- universe_shortfall_to_target: {payload['risk_section'].get('universe_shortfall_to_target')}")
    lines.append(f"- account_suitability_base_executable_raw_buy_ratio: {payload['risk_section'].get('account_suitability_base_executable_raw_buy_ratio')}")
    lines.append(f"- observation_readiness_status: {payload['risk_section'].get('observation_readiness_status')}")
    for item in payload["risk_section"].get("sensitivity_non_binding_classifications", []):
        lines.append(f"- sensitivity {item.get('param_path')}: {item.get('classification')}")
    for item in payload["risk_section"].get("module_contribution_classifications", []):
        lines.append(f"- module {item.get('module')}: {item.get('classification')}")
    lines.extend(["", "## release guard checks", ""])
    for row in payload["release_guard_checks"]:
        lines.append(f"- {row['status']} | {row['check_id']} | {row['check_name']} | actual={row['actual']}")
    resolve_path(RELEASE_MANIFEST_MD).write_text("\n".join(lines) + "\n", encoding="utf-8")


def build_release_guard_report(
    as_of_date: str = DEFAULT_AS_OF_DATE,
    ci: bool = False,
    strict: bool = False,
    write_report: bool = True,
    output_csv: str | Path = DEFAULT_CSV,
    output_md: str | Path = DEFAULT_MD,
) -> pd.DataFrame:
    rows: list[dict] = []
    audit_payloads: dict[str, dict] = {}

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

    config_consistency = build_config_consistency_report(write_report=write_report)
    audit_payloads["config_consistency"] = config_consistency
    _add_payload_check(rows, "RG-CONFIG-001", "config consistency audit", config_consistency, "scripts/audit_config_consistency.py", "运行配置之间冲突必须 FAIL；README 冲突只作为 DOC_MISMATCH WARN。")

    universe_integrity = build_universe_integrity_report(write_report=write_report)
    audit_payloads["universe_integrity"] = universe_integrity
    _add_payload_check(rows, "RG-UNIVERSE-001", "universe integrity audit", universe_integrity, "scripts/audit_universe_integrity.py", "股票池低于 floor、突破硬过滤或 override 无依据时必须 FAIL。")

    universe_shortfall = build_universe_shortfall_report(write_report=write_report)
    audit_payloads["universe_shortfall"] = universe_shortfall
    _add_payload_check(rows, "RG-UNIVERSE-002", "universe shortfall explanation", universe_shortfall, "scripts/build_universe_shortfall_report.py", "低于 target 但高于 floor 时保持 WARN，并输出候选损耗解释。")

    data_freshness = build_audit_data_freshness_report(as_of_date, write_report=write_report)
    audit_payloads["data_freshness"] = data_freshness
    _add_payload_check(rows, "RG-DATA-001", "data freshness audit", data_freshness, "scripts/audit_data_freshness.py", "target_trade_date 晚于数据 asof 时必须 FAIL。")

    account_constraints = build_account_constraints_report(write_report=write_report)
    audit_payloads["account_constraints"] = account_constraints
    _add_payload_check(rows, "RG-ACCOUNT-001", "account constraints report", account_constraints, "scripts/build_account_constraints_report.py", "账户约束 WARN 不自动阻断 release，但必须进入 manifest risk section.")

    account_suitability = build_account_suitability_report(write_report=write_report)
    audit_payloads["account_suitability"] = account_suitability
    _add_payload_check(rows, "RG-ACCOUNT-002", "account suitability report", account_suitability, "scripts/build_account_suitability_report.py", "base case 执行比例低于观察阈值时保持 WARN，研究场景不得用于 release PASS。")

    evidence_chain = build_observation_evidence_chain(
        as_of_date,
        target_trade_date=str(data_freshness.get("target_trade_date") or data_freshness.get("target_trading_date") or as_of_date),
        universe_report=universe_integrity,
        freshness_report=data_freshness,
        write_report=write_report,
    )
    audit_payloads["evidence_chain"] = evidence_chain
    _add_payload_check(rows, "RG-EVIDENCE-001", "observation evidence chain", evidence_chain, "scripts/build_observation_evidence_chain.py", "若 observation/release 声称可执行，必须同时存在 evidence_chain。")

    _check_lookahead_audit(rows)
    _check_sensitivity(rows)
    audit_payloads["sensitivity"] = _read_json("reports/backtest/robustness/sensitivity_report.json")
    sensitivity_coverage = build_sensitivity_trigger_coverage_report(write_report=write_report)
    audit_payloads["sensitivity_trigger_coverage"] = sensitivity_coverage
    _add_payload_check(rows, "RG-SENS-002", "sensitivity trigger coverage", sensitivity_coverage, "scripts/build_sensitivity_trigger_coverage_report.py", "NON_BINDING 参数必须分类；PARAM_NOT_WIRED 必须 FAIL，NO_SIGNAL_COVERAGE 保持 WARN。")
    _check_baseline_comparison(rows)
    audit_payloads["baseline_comparison"] = _read_json("reports/backtest/controls/baseline_comparison.json")
    module_contribution = build_module_contribution_report(write_report=write_report)
    audit_payloads["module_contribution"] = module_contribution
    _add_payload_check(rows, "RG-BASELINE-002", "module contribution report", module_contribution, "scripts/build_module_contribution_report.py", "MODULE_MAY_BE_DRAG 必须拆成风险收益解释，不自动删模块。")
    _check_tests_status(rows)

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
    observation_readiness = evaluate_observation_readiness(write_report=write_report)
    audit_payloads["observation_readiness"] = observation_readiness
    _add_observation_readiness_check(rows, observation_readiness)
    _check_config_hashes(rows)

    status_consistency = build_release_status_consistency_report(write_report=write_report)
    audit_payloads["release_status_consistency"] = status_consistency
    _row(
        rows,
        "RG-STATUS-001",
        "release status consistency",
        str(status_consistency.get("status", "FAIL")).upper(),
        "current release status consistent across public reports",
        status_consistency.get("expected_current_release_status", "missing"),
        "scripts/check_release_status_consistency.py",
        "manifest、release guard、README 和当前 project_status 文档不得互相矛盾。",
    )

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
        _write_release_manifest(frame, as_of_date, audit_payloads)
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run combined_v2 observation release guard checks.")
    parser.add_argument("--ci", action="store_true", help="Run CI-safe hash-only release checks.")
    parser.add_argument("--as-of-date", default=DEFAULT_AS_OF_DATE)
    parser.add_argument("--strict", action="store_true", help="Treat WARN as failing.")
    parser.add_argument("--write-report", action="store_true", help="Deprecated: reports are written by default.")
    parser.add_argument("--no-write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frame = build_release_guard_report(
        as_of_date=args.as_of_date,
        ci=args.ci,
        strict=args.strict,
        write_report=not args.no_write_report,
    )
    if (frame["status"] == "FAIL").any():
        return 1
    if args.strict and (frame["status"] == "WARN").any():
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
