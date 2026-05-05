# 参数敏感性测试

- 口径: combined_v2 next_bar，固定 2025-04-03 到 2026-04-03。
- mode: ci
- variant_timeout_seconds: 240
- 这是 one-at-a-time 扰动，不做参数优化，不输出最佳参数，不写回正式配置。
- sensitivity_status: WARN
- non_binding_parameters: cyclical_pb_threshold, defensive_valuation_threshold, grid_step, universe_size
- unknown_non_binding_count: 0
- error_variant_count: 0
- baseline next_bar 年化: 0.10%
- baseline 年化来源: /Users/meseg/shu/stocks/quantile/reports/backtest/compare_combined_vs_v2_metrics.csv
- 小幅收紧后是否仍有正收益: 是
- 小幅放宽后是否回撤失控: 否
- 年化接近 0 的变体数: 0/6
- 跑输 baseline 的变体数: 0/6
- 过拟合风险标记: 否

## 变体结果

- current_v2: 年化 12.13%，累计 11.62%，回撤 -2.02%，夏普 2.43，成交 26，平均仓位 37.28%，binding=BASELINE，reason=n/a，changed_action_days=0，run_status=PASS
- universe_large: 年化 12.13%，累计 11.62%，回撤 -2.02%，夏普 2.43，成交 26，平均仓位 37.28%，binding=NON_BINDING，reason=NO_SIGNAL_COVERAGE，changed_action_days=0，run_status=PASS
- defensive_valuation_strict: 年化 12.13%，累计 11.62%，回撤 -2.02%，夏普 2.43，成交 26，平均仓位 37.28%，binding=NON_BINDING，reason=NO_SIGNAL_COVERAGE，changed_action_days=0，run_status=PASS
- cyclical_pb_strict: 年化 12.13%，累计 11.62%，回撤 -2.02%，夏普 2.43，成交 26，平均仓位 37.28%，binding=NON_BINDING，reason=NO_SIGNAL_COVERAGE，changed_action_days=0，run_status=PASS
- holding_shorter: 年化 12.07%，累计 11.56%，回撤 -1.91%，夏普 2.50，成交 27，平均仓位 34.58%，binding=BINDING，reason=n/a，changed_action_days=1，run_status=PASS
- grid_tighter: 年化 12.13%，累计 11.62%，回撤 -2.02%，夏普 2.43，成交 26，平均仓位 37.28%，binding=NON_BINDING，reason=NO_SIGNAL_COVERAGE，changed_action_days=0，run_status=PASS
- position_conservative: 年化 3.86%，累计 3.70%，回撤 -1.99%，夏普 1.35，成交 13，平均仓位 19.05%，binding=BINDING，reason=n/a，changed_action_days=19，run_status=PASS
