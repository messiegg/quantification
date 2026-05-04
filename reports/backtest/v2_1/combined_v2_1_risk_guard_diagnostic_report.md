# combined_v2_1_risk_guard 回测诊断报告

## 三年绩效摘要

- 年化收益: 5.60%
- 累计收益: 17.01%
- 最大回撤: -8.88%
- 夏普: 0.68
- 胜率: 48.15%
- 成交笔数: 64，买入 37，卖出 27

## 仓位与持仓

- 平均日仓位: 43.03%
- 最大日仓位: 67.70%
- 平均持仓数量: 11.16
- 最大持仓数量: 18
- 平均持有天数: 192.59
- 持有天数中位数: 155.00

## 为什么交易稀疏

- 原始买入信号合计: 149
- 可执行买入信号合计: 37
- 实际买入成交合计: 37
- 市场状态阻断: 274
- 资金阻断: 0
- 最小交易额阻断: 82
- 整手阻断: 3
- 总仓位/每日数量限制阻断: 28

## 诊断结论

- 原始买入信号有 149 个，主要流失发生在执行层：可执行买入 37 个。
- 历史 effective universe 平均 24.16 只，最小 12 只，最大 33 只。
- 执行约束中，最小交易额阻断 82 次，整手阻断 3 次。
- 仓位或每日数量限制阻断 28 次，说明信号密度已高于可执行容量。
- 市场状态阻断 274 次；这些是日常决策层阻断，并不等同于已形成 raw buy 后被拦截。

## 每月 effective universe size

- 2023-04-03: 28
- 2023-05-04: 23
- 2023-06-01: 13
- 2023-07-03: 13
- 2023-08-01: 14
- 2023-09-01: 29
- 2023-10-09: 30
- 2023-11-01: 31
- 2023-12-01: 31
- 2024-01-02: 31
- 2024-02-01: 29
- 2024-03-01: 30
- 2024-04-01: 29
- 2024-05-06: 12
- 2024-06-03: 12
- 2024-07-01: 12
- 2024-08-01: 14
- 2024-09-02: 29
- 2024-10-08: 25
- 2024-11-01: 28
- 2024-12-02: 27
- 2025-01-02: 29
- 2025-02-05: 31
- 2025-03-03: 31
- 2025-04-01: 31
- 2025-05-06: 15
- 2025-06-03: 16
- 2025-07-01: 14
- 2025-08-01: 14
- 2025-09-01: 23
- 2025-10-09: 25
- 2025-11-03: 30
- 2025-12-01: 33
- 2026-01-05: 31
- 2026-02-02: 25
- 2026-03-02: 25
- 2026-04-01: 31

## 每月买入漏斗

- 2023-04: raw_buy=7, executable_buy=7, executed_buy=7
- 2023-05: raw_buy=23, executable_buy=6, executed_buy=6
- 2023-06: raw_buy=0, executable_buy=0, executed_buy=0
- 2023-07: raw_buy=0, executable_buy=0, executed_buy=0
- 2023-08: raw_buy=1, executable_buy=1, executed_buy=1
- 2023-09: raw_buy=9, executable_buy=0, executed_buy=0
- 2023-10: raw_buy=18, executable_buy=0, executed_buy=0
- 2023-11: raw_buy=19, executable_buy=0, executed_buy=0
- 2023-12: raw_buy=3, executable_buy=0, executed_buy=0
- 2024-01: raw_buy=2, executable_buy=0, executed_buy=0
- 2024-02: raw_buy=8, executable_buy=1, executed_buy=1
- 2024-03: raw_buy=5, executable_buy=0, executed_buy=0
- 2024-04: raw_buy=3, executable_buy=1, executed_buy=1
- 2024-05: raw_buy=1, executable_buy=1, executed_buy=1
- 2024-06: raw_buy=1, executable_buy=1, executed_buy=1
- 2024-07: raw_buy=10, executable_buy=1, executed_buy=1
- 2024-08: raw_buy=0, executable_buy=0, executed_buy=0
- 2024-09: raw_buy=8, executable_buy=5, executed_buy=5
- 2024-10: raw_buy=1, executable_buy=1, executed_buy=1
- 2024-11: raw_buy=0, executable_buy=0, executed_buy=0
- 2024-12: raw_buy=0, executable_buy=0, executed_buy=0
- 2025-01: raw_buy=2, executable_buy=2, executed_buy=2
- 2025-02: raw_buy=1, executable_buy=1, executed_buy=1
- 2025-03: raw_buy=2, executable_buy=2, executed_buy=2
- 2025-04: raw_buy=20, executable_buy=2, executed_buy=2
- 2025-05: raw_buy=2, executable_buy=2, executed_buy=2
- 2025-06: raw_buy=0, executable_buy=0, executed_buy=0
- 2025-07: raw_buy=0, executable_buy=0, executed_buy=0
- 2025-08: raw_buy=0, executable_buy=0, executed_buy=0
- 2025-09: raw_buy=0, executable_buy=0, executed_buy=0
- 2025-10: raw_buy=0, executable_buy=0, executed_buy=0
- 2025-11: raw_buy=1, executable_buy=1, executed_buy=1
- 2025-12: raw_buy=2, executable_buy=2, executed_buy=2
- 2026-01: raw_buy=0, executable_buy=0, executed_buy=0
- 2026-02: raw_buy=0, executable_buy=0, executed_buy=0
- 2026-03: raw_buy=0, executable_buy=0, executed_buy=0
- 2026-04: raw_buy=0, executable_buy=0, executed_buy=0

## 拦截原因排序

- MIN_TRADE_AMOUNT: 82
- TOTAL_EXPOSURE_LIMIT: 28
- LOT_SIZE_ZERO: 3

## 重点个股逐笔解释

- 三只重点股票在本次输出中无成交明细。
