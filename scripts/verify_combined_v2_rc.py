#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.audit_common import (
    DEFAULT_END_DATE,
    DEFAULT_START_DATE,
    V2_HISTORY_DIR,
    ensure_parent,
    load_audit_configs,
    load_benchmark_window,
    load_feature_window,
    metrics_row,
    prepare_v2_history,
    run_profile,
    status_from_rows,
)
from src.utils.config import resolve_path


MANIFEST_PATH = "reports/backtest/release/combined_v2_rc_manifest.json"
CODE_MANIFEST_PATH = "reports/backtest/release/combined_v2_rc_code_manifest.json"
VERIFY_CSV = "reports/backtest/release/combined_v2_rc_verify.csv"
VERIFY_MD = "reports/backtest/release/combined_v2_rc_verify.md"
EXPECTED_METRICS = {
    "annual_return": (0.0713520247687258, 1e-10),
    "cumulative_return": (0.2196444045310004, 1e-10),
    "max_drawdown": (-0.0936454742991675, 1e-10),
    "final_nav": (243928.8809062001, 1e-6),
}
EXPECTED_TOTAL_TRADES = 76
CODE_FILES = [
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
]


def sha256_path(path_like: str | Path) -> str:
    path = resolve_path(path_like)
    if not path.exists():
        return ""
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_frame(frame: pd.DataFrame) -> str:
    buffer = StringIO()
    frame.to_csv(buffer, index=False)
    return hashlib.sha256(buffer.getvalue().encode("utf-8")).hexdigest()


def _manifest_hash_map(manifest: dict) -> dict[str, str]:
    return {
        str(item.get("path")): str(item.get("sha256", ""))
        for item in manifest.get("key_output_file_hashes", [])
        if item.get("exists", False)
    }


def _row(
    rows: list[dict],
    check_id: str,
    check_name: str,
    status: str,
    expected: object,
    actual: object,
    diff: object,
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
            "diff": diff,
            "evidence": evidence,
            "recommendation": recommendation,
        }
    )


def _read_manifest(path_like: str | Path) -> dict:
    path = resolve_path(path_like)
    return json.loads(path.read_text(encoding="utf-8"))


def _load_existing_metrics(manifest: dict) -> tuple[dict, pd.DataFrame]:
    execution = pd.read_csv(resolve_path("reports/backtest/audit/execution_mode_compare.csv"))
    row = execution[(execution["profile"] == "combined_v2") & (execution["execution_mode"] == "next_bar")].iloc[0]
    initial_capital = float(manifest.get("initial_capital", 200000.0))
    metrics = {
        "annual_return": float(row["annual_return"]),
        "cumulative_return": float(row["cumulative_return"]),
        "max_drawdown": float(row["max_drawdown"]),
        "final_nav": initial_capital * (1.0 + float(row["cumulative_return"])),
        "total_trades": int(row["total_trades"]),
    }
    return metrics, execution


def _rerun_metrics(manifest: dict) -> tuple[dict, str]:
    configs = load_audit_configs()
    prepare_v2_history(configs)
    features = load_feature_window(
        str(manifest.get("start_date", DEFAULT_START_DATE)),
        str(manifest.get("end_date", DEFAULT_END_DATE)),
    )
    benchmark = load_benchmark_window(
        str(manifest.get("start_date", DEFAULT_START_DATE)),
        str(manifest.get("end_date", DEFAULT_END_DATE)),
    )
    result = run_profile("combined_v2", features, benchmark, configs, execution_mode="next_bar", historical_universe_dir=V2_HISTORY_DIR)
    row = metrics_row("combined_v2", "next_bar", result, benchmark)
    initial_capital = float(manifest.get("initial_capital", 200000.0))
    return (
        {
            "annual_return": float(row["annual_return"]),
            "cumulative_return": float(row["cumulative_return"]),
            "max_drawdown": float(row["max_drawdown"]),
            "final_nav": initial_capital * (1.0 + float(row["cumulative_return"])),
            "total_trades": int(row["total_trades"]),
        },
        sha256_frame(result.trades_detailed if result.trades_detailed is not None else pd.DataFrame()),
    )


def _current_code_hashes() -> dict:
    return {
        "created_at": datetime.now(timezone.utc).isoformat(),
        "files": [{"path": path, "sha256": sha256_path(path), "exists": resolve_path(path).exists()} for path in CODE_FILES],
    }


def _verify_code_manifest(rows: list[dict], code_manifest_path: str | Path) -> None:
    path = resolve_path(code_manifest_path)
    current = _current_code_hashes()
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(current, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        _row(rows, "CODE-001", "code hash manifest exists", "PASS", "created", str(path), "", str(path), "首次生成代码哈希基线。")
        return
    expected_payload = json.loads(path.read_text(encoding="utf-8"))
    expected = {str(item.get("path")): str(item.get("sha256", "")) for item in expected_payload.get("files", [])}
    drift = []
    for item in current["files"]:
        path_name = item["path"]
        if expected.get(path_name) != item["sha256"]:
            drift.append(path_name)
    _row(
        rows,
        "CODE-001",
        "strategy code hash drift",
        "WARN" if drift else "PASS",
        "no drift",
        ";".join(drift) if drift else "no drift",
        len(drift),
        str(path),
        "代码有漂移时不直接判定策略失效，但必须重跑完整审计。" if drift else "代码哈希与 RC code manifest 一致。",
    )


def verify_release_candidate(
    manifest_path: str | Path = MANIFEST_PATH,
    code_manifest_path: str | Path = CODE_MANIFEST_PATH,
    output_csv: str | Path = VERIFY_CSV,
    output_md: str | Path = VERIFY_MD,
    rerun_backtest: bool = True,
    mode: str | None = None,
    write_report: bool = True,
) -> pd.DataFrame:
    if mode is None:
        mode = "full" if rerun_backtest else "hash-only"
    if mode not in {"full", "hash-only"}:
        raise ValueError(f"unsupported verify mode: {mode}")
    rerun_backtest = mode == "full"

    manifest = _read_manifest(manifest_path)
    manifest_hashes = _manifest_hash_map(manifest)
    rows: list[dict] = []

    _row(
        rows,
        "MODE-001",
        "verification mode",
        "PASS",
        mode,
        mode,
        "",
        str(manifest_path),
        "hash-only 使用已提交的小型报告与 manifest，不重跑完整回测；full 仅用于本地完整数据环境。",
    )

    for path in ("config/strategy_v2.yml", "config/universe_rules_v2.yml"):
        expected = manifest_hashes.get(path, "")
        actual = sha256_path(path)
        _row(
            rows,
            f"CFG-{len(rows) + 1:03d}",
            f"{path} sha256 matches RC manifest",
            "PASS" if expected and actual == expected else "FAIL",
            expected,
            actual,
            "",
            path,
            "配置 hash 不匹配会改变主策略含义，必须停止观察日报。" if actual != expected else "配置未漂移。",
        )

    metrics, _ = _rerun_metrics(manifest) if rerun_backtest else _load_existing_metrics(manifest)
    source = "in-memory rerun" if rerun_backtest else "hash-only: execution_mode_compare.csv"
    for metric_name, (expected, tolerance) in EXPECTED_METRICS.items():
        actual = float(metrics[metric_name])
        diff = actual - expected
        _row(
            rows,
            f"MET-{metric_name}",
            f"{metric_name} strict RC metric",
            "PASS" if abs(diff) <= tolerance else "FAIL",
            expected,
            actual,
            diff,
            source,
            f"{metric_name} 必须在容差 {tolerance} 内复现。",
        )
    actual_trades = int(metrics["total_trades"])
    _row(
        rows,
        "MET-total_trades",
        "total_trades strict RC metric",
        "PASS" if actual_trades == EXPECTED_TOTAL_TRADES else "FAIL",
        EXPECTED_TOTAL_TRADES,
        actual_trades,
        actual_trades - EXPECTED_TOTAL_TRADES,
        source,
        "total_trades 必须等于 76。",
    )

    current_trade_hash = sha256_path("reports/backtest/combined_v2_trades_detailed.csv")
    expected_trade_hash = manifest_hashes.get("reports/backtest/combined_v2_trades_detailed.csv", "")
    rerun_trade_hash = metrics.get("trades_hash", "") if isinstance(metrics, dict) else ""
    _row(
        rows,
        "OUT-001",
        "combined_v2 trades detailed hash",
        "PASS" if current_trade_hash == expected_trade_hash else "WARN",
        expected_trade_hash,
        current_trade_hash,
        "",
        "reports/backtest/combined_v2_trades_detailed.csv",
        "交易明细文件 hash 漂移但严格指标一致时标记 WARN；若指标也漂移则整体 FAIL。",
    )

    for path, expected in sorted(manifest_hashes.items()):
        if path in {"config/strategy_v2.yml", "config/universe_rules_v2.yml", "reports/backtest/combined_v2_trades_detailed.csv"}:
            continue
        actual = sha256_path(path)
        _row(
            rows,
            f"OUT-{len(rows) + 1:03d}",
            f"{path} key output hash",
            "PASS" if actual == expected else "WARN",
            expected,
            actual,
            "",
            path,
            "报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。",
        )

    _verify_code_manifest(rows, code_manifest_path)

    frame = pd.DataFrame(rows, columns=["check_id", "check_name", "status", "expected", "actual", "diff", "evidence", "recommendation"])
    if write_report:
        csv_path = ensure_parent(output_csv)
        md_path = ensure_parent(output_md)
        frame.to_csv(csv_path, index=False)
        overall = status_from_rows(rows)
        lines = [
            "# combined_v2 RC verify",
            "",
            f"- overall_status: {overall}",
            f"- mode: {mode}",
            f"- profile: {manifest.get('profile')}",
            f"- execution_mode: {manifest.get('execution_mode')}",
            f"- period: {manifest.get('start_date')} to {manifest.get('end_date')}",
            f"- annual_return: {metrics['annual_return']}",
            f"- cumulative_return: {metrics['cumulative_return']}",
            f"- max_drawdown: {metrics['max_drawdown']}",
            f"- total_trades: {metrics['total_trades']}",
            f"- final_nav: {metrics['final_nav']}",
            "",
            "## checks",
            "",
        ]
        for row in rows:
            lines.append(
                f"- {row['status']} | {row['check_id']} | {row['check_name']} | expected={row['expected']} | actual={row['actual']} | {row['recommendation']}"
            )
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return frame


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Verify combined_v2 release-candidate strict next_bar口径。")
    parser.add_argument("--manifest", default=MANIFEST_PATH)
    parser.add_argument(
        "--mode",
        choices=["hash-only", "full"],
        default=None,
        help="hash-only checks manifest/report hashes and committed metrics without full backtest; full reruns the strict next_bar backtest.",
    )
    parser.add_argument(
        "--skip-rerun",
        action="store_true",
        help="Deprecated alias for --mode hash-only.",
    )
    parser.add_argument(
        "--no-rerun-backtest",
        action="store_true",
        help="Alias for --mode hash-only.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    mode = args.mode
    if mode is None and (args.skip_rerun or args.no_rerun_backtest):
        mode = "hash-only"
    if mode is None:
        mode = "full"
    frame = verify_release_candidate(manifest_path=args.manifest, mode=mode)
    return 1 if (frame["status"] == "FAIL").any() else 0


if __name__ == "__main__":
    raise SystemExit(main())
