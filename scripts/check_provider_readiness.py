#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import importlib.util
import json
import os
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.check_data_freshness import _json_optional, _parse_date, _date_str, resolve_target_trading_date
from src.utils.config import load_yaml_optional, resolve_path


OUTPUT_DIR = Path("reports/data_update/provider_preflight")
DEFAULT_JSON = OUTPUT_DIR / "provider_readiness_report.json"
DEFAULT_MD = OUTPUT_DIR / "provider_readiness_report.md"
DEFAULT_CSV = OUTPUT_DIR / "provider_readiness_check.csv"


def _has_import(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _token_present(env_name: str) -> bool:
    if bool(os.environ.get(env_name)):
        return True
    env_path = ROOT / ".env"
    if not env_path.exists():
        return False
    try:
        for raw_line in env_path.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() == env_name and value.strip().strip("\"'"):
                return True
    except OSError:
        return False
    return False


def _path_writable(path_like: str | Path) -> bool:
    path = resolve_path(path_like)
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / ".preflight_write_test"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except Exception:
        return False


def _provider_failures(payload: dict) -> list[dict]:
    return [entry for entry in payload.get("providers", []) if isinstance(entry, dict) and str(entry.get("success", "")).lower() == "false"]


def _row(rows: list[dict], check_id: str, check_name: str, provider: str, status: str, expected: object, actual: object, evidence: str, recommendation: str, secret_redacted: bool = True) -> None:
    rows.append(
        {
            "check_id": check_id,
            "check_name": check_name,
            "provider": provider,
            "status": status,
            "expected": expected,
            "actual": actual,
            "evidence": evidence,
            "recommendation": recommendation,
            "secret_redacted": secret_redacted,
        }
    )


def check_provider_readiness(
    as_of_date: str,
    target_trading_date: str | None = None,
    no_network: bool = False,
    write_report: bool = True,
    output_json: str | Path = DEFAULT_JSON,
    output_md: str | Path = DEFAULT_MD,
    output_csv: str | Path = DEFAULT_CSV,
) -> dict:
    data_cfg = load_yaml_optional("config/data_sources.yml")
    obs_cfg = load_yaml_optional("config/observation.yml").get("observation", {})
    target_info = resolve_target_trading_date(
        as_of_date,
        market=str(obs_cfg.get("calendar_market", "A_SHARE")),
        observation_config=obs_cfg,
        target_trading_date=target_trading_date,
    )
    target = str(target_info.get("target_trading_date") or "")
    rows: list[dict] = []

    tdx_dirs = [str(item) for item in data_cfg.get("tdx", {}).get("local_dirs", []) or []]
    if not tdx_dirs:
        _row(rows, "TDX-001", "tdx local dirs configured", "tdx", "NOT_APPLICABLE", "configured local dir", "none", "config/data_sources.yml", "未配置本地 TDX 路径。")
        local_tdx_available = False
    else:
        local_tdx_available = False
        for index, directory in enumerate(tdx_dirs, start=1):
            path = resolve_path(directory)
            exists = path.exists()
            readable_files = list(path.rglob("*"))[:5] if exists and path.is_dir() else []
            status = "PASS" if exists and readable_files else "FAIL"
            local_tdx_available = local_tdx_available or status == "PASS"
            _row(rows, f"TDX-{index:03d}", "tdx local dir readable", "tdx", status, "exists with readable files", f"exists={exists}, files={len(readable_files)}", str(path), "本地 TDX 不可用时不能选择 no-network 更新。")

    modules = {
        "akshare": "akshare",
        "pytdx": "pytdx",
        "py_mini_racer": "py_mini_racer",
        "efinance": "efinance",
        "baostock": "baostock",
        "adata": "adata",
    }
    import_status: dict[str, bool] = {}
    for provider, module in modules.items():
        present = _has_import(module)
        import_status[provider] = present
        if provider == "py_mini_racer":
            status = "PASS" if present else "WARN"
        else:
            status = "PASS" if present else "WARN"
        _row(rows, f"IMPORT-{provider}", f"{module} import", provider, status, "importable", present, module, "缺少 provider 依赖时相关数据源不可用。")

    token_checks = {
        "tushare": "TUSHARE_TOKEN",
        "jqdata_username": str(data_cfg.get("jqdata", {}).get("username_env", "JQDATA_USERNAME")),
        "jqdata_password": str(data_cfg.get("jqdata", {}).get("password_env", "JQDATA_PASSWORD")),
    }
    token_status: dict[str, bool] = {}
    for provider, env_name in token_checks.items():
        present = _token_present(env_name)
        token_status[provider] = present
        _row(rows, f"TOKEN-{provider}", f"{env_name} present", provider, "PASS" if present else "WARN", "present if provider required", present, env_name, "报告只记录 token_present，不输出 token 原文。")

    provider_health = _json_optional("provider_health/latest.json")
    provider_date = str(provider_health.get("as_of_date", ""))
    provider_failures = _provider_failures(provider_health)
    provider_stale = bool(provider_date and target and _parse_date(provider_date) is not None and _parse_date(target) is not None and _parse_date(provider_date) < _parse_date(target))
    _row(rows, "HEALTH-001", "provider_health exists", "provider_health", "PASS" if provider_health else "WARN", "exists", bool(provider_health), "provider_health/latest.json", "缺少 provider health 时不能确认上一轮 provider 状态。")
    _row(rows, "HEALTH-002", "provider_health date", "provider_health", "WARN" if provider_stale else "PASS" if provider_date else "WARN", f">= {target}", provider_date or "missing", "provider_health/latest.json", "provider health 过期时需要先做 provider 验证。")
    _row(rows, "HEALTH-003", "provider failures", "provider_health", "WARN" if provider_failures else "PASS", "0", len(provider_failures), "provider_health/latest.json", "存在失败 provider 时需审阅失败原因。")

    quality = _json_optional("data_quality/latest.json")
    quality_date = str(quality.get("as_of_date", ""))
    quality_stale = bool(quality_date and target and _parse_date(quality_date) is not None and _parse_date(target) is not None and _parse_date(quality_date) < _parse_date(target))
    _row(rows, "QUALITY-001", "data_quality exists", "data_quality", "PASS" if quality else "WARN", "exists", bool(quality), "data_quality/latest.json", "缺少 data quality 时需要重新生成。")
    _row(rows, "QUALITY-002", "data_quality date", "data_quality", "WARN" if quality_stale else "PASS" if quality_date else "WARN", f">= {target}", quality_date or "missing", "data_quality/latest.json", "data quality 过期时不能直接信任当前覆盖。")

    output_dirs = ["data/raw", "data/features", "data/curated", "provider_health", "data_quality", "reports/data_update", "reports/observation"]
    all_writable = True
    for index, directory in enumerate(output_dirs, start=1):
        writable = _path_writable(directory)
        all_writable = all_writable and writable
        _row(rows, f"WRITE-{index:03d}", "output directory writable", "filesystem", "PASS" if writable else "FAIL", "writable", writable, directory, "输出目录不可写时禁止非 dry-run 更新。", secret_redacted=False)

    network_available = any(import_status.get(provider) for provider in ("akshare", "baostock", "efinance", "adata", "pytdx"))
    usable_source = local_tdx_available or (network_available and not no_network)
    if no_network and not local_tdx_available:
        _row(rows, "SOURCE-001", "no-network usable local source", "source", "FAIL", "local source available", False, "config/data_sources.yml", "--no-network 时必须有可用本地数据源。")
    else:
        _row(rows, "SOURCE-001", "at least one usable source", "source", "PASS" if usable_source else "FAIL", "usable source available", usable_source, "imports/config", "没有可用数据源时禁止非 dry-run 更新。")

    frame = pd.DataFrame(rows)
    if (frame["status"] == "FAIL").any():
        overall = "FAIL"
    elif (frame["status"] == "WARN").any():
        overall = "WARN"
    else:
        overall = "PASS"
    report = {
        **target_info,
        "status": overall,
        "no_network": no_network,
        "local_tdx_available": local_tdx_available,
        "network_provider_imports": import_status,
        "network_providers_available": network_available and not no_network,
        "token_present": token_status,
        "provider_health_date": provider_date,
        "provider_health_stale": provider_stale,
        "provider_failure_count": len(provider_failures),
        "provider_failure_summary": [
            {"method": item.get("method"), "adapter": item.get("adapter"), "error": str(item.get("error", ""))[:200]}
            for item in provider_failures[:20]
        ],
        "data_quality_date": quality_date,
        "data_quality_stale": quality_stale,
        "output_dirs_writable": all_writable,
        "checks": frame.to_dict(orient="records"),
    }
    if write_report:
        csv_path = resolve_path(output_csv)
        json_path = resolve_path(output_json)
        md_path = resolve_path(output_md)
        csv_path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(csv_path, index=False, quoting=csv.QUOTE_MINIMAL)
        json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        lines = [
            "# provider readiness report",
            "",
            f"- overall_status: {overall}",
            f"- as_of_date: {as_of_date}",
            f"- target_trading_date: {target or '无法解析'}",
            f"- local_tdx_available: {str(local_tdx_available).lower()}",
            f"- network_providers_available: {str(report['network_providers_available']).lower()}",
            f"- provider_health_date: {provider_date or 'missing'}",
            f"- provider_health_stale: {str(provider_stale).lower()}",
            f"- data_quality_date: {quality_date or 'missing'}",
            f"- data_quality_stale: {str(quality_stale).lower()}",
            "",
            "## checks",
            "",
        ]
        for row in frame.to_dict(orient="records"):
            lines.append(f"- {row['status']} | {row['check_id']} | {row['provider']} | {row['check_name']} | actual={row['actual']} | {row['recommendation']}")
        md_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Check market data provider readiness without printing secrets.")
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--target-trading-date", default="")
    parser.add_argument("--no-network", action="store_true")
    parser.add_argument("--write-report", action="store_true")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    report = check_provider_readiness(
        args.as_of_date,
        target_trading_date=args.target_trading_date or None,
        no_network=args.no_network,
        write_report=args.write_report,
    )
    return 1 if report["status"] == "FAIL" else 0


if __name__ == "__main__":
    raise SystemExit(main())
