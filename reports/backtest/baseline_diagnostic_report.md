# baseline 回测诊断报告

## 三年绩效摘要

- 年化收益: 0.10%
- 累计收益: 0.30%
- 最大回撤: -1.66%
- 夏普: 0.10
- 胜率: 0.00%
- 成交笔数: 7，买入 4，卖出 3

## 仓位与持仓

- 平均日仓位: 2.66%
- 最大日仓位: 6.85%
- 平均持仓数量: 0.75
- 最大持仓数量: 2
- 平均持有天数: 7.67
- 持有天数中位数: 9.00

## 为什么交易稀疏

- 原始买入信号合计: 5
- 可执行买入信号合计: 4
- 实际买入成交合计: 4
- 市场状态阻断: 2076
- 资金阻断: 0
- 最小交易额阻断: 1
- 整手阻断: 0
- 总仓位/每日数量限制阻断: 0

## 诊断结论

- 交易稀疏的首要原因是原始买入信号本身很少：三年只有 5 个 raw buy，实际成交 4 个。
- 历史 effective universe 平均 11.68 只，最小 3 只，最大 17 只。
- 执行约束中，最小交易额阻断 1 次，整手阻断 0 次。
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

- 2023-04: raw_buy=0, executable_buy=0, executed_buy=0
- 2023-05: raw_buy=0, executable_buy=0, executed_buy=0
- 2023-06: raw_buy=0, executable_buy=0, executed_buy=0
- 2023-07: raw_buy=0, executable_buy=0, executed_buy=0
- 2023-08: raw_buy=0, executable_buy=0, executed_buy=0
- 2023-09: raw_buy=0, executable_buy=0, executed_buy=0
- 2023-10: raw_buy=0, executable_buy=0, executed_buy=0
- 2023-11: raw_buy=0, executable_buy=0, executed_buy=0
- 2023-12: raw_buy=0, executable_buy=0, executed_buy=0
- 2024-01: raw_buy=0, executable_buy=0, executed_buy=0
- 2024-02: raw_buy=1, executable_buy=1, executed_buy=1
- 2024-03: raw_buy=1, executable_buy=1, executed_buy=1
- 2024-04: raw_buy=1, executable_buy=0, executed_buy=0
- 2024-05: raw_buy=0, executable_buy=0, executed_buy=0
- 2024-06: raw_buy=0, executable_buy=0, executed_buy=0
- 2024-07: raw_buy=0, executable_buy=0, executed_buy=0
- 2024-08: raw_buy=0, executable_buy=0, executed_buy=0
- 2024-09: raw_buy=0, executable_buy=0, executed_buy=0
- 2024-10: raw_buy=0, executable_buy=0, executed_buy=0
- 2024-11: raw_buy=0, executable_buy=0, executed_buy=0
- 2024-12: raw_buy=0, executable_buy=0, executed_buy=0
- 2025-01: raw_buy=0, executable_buy=0, executed_buy=0
- 2025-02: raw_buy=1, executable_buy=1, executed_buy=1
- 2025-03: raw_buy=1, executable_buy=1, executed_buy=1
- 2025-04: raw_buy=0, executable_buy=0, executed_buy=0
- 2025-05: raw_buy=0, executable_buy=0, executed_buy=0
- 2025-06: raw_buy=0, executable_buy=0, executed_buy=0
- 2025-07: raw_buy=0, executable_buy=0, executed_buy=0
- 2025-08: raw_buy=0, executable_buy=0, executed_buy=0
- 2025-09: raw_buy=0, executable_buy=0, executed_buy=0
- 2025-10: raw_buy=0, executable_buy=0, executed_buy=0
- 2025-11: raw_buy=0, executable_buy=0, executed_buy=0
- 2025-12: raw_buy=0, executable_buy=0, executed_buy=0
- 2026-01: raw_buy=0, executable_buy=0, executed_buy=0
- 2026-02: raw_buy=0, executable_buy=0, executed_buy=0
- 2026-03: raw_buy=0, executable_buy=0, executed_buy=0
- 2026-04: raw_buy=0, executable_buy=0, executed_buy=0

## 拦截原因排序

- MIN_TRADE_AMOUNT: 1

## 重点个股逐笔解释

- 2024-02-02 002705.sz BUY_1 500 股，价格 11.2656，持有天数 0，原因：满足第一笔买点。
- 2024-03-13 002271.sz BUY_1 400 股，价格 14.2471，持有天数 0，原因：满足第一笔买点。
- 2024-03-29 002271.sz SELL_ALL 400 股，价格 12.9635，持有天数 12，原因：周期趋势转弱，触发清仓。
- 2025-02-28 000012.sz BUY_1 1200 股，价格 4.9024，持有天数 0，原因：满足第一笔买点。
- 2025-03-04 000012.sz SELL_ALL 1200 股，价格 4.8776，持有天数 2，原因：周期趋势转弱，触发清仓。
- 2025-03-26 000012.sz BUY_1 1200 股，价格 5.0125，持有天数 0，原因：满足第一笔买点。
- 2025-04-09 000012.sz SELL_ALL 1200 股，价格 4.6477，持有天数 9，原因：周期趋势转弱，触发清仓。
