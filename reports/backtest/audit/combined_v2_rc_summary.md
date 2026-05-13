# combined_v2 RC 总结

- 最终评级: FAIL_RESEARCH_ONLY
- 评级边界: 这是“小资金手动试运行候选”评级，不是自动实盘策略评级；本仓库仍禁止自动下单和券商 API。

## 当前严格主口径

- combined_v2 PIT next_bar。
- 当前严谨结果: 年化 2.48%，累计 7.33%，最大回撤 -8.88%，夏普 0.36，成交 41，平均日仓位 44.59%，最大持仓数 8。
- 9.14% / 83 笔是旧口径，已被废弃；不作为当前主策略复现标准。

## 报告口径修复状态

- monthly_returns 复合一致: 是，diff=0.000000000000。
- open position holding days 已修复: 未平仓统计到回测结束日。
- signal attribution 已按 entry_signal / exit_signal / entry_exit_pair 归因。
- regime attribution 已使用 daily MTM，并保留 trade realization 对照。
- bucket / industry attribution 已统一 total_pnl 口径。
- markdown / CSV consistency: WARN。

## 审计状态

- integrity: FAIL
- lookahead audit status: WARN，确认违规 0 条
- universe PIT: future-data 文件 0 个
- execution mode: PASS，next_bar 为严格主口径
- report consistency: WARN
- cost stress: high_cost 年化 1.46%
- sensitivity: near_zero 0/6，under_baseline 0/6

## control baseline 结果

- v2 是否优于 universe equal weight: 是。
- v2 是否优于 top score monthly: 是。
- v2 是否优于 random placebo: percentile 28.0%。
- defensive_only / cyclical_only: 5.82% / 2.81%。
- no_high_dividend_supplement: 8.11%。
- no_grid: 5.80%。
- no_trend_stop: 8.23%。
- risk_off_no_new_buy: 6.68%。

## v2_1_risk_guard

- 年化 1.99%，回撤 -4.27%，交易 21。
- 不替换 v2；可作为保守观察候选。

## 主要风险

- 三年样本偏短。
- A 股风格切换可能导致当前 bucket 和估值分位逻辑失效。
- risk_off daily MTM 损失仍明显。
- no_high_dividend_supplement 和 no_trend_stop 对照结果提示部分模块需要后续研究，但不能直接删除。
- 数据更新滞后到 2026-04-03，不能生成 2026-05-04 实盘日报。

## 最终建议

- combined_v2 是否保留为主候选: 是，前提是继续使用 PIT next_bar 严格口径。
- combined_v2_1_risk_guard 是否值得继续观察: 取决于上面的 v2_1 对比标签，不自动替换 v2。
- 已证明有贡献或需要保留观察的模块: PIT 股票池、defensive/cyclical 双 bucket、严格 next_bar 审计、成本压力和敏感性检查。
- 贡献不足或需后续研究的模块: 见 no_grid、no_trend_stop、risk_off_no_new_buy 和 signal attribution 的对照结果。
- 是否可进入小资金手动试运行候选阶段: 由最终评级决定；即便 PASS_CANDIDATE，也只能小资金、手动、继续观察，不能自动下单。

## 降级项

- integrity_audit 存在非 legacy FAIL。
- combined_v2 随机 placebo 年化分位只有 28.0%。
- 最大单股贡献 81.06% 超过 50%。
- 最大行业贡献 75.42% 超过 70%。
- lookahead 审计仍有非确认前视的 WARN，例如字段缺失或报告口径提示。
- report_consistency_check 存在 WARN。
