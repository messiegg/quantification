# capital_200k_maxpos20 回测诊断报告

## 元数据

- git_commit: fcbad4f7fd70542596dcb7537dba4e7ea41a84c9
- config_hash: 6817ac43cf178fea81d0976750c1269eba0c1b2f4a2e0e6c4f4e7c1f16eaf1d5
- data_hash: 0434a444d798704567c3af8b0f6cfa56a73af8a0d8353cd3b2d4049672b2773a
- manual_review_required: true
- auto_trading_approved: false

## 三年绩效摘要

- 年化收益: 5.10%
- 累计收益: 15.42%
- 最大回撤: -8.96%
- 夏普: 0.59
- 胜率: 50.00%
- 成交笔数: 79，买入 47，卖出 32

## 仓位与持仓

- 平均日仓位: 46.76%
- 最大日仓位: 68.31%
- 平均持仓数量: 13.36
- 最大持仓数量: 20
- 平均持有天数: 196.66
- 持有天数中位数: 156.50

## 为什么交易稀疏

- 原始买入信号合计: 264
- 账户初筛可行买入信号合计: 79
- 可执行买入信号合计: 50
- 实际买入成交合计: 47
- 市场状态阻断: 0
- 资金阻断: 12
- 最小交易额阻断: 0
- 整手阻断: 0
- 总仓位/每日数量限制阻断: 0
- 最大持仓数阻断: 29
- 每日新开仓限制阻断: 0
- 每日加仓限制阻断: 0

## 诊断结论

- 原始买入信号有 264 个，主要流失发生在执行层：可执行买入 50 个。
- 历史 effective universe 平均 24.16 只，最小 12 只，最大 33 只。

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

- 2023-04: raw_buy=7, account_feasible=7, executable_buy=7, executed_buy=7
- 2023-05: raw_buy=7, account_feasible=7, executable_buy=7, executed_buy=7
- 2023-06: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2023-07: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2023-08: raw_buy=1, account_feasible=1, executable_buy=1, executed_buy=1
- 2023-09: raw_buy=26, account_feasible=0, executable_buy=0, executed_buy=0
- 2023-10: raw_buy=44, account_feasible=2, executable_buy=2, executed_buy=1
- 2023-11: raw_buy=24, account_feasible=3, executable_buy=3, executed_buy=2
- 2023-12: raw_buy=1, account_feasible=1, executable_buy=1, executed_buy=1
- 2024-01: raw_buy=2, account_feasible=2, executable_buy=2, executed_buy=2
- 2024-02: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-03: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-04: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-05: raw_buy=1, account_feasible=1, executable_buy=1, executed_buy=1
- 2024-06: raw_buy=1, account_feasible=1, executable_buy=1, executed_buy=1
- 2024-07: raw_buy=5, account_feasible=5, executable_buy=5, executed_buy=5
- 2024-08: raw_buy=8, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-09: raw_buy=96, account_feasible=8, executable_buy=8, executed_buy=7
- 2024-10: raw_buy=1, account_feasible=1, executable_buy=1, executed_buy=1
- 2024-11: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-12: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-01: raw_buy=2, account_feasible=2, executable_buy=2, executed_buy=2
- 2025-02: raw_buy=1, account_feasible=1, executable_buy=1, executed_buy=1
- 2025-03: raw_buy=2, account_feasible=2, executable_buy=2, executed_buy=2
- 2025-04: raw_buy=26, account_feasible=26, executable_buy=2, executed_buy=2
- 2025-05: raw_buy=6, account_feasible=6, executable_buy=1, executed_buy=1
- 2025-06: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-07: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-08: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-09: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-10: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-11: raw_buy=1, account_feasible=1, executable_buy=1, executed_buy=1
- 2025-12: raw_buy=2, account_feasible=2, executable_buy=2, executed_buy=2
- 2026-01: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2026-02: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2026-03: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2026-04: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0

## 拦截原因排序

- CASH_INSUFFICIENT_FOR_ONE_LOT: 173
- MAX_POSITIONS_LIMIT: 29
- CASH_INSUFFICIENT: 12
- LOT_SIZE_ZERO: 2
- TOTAL_EXPOSURE_LIMIT_AT_FILL: 1

## 重点个股逐笔解释

- 三只重点股票在本次输出中无成交明细。
