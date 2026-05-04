# 数据新鲜度检查

- requested_as_of_date: 2026-05-04
- requested_as_of_is_trading_day: false
- target_trading_date: 2026-04-30
- calendar_source: project_trade_calendar+a_share_weekday_holiday_overrides
- data_max_date: 2026-04-03
- feature_max_date: 2026-04-03
- benchmark_max_date: 2026-04-03
- universe_max_effective_date: 2026-05-01
- provider_health_date: 2026-04-03
- data_quality_date: 2026-04-03
- stale_calendar_days: 31
- stale_trading_days: 18
- require_data_max_date_ge_target_trading_date: true
- is_data_current_for_target_trading_date: false
- blocking_reason: DATA_MAX_DATE_BEFORE_TARGET_TRADING_DATE|FEATURE_MAX_DATE_BEFORE_TARGET_TRADING_DATE|BENCHMARK_MAX_DATE_BEFORE_TARGET_TRADING_DATE|STALE_CALENDAR_DAYS_EXCEED_LIMIT|STALE_TRADING_DAYS_EXCEED_LIMIT
- allowed_actions: historical_review_only

STALE_DATA_BLOCKED：只能历史复盘，不允许生成实盘观察日报或手工订单清单。

## 缺口交易日

- 2026-04-07
- 2026-04-08
- 2026-04-09
- 2026-04-10
- 2026-04-13
- 2026-04-14
- 2026-04-15
- 2026-04-16
- 2026-04-17
- 2026-04-20
- 2026-04-21
- 2026-04-22
- 2026-04-23
- 2026-04-24
- 2026-04-27
- 2026-04-28
- 2026-04-29
- 2026-04-30
