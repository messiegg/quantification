# combined_v2 vs combined_v2_1_risk_guard 观察对照

- combined_v2 仍是 primary_profile。
- combined_v2_1_risk_guard 只作为 conservative_profile 输出，不替换主候选。
- 非交易日仅用于 next trading day manual review。
- auto_order_allowed: false。
- broker_connected: false。
- combined_v2 当日动作数: 0
- combined_v2_1_risk_guard 当日动作数: 0
- v2_1 是否更保守: 当日无足够动作差异，继续观察。
