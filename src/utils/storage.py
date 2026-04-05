from __future__ import annotations

import shutil
from pathlib import Path
import json

import pandas as pd

from src.utils.config import resolve_path


def clear_directories(paths: list[str | Path]) -> list[Path]:
    cleared: list[Path] = []
    for path_like in paths:
        path = resolve_path(path_like)
        if path.exists():
            try:
                shutil.rmtree(path)
            except FileNotFoundError:
                pass
            except OSError:
                shutil.rmtree(path, ignore_errors=True)
        path.mkdir(parents=True, exist_ok=True)
        cleared.append(path)
    return cleared


def configured_cache_directories(data_cfg: dict) -> list[str]:
    cache_cfg = data_cfg.get("cache", {})
    directories = [str(item) for item in cache_cfg.get("directories", []) if str(item).strip()]
    if directories:
        return directories
    raw_dir = str(data_cfg.get("storage", {}).get("raw_dir", "data/raw"))
    return [str(Path(raw_dir) / "akshare")]


def read_parquet_optional(path_like: str | Path) -> pd.DataFrame:
    path = resolve_path(path_like)
    if not path.exists():
        return pd.DataFrame()
    return pd.read_parquet(path)


def read_dataset_flex(path_like: str | Path) -> pd.DataFrame:
    path = resolve_path(path_like)
    if not path.exists():
        return pd.DataFrame()
    if path.is_file():
        return pd.read_parquet(path)
    files = sorted(path.glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    frames = [pd.read_parquet(file_path) for file_path in files]
    if not frames:
        return pd.DataFrame()
    return pd.concat(frames, ignore_index=True, sort=False)


def write_json_report(path_like: str | Path, payload: dict) -> Path:
    path = resolve_path(path_like)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def write_blocker_report(
    name: str,
    as_of_date: str,
    stage: str,
    categories: list[dict],
    output_dir: str | Path,
) -> Path:
    payload = {
        "name": name,
        "as_of_date": as_of_date,
        "stage": stage,
        "categories": categories,
    }
    target = resolve_path(output_dir) / f"{name}_{as_of_date}.json"
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    return target


def write_feature_dataset(frame: pd.DataFrame, output_path: str | Path) -> list[Path]:
    path = resolve_path(output_path)
    if path.suffix == ".parquet":
        path.parent.mkdir(parents=True, exist_ok=True)
        frame.to_parquet(path, index=False)
        return [path]

    if path.exists():
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)

    if frame.empty:
        empty_path = path / "empty.parquet"
        frame.to_parquet(empty_path, index=False)
        return [empty_path]

    years = pd.to_datetime(frame["date"], errors="coerce").dt.year.fillna(0).astype(int)
    written: list[Path] = []
    for year, group in frame.assign(_feature_year=years).groupby("_feature_year", sort=True):
        filename = "unknown.parquet" if int(year) <= 0 else f"{int(year)}.parquet"
        target = path / filename
        group.drop(columns=["_feature_year"]).to_parquet(target, index=False)
        written.append(target)
    return written
