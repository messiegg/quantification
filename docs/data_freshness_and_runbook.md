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
- `data_max_date`
- `feature_max_date`
- `benchmark_max_date`
- `universe_max_effective_date`
- `provider_health_date`
- `data_quality_date`
- `stale_calendar_days`
- `blocking_reason`
- `allowed_actions`

## 阻断规则

如果 `data_max_date < requested_as_of_date`，且观察配置要求数据覆盖目标日期，则输出：

- `is_data_current: false`
- `blocking_reason: DATA_MAX_DATE_BEFORE_AS_OF_DATE`
- `allowed_actions: historical_review_only`

如果 stale calendar days 超过配置上限，继续阻断每日观察报告。缺少 feature snapshot 或 benchmark 也阻断。缺少 provider health 或 data quality 是 `WARN`，报告必须显式说明。

## 当前 2026-05-04 状态

当前 RC 历史数据截止 `2026-04-03`。在数据没有真实更新到 `2026-05-04` 并通过 freshness gate 前，不能生成 `2026-05-04` 的实盘观察日报，也不能生成当日手工执行清单。

正确行为是：

- 生成 `reports/observation/2026-05-04/data_freshness_report.md`
- 生成 `reports/observation/2026-05-04/observation_blocked.md`
- 生成 `reports/observation/2026-05-04/observation_run_manifest.json`
- 不生成 `combined_v2_manual_order_list.csv`

## 全流程

```bash
./.venv/bin/python scripts/check_report_freshness.py
./.venv/bin/python scripts/verify_combined_v2_rc.py
./.venv/bin/python scripts/check_data_freshness.py --as-of-date 2026-05-04 --write-report
./.venv/bin/python scripts/run_observation_pipeline.py --as-of-date 2026-05-04 --profile combined_v2 --mode paper --compare-conservative true
./.venv/bin/python scripts/update_paper_observation.py --as-of-date 2026-05-04
```

即使 freshness gate 通过，输出仍是手工观察和手工执行参考，不是自动交易。
