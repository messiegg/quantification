# executable/raw 改善实验报告

- status: RESEARCH_ONLY
- default_release_profile_unchanged: actual_50k_lot_aware
- release_account_profile_unchanged: retail_50k_lot_aware
- auto_trading_approved: false
- broker_integration_enabled: false
- llm_decision_allowed: false
- not production ready
- baseline_exec_raw: 3.66%
- best_valid_variant: capital_200k_maxpos20 (18.94%)
- best_50k_realistic_variant: max_positions_20_50k (10.24%)
- best_any_including_invalid: capital_200k_maxpos20 (18.94%)

## 结论

- 当前默认 50k lot-aware 为基线，executable/raw=3.66%，executable=23。
- 不含取消整手的有效实验里，最高的是 capital_200k_maxpos20，executable/raw=18.94%，比基线提高 15.28%。
- 仍限定 50k 和 100 股整手时，最高的是 max_positions_20_50k，executable/raw=10.24%，recommendation_class=more_positions_same_capital。
- 理论上限实验没有超过有效实验。

## 50k feasibility conclusion

- 当前 50k lot-aware 默认 profile 不应升级为 PASS；默认 executable/raw 仍显著低于 25% guard。
- 低风险参数修改不能把 executable/raw 推近 25%；降低最小成交额、提高单票上限、放宽日内限制在本轮都没有形成有效改善。
- max_positions_20_50k 虽然提高执行率，但通过显著提高暴露和回撤换来，不应作为低风险修复。
- capital_200k_maxpos20 是研究上限，不是默认 release 方案，也不能替代 50k lot-aware 默认口径。
- 取消整手约束是无效的 A 股理论上限测试，不能作为实盘方案。
- 下一步如果坚持 50k，应优先做 observation/paper trading，而不是继续参数放宽。
- 如果要实盘化，应考虑提高资金规模、降低目标股票数、重新设计专门适配 50k 的候选池，或接受这是研究/观察系统而不是 50k 可执行交易系统。

## 排名表

| rank | variant | category | class | capital | min_trade | lot | max_single | max_pos | raw | feasible | executable | exec/raw | delta | max_dd | exposure | status |
|---:|---|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| 1 | capital_200k_maxpos20 | capital_and_capacity | research_only_reference_scale | 200000.0 | 1500.0 | 100 | 0.12 | 20 | 264 | 79 | 50 | 18.94% | 15.28% | -8.96% | 68.31% | WARN |
| 2 | max_positions_20_50k | portfolio_capacity | more_positions_same_capital | 50000.0 | 1500.0 | 100 | 0.12 | 20 | 371 | 43 | 38 | 10.24% | 6.59% | -12.06% | 94.76% | WARN |
| 3 | max_positions_12_50k | portfolio_capacity | more_positions_same_capital | 50000.0 | 1500.0 | 100 | 0.12 | 12 | 481 | 168 | 31 | 6.44% | 2.79% | -12.06% | 70.60% | WARN |
| 4 | round_lot_1_upper_bound | invalid_upper_bound | invalid_for_a_share | 50000.0 | 1500.0 | 1 | 0.12 | 8 | 541 | 541 | 34 | 6.28% | 2.63% | -6.83% | 40.55% | WARN |
| 5 | capital_200k_lot_aware | capital_scale | research_only | 200000.0 | 1500.0 | 100 | 0.12 | 8 | 538 | 538 | 31 | 5.76% | 2.11% | -6.15% | 36.53% | WARN |
| 6 | capital_100k_lot_aware | capital_scale | research_only | 100000.0 | 1500.0 | 100 | 0.12 | 8 | 555 | 531 | 28 | 5.05% | 1.39% | -6.06% | 39.96% | WARN |
| 7 | daily_limits_3_5 | daily_limits | research_only | 50000.0 | 1500.0 | 100 | 0.12 | 8 | 628 | 425 | 23 | 3.66% | 0.01% | -8.87% | 54.99% | WARN |
| 8 | baseline_50k_lot_aware | baseline | current_default_reference | 50000.0 | 1500.0 | 100 | 0.12 | 8 | 629 | 426 | 23 | 3.66% | 0.00% | -8.88% | 55.01% | WARN |
| 9 | max_single_20pct | single_name_capacity | high_concentration | 50000.0 | 1500.0 | 100 | 0.2 | 8 | 629 | 426 | 23 | 3.66% | 0.00% | -8.88% | 55.01% | WARN |
| 10 | min_trade_1000_50k | min_trade_value | research_only | 50000.0 | 1000.0 | 100 | 0.12 | 8 | 674 | 482 | 22 | 3.26% | -0.39% | -6.62% | 55.52% | WARN |
| 11 | min_trade_500_50k | min_trade_value | research_only | 50000.0 | 500.0 | 100 | 0.12 | 8 | 674 | 482 | 22 | 3.26% | -0.39% | -6.66% | 55.46% | WARN |
| 12 | tranche_5_10_15_max15 | position_sizing | higher_concentration | 50000.0 | 1500.0 | 100 | 0.15 | 6 | 849 | 811 | 24 | 2.83% | -0.83% | -8.71% | 43.91% | WARN |
| 13 | no_lot_aware_50k | execution_mechanism | research_only | 50000.0 | 1500.0 | 100 | 0.12 | 8 | 1145 | 12 | 12 | 1.05% | -2.61% | -4.28% | 26.30% | WARN |

## 方法判断

- 提高本金本身会改善一手可买性；如果同时提高最大持仓容量，才会显著缓解 MAX_POSITIONS_LIMIT 对 raw 分母的压制。
- 本轮结果显示，50k 内部单独降低最小成交额、提高单票上限或放宽每日新开/加仓次数，改善都很有限；主瓶颈不是 1500 元最小成交额。
- 目标分层放大可能增加可行信号，但也会抬高 raw 分母和集中度，不等于 executable/raw 变好。
- 取消整手约束只能说明理论损耗上限，不是可落地方案。
- 本报告只评估账户执行约束，不新增策略想法，不改变 action_enum 的规则驱动来源。
