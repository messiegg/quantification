# 回测完整性审计

- 审计结论: FAIL
- git_commit: fcbad4f7fd70542596dcb7537dba4e7ea41a84c9
- config_hash: 6817ac43cf178fea81d0976750c1269eba0c1b2f4a2e0e6c4f4e7c1f16eaf1d5
- data_hash: ea7c14af5f4b454e5e18df55b7c8851fcaa28170542dccc4a7d598f0b7426c7e
- 固定区间: 2023-04-03 到 2026-04-03
- baseline next_bar: 年化 -0.08%，成交 2 笔，最大回撤 -0.30%
- combined_v2 next_bar: 年化 2.48%，成交 41 笔，最大回撤 -8.88%

## 检查项

- INT-001 PASS [both]: 账户与执行成本一致。证据：initial_capital=50000, fee=0.0003, tax=0.0005, slippage_bps=5, lot=100, min_trade=1500
- INT-002 PASS [both]: baseline 与 combined_v2 日期一致。证据：features_start=2023-04-03, features_end=2026-04-03
- INT-003 PASS [both]: 交易日历与 benchmark 一致。证据：feature_days=727, benchmark_days=727
- INT-004 PASS [both]: compare 账户状态互不污染。证据：compare script constructs separate baseline_engine and v2_engine instances
- INT-005 PASS [both]: diagnostics 不改变策略行为。证据：writing diagnostics left trades and metrics unchanged
- INT-006 PASS [both]: strategy_config 与 universe_config 未串线。证据：baseline uses config/strategy.yml + config/universe_rules.yml; v2 uses config/strategy_v2.yml + config/universe_rules_v2.yml
- INT-007 PASS [both]: historical_universe_dir 按 profile 读取。证据：baseline=data/curated/universe_history; combined_v2=reports/backtest/combined_v2_universe_history
- INT-008-baseline PASS [baseline]: 最终权益等于现金加持仓市值。证据：final_equity=49888.98, nav_last=49888.98
- INT-009-baseline PASS [baseline]: 逐笔交易 cash_after 可复算。证据：violations=0, trades=2
- INT-010-baseline PASS [baseline]: 交易订单满足整手、最小成交额、现金和仓位约束。证据：{'lot': 0, 'min_amount': 0, 'cash': 0, 'single': 0, 'exposure': 0}
- INT-008-combined_v2 PASS [combined_v2]: 最终权益等于现金加持仓市值。证据：final_equity=53663.28, nav_last=53663.28
- INT-009-combined_v2 PASS [combined_v2]: 逐笔交易 cash_after 可复算。证据：violations=0, trades=41
- INT-010-combined_v2 PASS [combined_v2]: 交易订单满足整手、最小成交额、现金和仓位约束。证据：{'lot': 0, 'min_amount': 0, 'cash': 0, 'single': 0, 'exposure': 0}
- INT-011 FAIL [baseline]: baseline 结果可复现。证据：annual_return=-0.08%, total_trades=2
- INT-012-LEGACY WARN [combined_v2]: legacy pre-PIT 结果已废弃。证据：legacy same_close / pre-PIT result was 9.14% / 83 trades, now superseded by PIT-corrected result 7.14% / 76 trades
- INT-013-CURRENT-PIT-STRICT FAIL [combined_v2]: combined_v2 当前 PIT 严格主口径可复现。证据：profile=combined_v2, execution_mode=next_bar, annual_return=2.48%, cumulative_return=7.33%, max_drawdown=-8.88%, total_trades=41
