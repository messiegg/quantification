from __future__ import annotations

import subprocess

from scripts import audit_data_update_cli as audit


def test_audit_data_update_cli_missing_script_fails(monkeypatch) -> None:
    monkeypatch.setattr(audit, "SCRIPTS", ["scripts/not_a_real_update_script.py"])
    frame = audit.audit_data_update_cli(write_report=False)
    assert frame.iloc[0]["status"] == "FAIL"
    assert bool(frame.iloc[0]["exists"]) is False


def test_audit_data_update_cli_start_end_fallback_warns_and_builds_command(monkeypatch) -> None:
    monkeypatch.setattr(audit, "SCRIPTS", ["scripts/update_market_data.py", "scripts/build_features.py"])

    def fake_help(script_path: str) -> subprocess.CompletedProcess[str]:
        if script_path == "scripts/update_market_data.py":
            stdout = "usage: update --start-date START --end-date END --all-stocks"
        else:
            stdout = "usage: features --start-date START --end-date END"
        return subprocess.CompletedProcess([script_path, "--help"], 0, stdout=stdout, stderr="")

    monkeypatch.setattr(audit, "_run_help", fake_help)
    frame = audit.audit_data_update_cli(write_report=False)
    assert audit.cli_status(frame) == "WARN"
    assert frame.loc[frame["script_path"] == "scripts/update_market_data.py", "status"].iloc[0] == "WARN"
    commands, status = audit.build_update_commands("2026-04-30", next_missing_date="2026-04-07", audit_frame=frame)
    assert status == "OK"
    assert commands[0] == [
        audit.project_python_command(),
        "scripts/update_market_data.py",
        "--start-date",
        "2026-04-07",
        "--end-date",
        "2026-04-30",
        "--all-stocks",
    ]
    assert commands[1] == [
        audit.project_python_command(),
        "scripts/build_features.py",
        "--start-date",
        "2026-04-07",
        "--end-date",
        "2026-04-30",
    ]
