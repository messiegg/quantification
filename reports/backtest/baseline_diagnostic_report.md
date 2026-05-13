# baseline 回测诊断报告

## 元数据

- git_commit: fcbad4f7fd70542596dcb7537dba4e7ea41a84c9
- config_hash: 6817ac43cf178fea81d0976750c1269eba0c1b2f4a2e0e6c4f4e7c1f16eaf1d5
- data_hash: ea7c14af5f4b454e5e18df55b7c8851fcaa28170542dccc4a7d598f0b7426c7e
- manual_review_required: true
- auto_trading_approved: false

## 三年绩效摘要

- 年化收益: -0.08%
- 累计收益: -0.22%
- 最大回撤: -0.30%
- 夏普: -0.44
- 胜率: 0.00%
- 成交笔数: 2，买入 1，卖出 1

## 仓位与持仓

- 平均日仓位: 0.04%
- 最大日仓位: 3.00%
- 平均持仓数量: 0.01
- 最大持仓数量: 1
- 平均持有天数: 9.00
- 持有天数中位数: 9.00

## 为什么交易稀疏

- 原始买入信号合计: 16
- 账户初筛可行买入信号合计: 1
- 可执行买入信号合计: 1
- 实际买入成交合计: 1
- 市场状态阻断: 2076
- 资金阻断: 0
- 最小交易额阻断: 14
- 整手阻断: 1
- 总仓位/每日数量限制阻断: 0
- 最大持仓数阻断: 0
- 每日新开仓限制阻断: 0
- 每日加仓限制阻断: 0

## 诊断结论

- 原始买入信号有 16 个，主要流失发生在执行层：可执行买入 1 个。
- 历史 effective universe 平均 11.68 只，最小 3 只，最大 17 只。
- 执行约束中，最小交易额阻断 14 次，整手阻断 1 次。
- 市场状态阻断 2076 次；这些是日常决策层阻断，并不等同于已形成 raw buy 后被拦截。

## 每月 effective universe size

- 2023-04-03: 14
- 2023-05-04: 14
- 2023-06-01: 6
- 2023-07-03: 7
- 2023-08-01: 7
- 2023-09-01: 14
- 2023-10-09: 14
- 2023-11-01: 16
- 2023-12-01: 16
- 2024-01-02: 16
- 2024-02-01: 17
- 2024-03-01: 17
- 2024-04-01: 17
- 2024-05-06: 3
- 2024-06-03: 4
- 2024-07-01: 4
- 2024-08-01: 5
- 2024-09-02: 13
- 2024-10-08: 15
- 2024-11-01: 14
- 2024-12-02: 16
- 2025-01-02: 16
- 2025-02-05: 16
- 2025-03-03: 15
- 2025-04-01: 16
- 2025-05-06: 5
- 2025-06-03: 6
- 2025-07-01: 7
- 2025-08-01: 8
- 2025-09-01: 10
- 2025-10-09: 12
- 2025-11-03: 13
- 2025-12-01: 12
- 2026-01-05: 10
- 2026-02-02: 11
- 2026-03-02: 12
- 2026-04-01: 14

## 每月买入漏斗

- 2023-04: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2023-05: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2023-06: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2023-07: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2023-08: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2023-09: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2023-10: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2023-11: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2023-12: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-01: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-02: raw_buy=7, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-03: raw_buy=6, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-04: raw_buy=1, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-05: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-06: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-07: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-08: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-09: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-10: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-11: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2024-12: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-01: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-02: raw_buy=1, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-03: raw_buy=1, account_feasible=1, executable_buy=1, executed_buy=1
- 2025-04: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-05: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-06: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-07: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-08: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-09: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-10: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-11: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2025-12: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2026-01: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2026-02: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2026-03: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0
- 2026-04: raw_buy=0, account_feasible=0, executable_buy=0, executed_buy=0

## 拦截原因排序

- MIN_TRADE_AMOUNT: 14
- LOT_SIZE_ZERO: 1

## 重点个股逐笔解释

- 2025-03-26 000012.sz BUY_1 300 股，价格 5.0125，持有天数 0，原因：满足第一笔买点。
- 2025-04-09 000012.sz SELL_ALL 300 股，价格 4.6477，持有天数 9，原因：周期趋势转弱，触发清仓。
