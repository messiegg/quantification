# combined_v2 vs combined_v2_1_risk_guard

- 主策略仍是 combined_v2 PIT next_bar；combined_v2_1_risk_guard 只是非主策略候选，不替换主口径。
- v2_1 沿用 combined_v2 universe，不新增 universe_rules 文件。

## 对比结果

- v2: 年化 7.14%，累计 21.96%，最大回撤 -9.36%，成交 76。
- v2_1: 年化 5.60%，累计 17.01%，最大回撤 -8.88%，成交 64。
- 是否降低 risk_off / neutral 损失: 是。
- 是否降低最大回撤: 是。
- 是否牺牲太多收益: 否；年化差 1.53%。
- 是否减少过多交易: 否。

## 最低交易密度

- total_trades >= 25: 64
- buy_trades >= 12: 37
- avg_daily_exposure >= 15%: 43.03%
- exposure_active_days_ratio >= 30%: 100.00%
- avg_positions >= 2: 11.16
- density_status: PASS

## 结论

- 候选标签: candidate_for_manual_review。
- 如果 v2_1 不明显优于 v2，不推荐替换 v2；若只是降低回撤但明显牺牲收益，只能作为 conservative candidate 继续观察。
