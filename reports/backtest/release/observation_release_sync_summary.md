# observation 发布同步总结

- 当前分支名: codex/combined-v2-rc-release
- 当前 HEAD commit: 6d16a186b7ccdf06aaeed7882c7847cafddc0aaf
- 存在 untracked 文件: True
- 存在未暂存修改: True
- 存在已暂存但未提交修改: False

## observation 相关文件跟踪状态

- 当前报告生成时 observation 新文件尚未暂存；observation_sync_check 中标记为 ADD_TO_GIT。

## paper ledger ignore 状态

- data/observation/paper_account.yml: ignored=True; .gitignore:19:data/observation/paper_account.yml	data/observation/paper_account.yml
- data/observation/paper_trades.csv: ignored=True; .gitignore:20:data/observation/paper_trades.csv	data/observation/paper_trades.csv
- data/observation/paper_positions.yml: ignored=True; .gitignore:21:data/observation/paper_positions.yml	data/observation/paper_positions.yml

## 2026-05-04 freshness / pipeline

- data freshness: BLOCK
- data_max_date: 2026-04-03
- feature_max_date: 2026-04-03
- benchmark_max_date: 2026-04-03
- stale_calendar_days: 31
- allowed_actions: historical_review_only
- observation_pipeline blocking_reason: STALE_DATA_BLOCKED
- observation_pipeline action_allowed: False
- manual_order_list 未生成: True

## RC / tests

- stale_report_check: {'PASS': 7}
- verify_combined_v2_rc: {'PASS': 19}
- pytest: 130 passed, 2 warnings in 81.04s
- annual_return: 0.0713520247687258
- cumulative_return: 0.2196444045310004
- max_drawdown: -0.0936454742991675
- total_trades: 76
- final_nav: 243928.8809062001
- combined_v2 next_bar 结果保持不变: 是

## 提交 / 推送状态

- 最终是否可以提交: 是，前提是只暂存 observation gate、RC 验证、报告、docs、tests、example 模板和 .gitignore。
- 如果已经提交，commit hash: 报告生成时尚未提交；最终 commit hash 见本次执行记录。
- 如果已经 push，远端分支名和结果: 报告生成时尚未 push。
- 如果没有 push，需要执行: git push origin codex/combined-v2-rc-release
