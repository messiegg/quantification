from __future__ import annotations

import configparser
from pathlib import Path

import pytest
import yaml

from scripts import verify_combined_v2_rc as verify_mod


ROOT = Path(__file__).resolve().parents[1]


def test_pytest_markers_are_declared() -> None:
    parser = configparser.ConfigParser()
    parser.read(ROOT / "pytest.ini", encoding="utf-8")
    markers = parser.get("pytest", "markers")
    for marker in ("data_required", "full_backtest", "release_guard", "observation", "no_network"):
        assert f"{marker}:" in markers


def test_ci_lightweight_command_excludes_data_required_and_full_backtest() -> None:
    workflow = yaml.safe_load((ROOT / ".github" / "workflows" / "ci.yml").read_text(encoding="utf-8"))
    runs = []
    for job in workflow["jobs"].values():
        for step in job.get("steps", []):
            if "run" in step:
                runs.append(step["run"])
    joined = "\n".join(runs)
    assert 'python -m pytest -q -m "not data_required and not full_backtest"' in joined
    assert "python scripts/run_release_guard.py --ci --as-of-date 2026-05-04" in joined


def test_verify_combined_v2_rc_hash_only_does_not_rerun_backtest(monkeypatch: pytest.MonkeyPatch) -> None:
    def fail_rerun(*args, **kwargs):
        raise AssertionError("hash-only mode must not rerun the full backtest")

    monkeypatch.setattr(verify_mod, "_rerun_metrics", fail_rerun)
    frame = verify_mod.verify_release_candidate(mode="hash-only", write_report=False)
    failures = frame[frame["status"] == "FAIL"]
    assert failures[~failures["check_id"].astype(str).str.startswith("CFG-")].empty
    metrics = frame[frame["check_id"].astype(str).str.startswith("MET-")]
    assert set(metrics["status"]) == {"PASS"}
    mode = frame[frame["check_id"] == "MODE-001"].iloc[0]
    assert mode["actual"] == "hash-only"
