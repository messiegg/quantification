# 数据新鲜度与运行手册

## 新鲜度守门

```bash
./.venv/bin/python scripts/check_data_freshness.py --as-of-date 2026-05-04 --write-report
```

输出：

- `reports/observation/<as_of_date>/data_freshness_report.md`
- `reports/observation/<as_of_date>/data_freshness_report.json`

核心字段：

- `requested_as_of_date`
- `requested_as_of_is_trading_day`
- `target_trading_date`
- `calendar_source`
- `data_max_date`
- `feature_max_date`
- `benchmark_max_date`
- `universe_max_effective_date`
- `provider_health_date`
- `data_quality_date`
- `stale_calendar_days`
- `stale_trading_days`
- `require_data_max_date_ge_target_trading_date`
- `is_data_current_for_target_trading_date`
- `blocking_reason`
- `allowed_actions`

## 阻断规则

freshness gate 先把 `requested_as_of_date` 映射到 `target_trading_date`。如果请求日不是 A 股交易日，目标日期为小于等于请求日的最近交易日；本地交易日历优先使用 `data/curated/trade_calendar.parquet`，必要时用 benchmark / features 日期推断，并记录 `calendar_source`。

如果无法解析 `target_trading_date`，则输出：

- `blocking_reason: TARGET_TRADING_DATE_UNRESOLVED`
- `allowed_actions: historical_review_only`

如果 `data_max_date < target_trading_date`，且观察配置要求数据覆盖目标交易日，则输出：

- `is_data_current: false`
- `blocking_reason: DATA_MAX_DATE_BEFORE_TARGET_TRADING_DATE`
- `allowed_actions: historical_review_only`

如果 `feature_max_date` 或 `benchmark_max_date` 早于目标交易日，也会阻断。`stale_trading_days > max_stale_trading_days_for_daily_report` 时会输出 `STALE_TRADING_DAYS_EXCEED_LIMIT`。缺少 provider health 或 data quality 是 `WARN`，报告必须显式说明。

非交易日请求在数据覆盖到目标交易日且质量检查通过时，可以生成节假日期间观察报告；报告必须标记 `MARKET_CLOSED_AS_OF_DATE`，所有动作只能作为下一交易日人工复盘，不能写成当日实盘执行。

## 当前 2026-05-04 状态

2026-05-04 是劳动节休市期间，`target_trading_date` 应解析为 `2026-04-30`。当前 RC 历史数据截止 `2026-04-03`。在数据没有真实更新到 `2026-04-30` 并通过 freshness / quality gate 前，不能生成 `2026-05-04` 的观察日报，也不能生成手工执行清单。

正确行为是：

- 生成 `reports/observation/2026-05-04/data_freshness_report.md`
- 生成 `reports/observation/2026-05-04/observation_blocked.md`
- 生成 `reports/observation/2026-05-04/observation_run_manifest.json`
- 不生成 `combined_v2_manual_order_list.csv`

## 全流程

```bash
./.venv/bin/python scripts/check_report_freshness.py
./.venv/bin/python scripts/verify_combined_v2_rc.py
./.venv/bin/python scripts/check_release_sync_consistency.py
./.venv/bin/python scripts/check_data_freshness.py --as-of-date 2026-05-04 --write-report
./.venv/bin/python scripts/update_market_data_safe.py --as-of-date 2026-05-04 --dry-run --write-report
./.venv/bin/python scripts/run_observation_pipeline.py --as-of-date 2026-05-04 --profile combined_v2 --mode paper --compare-conservative true
./.venv/bin/python scripts/update_paper_observation.py --as-of-date 2026-05-04
```

即使 freshness gate 通过，输出仍是手工观察和手工执行参考，不是自动交易。

## 安全数据更新入口

`scripts/update_market_data_safe.py` 只做编排和报告，不新增抓取器。dry-run 模式只输出：

- `reports/data_update/<as_of_date>/market_data_update_plan.md`
- `reports/data_update/<as_of_date>/market_data_update_plan.json`

非 dry-run 才调用现有 `update_market_data.py` 和 `build_features.py`。如果更新失败或质量检查失败，observation pipeline 必须继续阻断，不能生成手工订单清单。大体量 parquet、缓存、真实 paper ledger、provider token 和券商信息都不得提交。
