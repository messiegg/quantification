# 回测完整性审计

- 审计结论: PASS
- 固定区间: 2023-04-03 到 2026-04-03
- baseline next_bar: 年化 0.10%，成交 7 笔，最大回撤 -1.66%
- combined_v2 next_bar: 年化 7.14%，成交 76 笔，最大回撤 -9.36%

## 检查项

- INT-001 PASS [both]: 账户与执行成本一致。证据：initial_capital=200000, fee=0.0003, tax=0.0005, slippage_bps=5, lot=100, min_trade=5000
- INT-002 PASS [both]: baseline 与 combined_v2 日期一致。证据：features_start=2023-04-03, features_end=2026-04-03
- INT-003 PASS [both]: 交易日历与 benchmark 一致。证据：feature_days=727, benchmark_days=727
- INT-004 PASS [both]: compare 账户状态互不污染。证据：compare script constructs separate baseline_engine and v2_engine instances
- INT-005 PASS [both]: diagnostics 不改变策略行为。证据：writing diagnostics left trades and metrics unchanged
- INT-006 PASS [both]: strategy_config 与 universe_config 未串线。证据：baseline uses config/strategy.yml + config/universe_rules.yml; v2 uses config/strategy_v2.yml + config/universe_rules_v2.yml
- INT-007 PASS [both]: historical_universe_dir 按 profile 读取。证据：baseline=data/curated/universe_history; combined_v2=reports/backtest/combined_v2_universe_history
- INT-008-baseline PASS [baseline]: 最终权益等于现金加持仓市值。证据：final_equity=200595.82, nav_last=200595.82
- INT-009-baseline PASS [baseline]: 逐笔交易 cash_after 可复算。证据：violations=0, trades=7
- INT-010-baseline PASS [baseline]: 交易订单满足整手、最小成交额、现金和仓位约束。证据：{'lot': 0, 'min_amount': 0, 'cash': 0, 'single': 0, 'exposure': 0}
- INT-008-combined_v2 PASS [combined_v2]: 最终权益等于现金加持仓市值。证据：final_equity=243928.88, nav_last=243928.88
- INT-009-combined_v2 PASS [combined_v2]: 逐笔交易 cash_after 可复算。证据：violations=0, trades=76
- INT-010-combined_v2 PASS [combined_v2]: 交易订单满足整手、最小成交额、现金和仓位约束。证据：{'lot': 0, 'min_amount': 0, 'cash': 0, 'single': 0, 'exposure': 0}
- INT-011 PASS [baseline]: baseline 结果可复现。证据：annual_return=0.10%, total_trades=7
- INT-012-LEGACY WARN [combined_v2]: legacy pre-PIT 结果已废弃。证据：legacy same_close / pre-PIT result was 9.14% / 83 trades, now superseded by PIT-corrected result 7.14% / 76 trades
- INT-013-CURRENT-PIT-STRICT PASS [combined_v2]: combined_v2 当前 PIT 严格主口径可复现。证据：profile=combined_v2, execution_mode=next_bar, annual_return=7.14%, cumulative_return=21.96%, max_drawdown=-9.36%, total_trades=76
