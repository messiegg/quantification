# 观察期运行被阻断

- as_of_date: 2026-05-04
- blocking_reason: STALE_DATA_BLOCKED
- action_allowed: false
- 只允许历史复盘，不允许生成当日实盘观察日报或手工订单清单。
- 禁止自动下单，禁止连接券商，禁止把 LLM 输出用于 action_enum。

## 数据状态

- data_max_date: 2026-04-03
- feature_max_date: 2026-04-03
- benchmark_max_date: 2026-04-03
- stale_calendar_days: 31
- freshness_blocking_reason: DATA_MAX_DATE_BEFORE_AS_OF_DATE|STALE_CALENDAR_DAYS_EXCEED_LIMIT
