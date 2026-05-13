from __future__ import annotations

import csv
import json
from pathlib import Path

from scripts import check_observation_readiness as smoke


def _patch_resolve(monkeypatch, tmp_path: Path) -> None:
    def fake_resolve(path: str | Path) -> Path:
        candidate = Path(path)
        return candidate if candidate.is_absolute() else tmp_path / candidate

    monkeypatch.setattr(smoke, "resolve_path", fake_resolve)


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def _write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = ["check_id", "check_name", "status", "expected", "actual", "evidence", "recommendation"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for row in rows:
            writer.writerow({field: row.get(field, "") for field in fields})


def _write_ready_fixture(tmp_path: Path, *, manifest_overrides: dict | None = None, verify_rows: list[dict] | None = None, guard_rows: list[dict] | None = None) -> None:
    manifest = {
        "status": "WARN",
        "account_profile": "retail_50k_lot_aware",
        "manual_review_required": True,
        "auto_trading_approved": False,
        "broker_integration_enabled": False,
        "llm_decision_allowed": False,
    }
    manifest.update(manifest_overrides or {})
    _write_json(tmp_path / smoke.MANIFEST_PATH, manifest)
    _write_csv(
        tmp_path / smoke.VERIFY_CSV_PATH,
        verify_rows
        or [
            {"check_id": "MODE-001", "check_name": "verification mode", "status": "PASS"},
            {"check_id": "CFG-002", "check_name": "config/strategy_v2.yml sha256 matches RC manifest", "status": "PASS", "evidence": "config/strategy_v2.yml"},
            {"check_id": "CODE-001", "check_name": "strategy code hash drift", "status": "PASS", "actual": "no drift"},
        ],
    )
    _write_csv(
        tmp_path / smoke.RELEASE_GUARD_CSV_PATH,
        guard_rows
        or [
            {"check_id": "RG-ACCOUNT-003", "check_name": "default account warning", "status": "WARN", "actual": "default=actual_50k_lot_aware; ratio=0.03"},
            {"check_id": "RG-005", "check_name": "RC verify", "status": "PASS", "actual": "PASS=32 WARN=0 FAIL=0"},
        ],
    )


def test_ready_for_observation_allows_guard_warn_without_fail(monkeypatch, tmp_path: Path) -> None:
    _patch_resolve(monkeypatch, tmp_path)
    _write_ready_fixture(tmp_path)

    payload = smoke.build_observation_readiness_check(write_report=False)

    assert payload["status"] == smoke.READY
    assert payload["release_guard_status"] == "WARN"
    assert payload["release_guard_fail_count"] == 0
    assert payload["rc_verify_status"] == "PASS"
    assert payload["code_hash_drift"] is False
    assert payload["config_hash_drift"] is False
    assert payload["release_pass_approved"] is False


def test_verify_fail_is_not_ready(monkeypatch, tmp_path: Path) -> None:
    _patch_resolve(monkeypatch, tmp_path)
    _write_ready_fixture(tmp_path, verify_rows=[{"check_id": "MET-total_trades", "check_name": "metric", "status": "FAIL"}])

    payload = smoke.build_observation_readiness_check(write_report=False)

    assert payload["status"] == smoke.NOT_READY
    assert payload["rc_verify_fail_count"] == 1


def test_guard_fail_is_not_ready(monkeypatch, tmp_path: Path) -> None:
    _patch_resolve(monkeypatch, tmp_path)
    _write_ready_fixture(tmp_path, guard_rows=[{"check_id": "RG-STATUS-001", "check_name": "release status", "status": "FAIL"}])

    payload = smoke.build_observation_readiness_check(write_report=False)

    assert payload["status"] == smoke.NOT_READY
    assert payload["release_guard_fail_count"] == 1


def test_code_drift_is_not_ready(monkeypatch, tmp_path: Path) -> None:
    _patch_resolve(monkeypatch, tmp_path)
    _write_ready_fixture(
        tmp_path,
        verify_rows=[
            {"check_id": "MODE-001", "check_name": "verification mode", "status": "PASS"},
            {"check_id": "CODE-001", "check_name": "strategy code hash drift", "status": "WARN", "actual": "src/strategy/signals.py"},
        ],
    )

    payload = smoke.build_observation_readiness_check(write_report=False)

    assert payload["status"] == smoke.NOT_READY
    assert payload["code_hash_drift"] is True


def test_non_50k_default_account_is_not_ready(monkeypatch, tmp_path: Path) -> None:
    _patch_resolve(monkeypatch, tmp_path)
    _write_ready_fixture(tmp_path, manifest_overrides={"account_profile": "reference_200k"})

    payload = smoke.build_observation_readiness_check(write_report=False)

    assert payload["status"] == smoke.NOT_READY
    assert any(row["check_id"] == "OBS-DEFAULT-ACCOUNT" for row in payload["not_ready_reasons"])


def test_ready_check_does_not_modify_manifest_status(monkeypatch, tmp_path: Path) -> None:
    _patch_resolve(monkeypatch, tmp_path)
    _write_ready_fixture(tmp_path)
    manifest_path = tmp_path / smoke.MANIFEST_PATH
    before = manifest_path.read_text(encoding="utf-8")

    payload = smoke.build_observation_readiness_check(write_report=True)
    after = manifest_path.read_text(encoding="utf-8")

    assert payload["status"] == smoke.READY
    assert before == after
    assert (tmp_path / smoke.OUT_JSON).exists()
    assert (tmp_path / smoke.OUT_MD).exists()
    assert (tmp_path / smoke.OUT_CSV).exists()


def test_smoke_check_is_manual_only_and_does_not_touch_real_account_or_broker(monkeypatch, tmp_path: Path) -> None:
    _patch_resolve(monkeypatch, tmp_path)
    _write_ready_fixture(tmp_path)

    payload = smoke.build_observation_readiness_check(write_report=False)

    assert payload["reads_real_account"] is False
    assert payload["generates_real_orders"] is False
    assert payload["auto_trading_approved"] is False
    assert payload["broker_integration_enabled"] is False
    assert payload["llm_decision_allowed"] is False
    assert smoke.READ_ONLY_INPUTS == [smoke.MANIFEST_PATH, smoke.VERIFY_CSV_PATH, smoke.RELEASE_GUARD_CSV_PATH]
