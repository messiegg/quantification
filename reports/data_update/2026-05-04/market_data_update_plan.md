# market data safe update plan

- as_of_date: 2026-05-04
- requested_as_of_is_trading_day: false
- target_trading_date: 2026-04-30
- calendar_source: project_trade_calendar
- current_data_max_date: 2026-04-03
- current_feature_max_date: 2026-04-03
- current_benchmark_max_date: 2026-04-30
- dry_run_writes_data: false
- local_tdx_data_source_available: false
- network_providers_configured: true
- provider_readiness_status: WARN

## 需要补齐的交易日

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

## 计划更新的数据类型

- daily行情
- benchmark
- features
- valuation quantiles
- industry valuation
- universe history check
- provider health
- data quality

## 说明

- dry-run 只生成计划，不写行情、特征、账本或订单文件。
- 非 dry-run 只编排现有数据脚本，不新增抓取器，不生成 observation report。
- 大体量 parquet、缓存、真实 paper ledger 不应提交到 GitHub。
