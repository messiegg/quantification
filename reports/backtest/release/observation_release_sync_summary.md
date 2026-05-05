# observation 发布同步总结

## 验证目标

- 当前验证目标分支: codex/combined-v2-rc-release
- 当前本地分支: codex/combined-v2-rc-release
- verified_target_commit_at_generation: e3d6d7c8dfc0afbbe93cdc9dee3e74f813519a4f
- remote_branch_hash_at_generation: REMOTE_CHECK_UNAVAILABLE
- final_commit_after_report_commit: see final operator response

## 本地工作区状态

- status_before_report_refresh:
  - `M .github/workflows/ci.yml`
  - ` M README.md`
  - ` M pytest.ini`
  - ` M reports/backtest/audit/report_path_sanitization_check.csv`
  - ` M reports/backtest/audit/report_path_sanitization_check.md`
  - ` M reports/backtest/audit/stale_report_check.md`
  - ` M reports/backtest/release/combined_v2_rc_verify.csv`
  - ` M reports/backtest/release/combined_v2_rc_verify.md`
  - ` M reports/backtest/release/observation_release_sync_summary.md`
  - ` M reports/backtest/release/observation_sync_check.csv`
  - ` M reports/backtest/release/observation_sync_check.md`
  - ` M reports/backtest/release/release_sync_consistency_check.csv`
  - ` M reports/backtest/release/release_sync_consistency_check.md`
  - ` M scripts/check_release_sync_consistency.py`
  - ` M scripts/check_report_freshness.py`
  - ` M scripts/check_report_path_sanitization.py`
  - ` M scripts/verify_combined_v2_rc.py`
  - ` M tests/test_observation_gate_consistency.py`
  - ` M tests/test_provider_readiness.py`
  - ` M tests/test_safe_data_update.py`
  - ` M tests/test_strict_universe_smoke.py`
  - `?? config/release_file_allowlist.yml`
  - `?? docs/ci_and_local_validation.md`
  - `?? docs/pr_checklist.md`
  - `?? docs/release_checklist.md`
  - `?? reports/backtest/release/forbidden_tracked_files_check.csv`
  - `?? reports/backtest/release/forbidden_tracked_files_check.md`
  - `?? reports/backtest/release/release_guard_report.csv`
  - `?? reports/backtest/release/release_guard_report.md`
  - `?? scripts/check_forbidden_tracked_files.py`
  - `?? scripts/run_release_guard.py`
  - `?? tests/test_ci_markers.py`
  - `?? tests/test_forbidden_tracked_files.py`
  - `?? tests/test_release_guard.py`
- files_modified_by_this_refresh:
  - `reports/backtest/release/observation_sync_check.csv`
  - `reports/backtest/release/observation_sync_check.md`
  - `reports/backtest/release/observation_release_sync_summary.md`
- 说明: 上述 refresh 文件属于本轮报告同步修复范围，不代表发布状态过期。

## observation 文件跟踪状态

- 应跟踪文件数量: 45
- 已跟踪数量: 45
- 未跟踪数量: 0
- 真实 paper ledger ignored: 是

## 2026-05-04 data freshness

- data_freshness: ALLOW
- target_trading_date: 2026-04-30
- data_max_date: 2026-04-30
- feature_max_date: 2026-04-30
- benchmark_max_date: 2026-04-30
- stale_calendar_days: 4
- stale_trading_days: 0
- allowed_actions: observation_report_allowed

## observation pipeline

- blocking_reason: NONE
- action_allowed: true
- manual_order_list exists locally: 是
- manual_order_list tracked_by_git: 否
- manual_order_list ignored_by_git: 是

## RC verify

- RC verify: PASS
- annual_return: 0.0713520247687258
- cumulative_return: 0.2196444045310004
- max_drawdown: -0.0936454742991675
- total_trades: 76
- final_nav: 243928.8809062001

## pytest

- pytest: 184 passed, 2 warnings in 83.97s

## 结论

- 可以提交这轮报告同步修复。
- 不涉及策略变更。
- 不涉及数据更新。
- 观察期输出只允许下一交易日人工复核。
- 不允许自动下单或接券商。
