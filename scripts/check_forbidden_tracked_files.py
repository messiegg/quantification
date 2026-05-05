#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import fnmatch
import re
import subprocess
import sys
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.config import resolve_path


DEFAULT_ALLOWLIST = "config/release_file_allowlist.yml"
DEFAULT_CSV = "reports/backtest/release/forbidden_tracked_files_check.csv"
DEFAULT_MD = "reports/backtest/release/forbidden_tracked_files_check.md"

FORBIDDEN_GLOBS = [
    "*.parquet",
    "*.duckdb",
    "*.sqlite",
    "*.db",
    "*.cache",
    "data/features/**",
    "data/raw/**",
    "data/observation/paper_account.yml",
    "data/observation/paper_trades.csv",
    "data/observation/paper_positions.yml",
    "reports/observation/*/combined_v2_manual_order_list.csv",
    "reports/observation/*/combined_v2_actions.csv",
    "reports/observation/*/combined_v2_1_risk_guard_actions.csv",
    ".env",
    ".env.*",
    "**/.env",
    "**/.env.*",
]
SENSITIVE_PATH_RE = re.compile(r"(?i)(token|secret|credential|broker[_-]?account)")
SECRET_CONTENT_RE = re.compile(
    r"(?i)(token|secret|password|api[_-]?key)\s*[:=]\s*['\"]?"
    r"(?!false\b|true\b|null\b|missing\b|redacted\b|present\b)[A-Za-z0-9_\-]{20,}"
)
TEXT_SUFFIXES = {
    ".cfg",
    ".csv",
    ".ini",
    ".json",
    ".md",
    ".py",
    ".sh",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}


def _git_ls_files() -> list[str]:
    result = subprocess.run(
        ["git", "ls-files"],
        cwd=ROOT,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or "git ls-files failed")
    return [line.strip() for line in result.stdout.splitlines() if line.strip()]


def _is_forbidden_path(path: str) -> tuple[bool, str]:
    for pattern in FORBIDDEN_GLOBS:
        if fnmatch.fnmatch(path, pattern):
            return True, pattern
    name = Path(path).name
    if SENSITIVE_PATH_RE.search(name):
        return True, "sensitive filename pattern"
    return False, ""


def _read_allowlist(path_like: str | Path) -> dict[str, dict]:
    path = resolve_path(path_like)
    if not path.exists():
        return {}
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    items = payload.get("allowlist", payload if isinstance(payload, list) else [])
    allowed: dict[str, dict] = {}
    for item in items or []:
        if not isinstance(item, dict) or not item.get("path"):
            continue
        allowed[str(item["path"])] = item
    return allowed


def _allowlist_status(path: str, item: dict | None) -> tuple[bool, str]:
    if item is None:
        return False, "not allowlisted"
    if item.get("may_contain_sensitive_data") is not False:
        return False, "allowlist must set may_contain_sensitive_data: false"
    if not str(item.get("reason", "")).strip():
        return False, "allowlist reason is required"
    max_size = item.get("max_size_bytes")
    if not isinstance(max_size, int) or max_size <= 0:
        return False, "allowlist max_size_bytes must be a positive integer"
    file_path = resolve_path(path)
    if not file_path.exists():
        return False, "allowlisted file missing"
    actual_size = file_path.stat().st_size
    if actual_size > max_size:
        return False, f"allowlisted file too large: {actual_size} > {max_size}"
    return True, f"allowlisted small fixture/report, size={actual_size}"


def _safe_read_text(path: Path) -> str | None:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return None
    if not path.exists() or path.stat().st_size > 1_000_000:
        return None
    data = path.read_bytes()
    if b"\x00" in data:
        return None
    return data.decode("utf-8", errors="replace")


def _redact_secret_evidence(text: str) -> str:
    return re.sub(r"([:=]\s*['\"]?).*", r"\1<REDACTED>", text)


def _row(
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


def build_forbidden_tracked_files_check(
    tracked_files: list[str] | None = None,
    allowlist_path: str | Path = DEFAULT_ALLOWLIST,
    output_csv: str | Path = DEFAULT_CSV,
    output_md: str | Path = DEFAULT_MD,
    write_report: bool = True,
) -> pd.DataFrame:
    tracked = sorted(tracked_files if tracked_files is not None else _git_ls_files())
    allowlist = _read_allowlist(allowlist_path)
    rows: list[dict] = []
    forbidden_count = 0
    secret_count = 0
    allowlist_count = 0

    for path in tracked:
        forbidden, pattern = _is_forbidden_path(path)
        if forbidden:
            allowed, reason = _allowlist_status(path, allowlist.get(path))
            if allowed:
                allowlist_count += 1
                _row(
                    rows,
                    f"ALLOW-{allowlist_count:03d}",
                    "forbidden pattern allowed by release allowlist",
                    "PASS",
                    "explicit allowlist entry with size cap and no sensitive data",
                    path,
                    reason,
                    str(allowlist.get(path, {}).get("reason", "")),
                )
            else:
                forbidden_count += 1
                _row(
                    rows,
                    f"FORBID-{forbidden_count:03d}",
                    "forbidden tracked file pattern",
                    "FAIL",
                    "not tracked by git",
                    path,
                    f"matched={pattern}; {reason}",
                    "从 Git 中移除该文件，或仅对小型 fixture/report 写入 release allowlist。",
                )

        file_path = resolve_path(path)
        text = _safe_read_text(file_path)
        if text is None:
            continue
        for match in SECRET_CONTENT_RE.finditer(text):
            secret_count += 1
            _row(
                rows,
                f"SECRET-{secret_count:03d}",
                "tracked text contains token-like secret",
                "FAIL",
                "no token/password/secret/api key literal",
                path,
                _redact_secret_evidence(match.group(0)[:80]),
                "删除 secret 原文，改用环境变量或 redacted/present 这类布尔状态。",
            )

    if forbidden_count == 0:
        _row(
            rows,
            "FORBID-000",
            "no forbidden tracked files",
            "PASS",
            "0 forbidden tracked files outside allowlist",
            "0",
            "git ls-files",
            "未发现未豁免的大体量数据、真实账本、订单文件或 secret 文件。",
        )
    if secret_count == 0:
        _row(
            rows,
            "SECRET-000",
            "no token-like secrets in tracked text files",
            "PASS",
            "0 token-like secrets",
            "0",
            "tracked text scan",
            "未发现 token/password/secret/api key 原文。",
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
            "# forbidden tracked files check",
            "",
            f"- overall_status: {overall}",
            f"- tracked_files: {len(tracked)}",
            f"- allowlisted_exceptions: {allowlist_count}",
            f"- fail_count: {int((frame['status'] == 'FAIL').sum())}",
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
    parser = argparse.ArgumentParser(description="Check git-tracked files for data, orders, ledgers, and secrets that must stay local.")
    parser.add_argument("--allowlist", default=DEFAULT_ALLOWLIST)
    parser.add_argument("--write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    frame = build_forbidden_tracked_files_check(allowlist_path=args.allowlist, write_report=args.write_report)
    return 1 if (frame["status"] == "FAIL").any() else 0


if __name__ == "__main__":
    raise SystemExit(main())
