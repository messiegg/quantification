# combined_v2 vs combined_v2_1_risk_guard

- 主策略仍是 combined_v2 PIT next_bar；combined_v2_1_risk_guard 只是非主策略候选，不替换主口径。
- v2_1 沿用 combined_v2 universe，不新增 universe_rules 文件。

## 对比结果

- v2: 年化 2.48%，累计 7.33%，最大回撤 -8.88%，成交 41。
- v2_1: 年化 1.99%，累计 5.83%，最大回撤 -4.27%，成交 21。
- 是否降低 risk_off / neutral 损失: 是。
- 是否降低最大回撤: 是。
- 是否牺牲太多收益: 否；年化差 0.50%。
- 是否减少过多交易: 是。

## 最低交易密度

- total_trades >= 25: 21
- buy_trades >= 12: 12
- avg_daily_exposure >= 15%: 14.82%
- exposure_active_days_ratio >= 30%: 99.72%
- avg_positions >= 2: 3.69
- density_status: FAIL

## 结论

- 候选标签: research_only。
- 如果 v2_1 不明显优于 v2，不推荐替换 v2；若只是降低回撤但明显牺牲收益，只能作为 conservative candidate 继续观察。
