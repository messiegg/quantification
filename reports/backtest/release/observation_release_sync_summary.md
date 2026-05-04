# observation 发布同步总结

## 验证目标

- 当前验证目标分支: codex/combined-v2-rc-release
- 当前本地分支: codex/combined-v2-rc-release
- verified_target_commit_at_generation: cfce6cb5839bb30b93032cfbbb6fd535d3bf7590
- remote_branch_hash_at_generation: REMOTE_CHECK_UNAVAILABLE
- final_commit_after_report_commit: see final operator response

## 本地工作区状态

- status_before_report_refresh:
  - `M  README.md`
  - ` M reports/backtest/audit/stale_report_check.csv`
  - ` M reports/backtest/audit/stale_report_check.md`
  - `MM reports/backtest/release/observation_release_sync_summary.md`
  - `MM reports/backtest/release/observation_sync_check.csv`
  - `MM reports/backtest/release/observation_sync_check.md`
  - `AM reports/backtest/release/release_sync_consistency_check.csv`
  - `AM reports/backtest/release/release_sync_consistency_check.md`
  - ` M reports/observation/2026-05-04/observation_run_manifest.json`
  - `A  scripts/check_release_sync_consistency.py`
  - `M  scripts/check_report_freshness.py`
  - `A  tests/test_release_sync_consistency.py`
- files_modified_by_this_refresh:
  - `reports/backtest/release/observation_sync_check.csv`
  - `reports/backtest/release/observation_sync_check.md`
  - `reports/backtest/release/observation_release_sync_summary.md`
- 说明: 上述 refresh 文件属于本轮报告同步修复范围，不代表发布状态过期。

## observation 文件跟踪状态

- 应跟踪文件数量: 33
- 已跟踪数量: 33
- 未跟踪数量: 0
- 真实 paper ledger ignored: 是

## 2026-05-04 data freshness

- data_freshness: BLOCK
- data_max_date: 2026-04-03
- stale_calendar_days: 31
- allowed_actions: historical_review_only

## observation pipeline

- blocking_reason: STALE_DATA_BLOCKED
- action_allowed: false
- manual_order_list 未生成: 是

## RC verify

- RC verify: PASS
- annual_return: 0.0713520247687258
- cumulative_return: 0.2196444045310004
- max_drawdown: -0.0936454742991675
- total_trades: 76
- final_nav: 243928.8809062001

## pytest

- pytest: 137 passed, 2 warnings in 83.07s

## 结论

- 可以提交这轮报告同步修复。
- 不涉及策略变更。
- 不涉及数据更新。
- 不允许生成 2026-05-04 手工订单。
