# min_trade_1000_50k 回测诊断报告

## 元数据

- git_commit: fcbad4f7fd70542596dcb7537dba4e7ea41a84c9
- config_hash: 6817ac43cf178fea81d0976750c1269eba0c1b2f4a2e0e6c4f4e7c1f16eaf1d5
- data_hash: 0434a444d798704567c3af8b0f6cfa56a73af8a0d8353cd3b2d4049672b2773a
- manual_review_required: true
- auto_trading_approved: false

## 三年绩效摘要

- 年化收益: 4.43%
- 累计收益: 13.30%
- 最大回撤: -6.62%
- 夏普: 0.62
- 胜率: 52.94%
- 成交笔数: 39，买入 22，卖出 17

## 仓位与持仓

- 平均日仓位: 42.62%
- 最大日仓位: 55.52%
- 平均持仓数量: 7.28
- 最大持仓数量: 8
- 平均持有天数: 240.29
- 持有天数中位数: 174.00

## 为什么交易稀疏

- 原始买入信号合计: 674
- 账户初筛可行买入信号合计: 482
- 可执行买入信号合计: 22
- 实际买入成交合计: 22
- 市场状态阻断: 0
- 资金阻断: 0
- 最小交易额阻断: 14
- 整手阻断: 0
- 总仓位/每日数量限制阻断: 0
- 最大持仓数阻断: 459
- 每日新开仓限制阻断: 1
- 每日加仓限制阻断: 0

## 诊断结论

- 原始买入信号有 674 个，主要流失发生在执行层：可执行买入 22 个。
- 历史 effective universe 平均 24.16 只，最小 12 只，最大 33 只。
- 执行约束中，最小交易额阻断 14 次，整手阻断 0 次。

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

- 2023-04: raw_buy=8, account_feasible=8, executable_buy=7, executed_buy=7
- 2023-05: raw_buy=42, account_feasible=42, executable_buy=3, executed_buy=3
- 2023-06: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2023-07: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2023-08: raw_buy=2, account_feasible=2, executable_buy=0, executed_buy=0
- 2023-09: raw_buy=43, account_feasible=0, executable_buy=0, executed_buy=0
- 2023-10: raw_buy=68, account_feasible=0, executable_buy=0, executed_buy=0
- 2023-11: raw_buy=22, account_feasible=1, executable_buy=1, executed_buy=1
- 2023-12: raw_buy=2, account_feasible=2, executable_buy=2, executed_buy=2
- 2024-01: raw_buy=23, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-02: raw_buy=5, account_feasible=1, executable_buy=1, executed_buy=1
- 2024-03: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-04: raw_buy=1, account_feasible=1, executable_buy=1, executed_buy=1
- 2024-05: raw_buy=9, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-06: raw_buy=14, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-07: raw_buy=11, account_feasible=4, executable_buy=2, executed_buy=2
- 2024-08: raw_buy=35, account_feasible=35, executable_buy=0, executed_buy=0
- 2024-09: raw_buy=107, account_feasible=104, executable_buy=0, executed_buy=0
- 2024-10: raw_buy=13, account_feasible=13, executable_buy=0, executed_buy=0
- 2024-11: raw_buy=26, account_feasible=26, executable_buy=0, executed_buy=0
- 2024-12: raw_buy=17, account_feasible=17, executable_buy=0, executed_buy=0
- 2025-01: raw_buy=22, account_feasible=22, executable_buy=0, executed_buy=0
- 2025-02: raw_buy=35, account_feasible=35, executable_buy=0, executed_buy=0
- 2025-03: raw_buy=30, account_feasible=30, executable_buy=1, executed_buy=1
- 2025-04: raw_buy=73, account_feasible=73, executable_buy=0, executed_buy=0
- 2025-05: raw_buy=21, account_feasible=21, executable_buy=1, executed_buy=1
- 2025-06: raw_buy=4, account_feasible=4, executable_buy=0, executed_buy=0
- 2025-07: raw_buy=1, account_feasible=1, executable_buy=0, executed_buy=0
- 2025-08: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-09: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-10: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-11: raw_buy=1, account_feasible=1, executable_buy=1, executed_buy=1
- 2025-12: raw_buy=4, account_feasible=4, executable_buy=1, executed_buy=1
- 2026-01: raw_buy=20, account_feasible=20, executable_buy=0, executed_buy=0
- 2026-02: raw_buy=14, account_feasible=14, executable_buy=0, executed_buy=0
- 2026-03: raw_buy=1, account_feasible=1, executable_buy=1, executed_buy=1
- 2026-04: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0

## 拦截原因排序

- MAX_POSITIONS_LIMIT: 459
- CASH_INSUFFICIENT_FOR_ONE_LOT: 151
- PRICE_TOO_HIGH_FOR_ACCOUNT_LOT: 30
- MIN_TRADE_AMOUNT: 14
- PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY: 11
- DAILY_NEW_POSITION_LIMIT: 1

## 重点个股逐笔解释

- 三只重点股票在本次输出中无成交明细。
