# combined_v2 总审计结论

- 最终评级: FAIL
- 评级含义: 旧 9.14% / 83 笔为 LEGACY_SUPERSEDED 口径；当前审计不再要求复现 legacy 指标。

## 1. baseline vs combined_v2 主结果

- baseline next_bar: 年化 -0.08%，累计 -0.22%，最大回撤 -0.30%，成交 2。
- combined_v2 PIT next_bar: 年化 2.48%，累计 7.33%，最大回撤 -8.88%，成交 41。
- legacy pre-PIT / old same_close: 9.14% 年化、83 笔，已标记为 INT-012-LEGACY WARN，仅保留作历史记录。

## 2. same_close vs next_bar

- same_close: 年化 2.19%，累计 6.46%，最大回撤 -8.92%。
- next_bar: 年化 2.48%，累计 7.33%，最大回撤 -8.88%。
- next_bar 相对 same_close 年化变化 -13.35%。

## 3. 审计状态

- integrity: FAIL。
- lookahead audit status: WARN；确认违规 0 条。
- universe PIT: 月度文件 38 个，future-data 文件 0 个。
- execution mode: next_bar 为当前严格主口径。
- report consistency: WARN。
- cost stress high_cost: 年化 1.46%。
- sensitivity: 年化接近 0 的变体 0/6，跑输 baseline 的变体 0/6。

## 4. 收益归因修复

- monthly_returns: 最后一行复合差异 0.000000000000。
- open position holding days: 未平仓持仓统计到回测结束日，字段包含 is_open_position/open_position_days/realized_holding_days/total_holding_days_to_end。
- signal attribution: 已按 entry_signal / exit_signal / entry_exit_pair 归因。
- regime attribution: 已新增 daily MTM 口径，并与 trade realization 口径分开。
- bucket / industry attribution: 已统一 total_pnl 口径。
- markdown / CSV consistency: WARN。
- 最大单股贡献 81.06%，最大行业贡献 75.42%。

## 5. control baselines

- v2 vs universe equal weight: 7.14% vs -1.33%。
- v2 vs top score monthly: 7.14% vs 3.33%。
- random placebo percentile: 28.0%。
- defensive_only 年化 5.82%；cyclical_only 年化 2.81%。
- no_high_dividend_supplement 年化 8.11%。
- no_grid 年化 5.80%。
- no_trend_stop 年化 8.23%，只作风险解释。
- risk_off_no_new_buy 年化 6.68%。

## 6. v2_1_risk_guard

- 年化 1.99%，最大回撤 -4.27%，成交 21。
- v2_1 不覆盖 combined_v2；如果不明显优于 v2，不推荐替换。

## 7. 最大风险点

- integrity_audit 存在非 legacy FAIL。
- combined_v2 随机 placebo 年化分位只有 28.0%。
- 最大单股贡献 81.06% 超过 50%。
- 最大行业贡献 75.42% 超过 70%。
- lookahead 审计仍有非确认前视的 WARN，例如字段缺失或报告口径提示。
- report_consistency_check 存在 WARN。

## 8. 下一步建议

- 保留 combined_v2 为当前严格主候选，主口径固定为 PIT next_bar 7.14%/76 笔附近。
- 不追求恢复 legacy 9.14%，不继续放宽参数。
- 若进入观察，只能小资金、人工、继续审计，不能自动下单。
