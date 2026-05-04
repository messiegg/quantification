from __future__ import annotations

from pathlib import Path

from scripts import check_provider_readiness as readiness


def _target_info() -> dict:
    return {
        "requested_as_of_date": "2026-05-04",
        "requested_as_of_is_trading_day": False,
        "target_trading_date": "2026-04-30",
        "target_trading_date_is_valid": True,
        "calendar_source": "fixture",
        "calendar_min_date": "2026-04-01",
        "calendar_max_date": "2026-04-30",
        "calendar_market": "A_SHARE",
    }


def test_provider_readiness_reports_do_not_leak_token(monkeypatch, tmp_path: Path) -> None:
    secret = "SUPER_SECRET_TUSHARE_TOKEN"
    monkeypatch.setenv("TUSHARE_TOKEN", secret)
    monkeypatch.setattr(readiness, "resolve_target_trading_date", lambda *args, **kwargs: _target_info())
    report = readiness.check_provider_readiness(
        "2026-05-04",
        write_report=True,
        output_json=tmp_path / "provider.json",
        output_md=tmp_path / "provider.md",
        output_csv=tmp_path / "provider.csv",
    )
    assert report["token_present"]["tushare"] is True
    for path in (tmp_path / "provider.json", tmp_path / "provider.md", tmp_path / "provider.csv"):
        assert secret not in path.read_text(encoding="utf-8")


def test_provider_readiness_handles_missing_tdx_dir_without_exception(monkeypatch, tmp_path: Path) -> None:
    missing = tmp_path / "missing_vipdoc"

    def fake_yaml(path):
        if str(path) == "config/data_sources.yml":
            return {"tdx": {"local_dirs": [str(missing)]}, "jqdata": {}}
        if str(path) == "config/observation.yml":
            return {"observation": {"calendar_market": "A_SHARE"}}
        return {}

    monkeypatch.setattr(readiness, "load_yaml_optional", fake_yaml)
    monkeypatch.setattr(readiness, "resolve_target_trading_date", lambda *args, **kwargs: _target_info())
    monkeypatch.setattr(readiness, "_has_import", lambda module: False)
    report = readiness.check_provider_readiness("2026-05-04", write_report=False)
    tdx_rows = [row for row in report["checks"] if row["provider"] == "tdx"]
    assert tdx_rows
    assert tdx_rows[0]["status"] == "FAIL"
    assert report["local_tdx_available"] is False


def test_provider_readiness_no_network_requires_local_source(monkeypatch) -> None:
    monkeypatch.setattr(readiness, "resolve_target_trading_date", lambda *args, **kwargs: _target_info())
    monkeypatch.setattr(readiness, "_has_import", lambda module: True)
    report = readiness.check_provider_readiness("2026-05-04", no_network=True, write_report=False)
    source_rows = [row for row in report["checks"] if row["check_id"] == "SOURCE-001"]
    assert source_rows
    assert source_rows[0]["status"] == "FAIL"
    assert report["status"] == "FAIL"
