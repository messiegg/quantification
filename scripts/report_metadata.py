from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

import yaml

from src.utils.config import resolve_path


ACTIVE_RUNTIME_CONFIG_PATHS = [
    "config/strategy_v2.yml",
    "config/account.yml",
    "config/universe_rules_v2.yml",
    "config/metric_map.yml",
    "config/data_sources.yml",
    "config/observation.yml",
    "config/observation_readiness.yml",
]


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def git_stdout(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=resolve_path("."),
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        check=False,
    )
    return result.stdout.strip() if result.returncode == 0 else ""


def git_commit() -> str:
    return git_stdout(["rev-parse", "HEAD"])


def git_branch() -> str:
    return git_stdout(["branch", "--show-current"])


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_path(path_like: str | Path) -> str:
    path = resolve_path(path_like)
    if not path.exists() or not path.is_file():
        return ""
    return sha256_bytes(path.read_bytes())


def stable_json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=str)


def stable_hash(value: Any) -> str:
    return sha256_bytes(stable_json_dumps(value).encode("utf-8"))


def load_yaml_file(path_like: str | Path) -> dict[str, Any]:
    path = resolve_path(path_like)
    if not path.exists():
        return {}
    data = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return data if isinstance(data, dict) else {}


def config_hash(paths: Iterable[str | Path] | None = None) -> str:
    items: list[dict[str, Any]] = []
    for path_like in paths or ACTIVE_RUNTIME_CONFIG_PATHS:
        path = resolve_path(path_like)
        item = {
            "path": str(path_like),
            "exists": path.exists(),
            "sha256": sha256_path(path),
        }
        items.append(item)
    return stable_hash(items)


def config_file_hashes(paths: Iterable[str | Path] | None = None) -> list[dict[str, Any]]:
    return [
        {"path": str(path_like), "exists": resolve_path(path_like).exists(), "sha256": sha256_path(path_like)}
        for path_like in (paths or ACTIVE_RUNTIME_CONFIG_PATHS)
    ]


def data_hash(paths: Iterable[str | Path] | None = None) -> str:
    """Hash lightweight file metadata for data artifacts without reading large parquet bodies."""
    default_paths = [
        "data/curated/run_manifest.json",
        "data_quality/latest.json",
        "provider_health/latest.json",
        "data/features/latest_feature_snapshot.parquet",
        "data/raw/benchmark_daily.parquet",
        "config/universe.yml",
    ]
    items: list[dict[str, Any]] = []
    for path_like in paths or default_paths:
        path = resolve_path(path_like)
        if path.exists() and path.is_file():
            stat = path.stat()
            digest = sha256_path(path) if stat.st_size <= 5_000_000 else ""
            items.append(
                {
                    "path": str(path_like),
                    "exists": True,
                    "size": stat.st_size,
                    "mtime_ns": stat.st_mtime_ns,
                    "sha256": digest,
                    "sha256_skipped": digest == "",
                }
            )
        else:
            items.append({"path": str(path_like), "exists": False})
    return stable_hash(items)


def status_from_children(statuses: Iterable[str]) -> str:
    normalized = {str(item).upper() for item in statuses if str(item)}
    if "FAIL" in normalized:
        return "FAIL"
    if "WARN" in normalized:
        return "WARN"
    return "PASS"


def write_json(path_like: str | Path, payload: dict[str, Any]) -> Path:
    path = resolve_path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n", encoding="utf-8")
    return path


def metadata_header(
    *,
    requested_date: str = "",
    target_trade_date: str = "",
    extra_config_paths: Iterable[str | Path] | None = None,
) -> dict[str, Any]:
    paths = list(ACTIVE_RUNTIME_CONFIG_PATHS)
    if extra_config_paths:
        for path in extra_config_paths:
            if str(path) not in paths:
                paths.append(str(path))
    return {
        "generated_at": now_utc_iso(),
        "git_commit": git_commit(),
        "branch": git_branch(),
        "config_hash": config_hash(paths),
        "config_files": config_file_hashes(paths),
        "data_hash": data_hash(),
        "requested_date": requested_date,
        "target_trade_date": target_trade_date,
        "manual_review_required": True,
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
    }
