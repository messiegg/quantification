# 数据新鲜度检查

- requested_as_of_date: 2026-05-04
- requested_as_of_is_trading_day: false
- target_trading_date: 2026-04-30
- calendar_source: project_trade_calendar
- data_max_date: 2026-04-30
- feature_max_date: 2026-04-30
- benchmark_max_date: 2026-04-30
- universe_max_effective_date: 2026-05-01
- provider_health_date: 2026-04-30
- data_quality_date: 2026-04-30
- stale_calendar_days: 4
- stale_trading_days: 0
- max_stale_calendar_days: 3
- max_stale_trading_days: 0
- calendar_staleness_policy: WARN_ONLY_WHEN_MARKET_CLOSED_AND_TARGET_CURRENT
- calendar_staleness_blocking: false
- calendar_staleness_warning: true
- require_data_max_date_ge_target_trading_date: true
- is_data_current_for_target_trading_date: true
- blocking_reason: NONE
- allowed_actions: observation_report_allowed

数据新鲜度允许生成观察报告，但仍禁止自动下单。
MARKET_CLOSED_AS_OF_DATE：仅允许为下一交易日进行人工复盘，不得写成当日实盘执行。

## WARN

- STALE_CALENDAR_DAYS_EXCEED_LIMIT_NON_TRADING_DAY_WARN
