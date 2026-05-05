# 每日人工观察报告

## 结论区

- 允许生成观察日报: 是。
- 数据 stale 阻断: 否。
- RC verify: PASS。
- report freshness: PASS。
- release sync consistency: PASS。
- data freshness: PASS。
- data quality: WARN。
- 禁止自动下单。
- broker_connected: false。
- auto_order_allowed: false。
- MARKET_CLOSED_AS_OF_DATE。
- 所有动作只作为 next trading day manual review。

## 数据状态

- requested_as_of_date: 2026-05-04
- git_commit: 2d64f444960ceb631de8430a8f406b14d0703010
- config_hash: 737f7484fbffc7d8084cd990831e73048187ea298be039a784f0a2550145d8d2
- data_hash: a09eaa5950a5129cd4f6eb5ef89ebb3937b6496ffe79934d97b42ac17f2a4fcd
- requested_as_of_is_trading_day: false
- target_trading_date: 2026-04-30
- data_max_date: 2026-04-30
- feature_max_date: 2026-04-30
- benchmark_max_date: 2026-04-30
- stale_calendar_days: 4
- stale_trading_days: 0
- blocking_reason: NONE

## 数据质量

- data_quality_status: WARN
- feature_rows_on_target_date: 5151
- unique_stocks_on_target_date: 5151
- benchmark_row_exists_on_target_trading_date: True

### 数据质量 WARN 摘要

- WARN 不等于禁止观察；本报告仍要求人工复核。
- CORE-pe_ttm | pe_ttm completeness | actual=0.27451 | 核心字段缺失超过规则时阻断或降级观察。

## combined_v2 当前状态

- market_regime: risk_on
- max_total_exposure: 0.95
- current paper exposure: 0.00%
- cash: 200000.00
- holdings_count: 0
- effective_universe_size: 31
- raw buy / sell signals: 0 / 0
- executable actions: 0
- blocked reasons: 无

## 手工动作清单

- 只输出建议，需要人工判断和人工执行。
- 不连接券商，禁止自动下单，不生成实盘委托。
- 本地文件: reports/observation/2026-05-04/combined_v2_manual_order_list.csv
- 该文件为 ignored local artifact，不提交公开仓库。
- auto_order_allowed: false。
- broker_connected: false。
- requires_human_review: true。
- review_scope: next_trading_day_manual_review_only。
- execution_scope: NEXT_TRADING_DAY_MANUAL_REVIEW_ONLY。

## combined_v2_1_risk_guard 对照

- combined_v2_1_risk_guard 只作为 conservative_profile 输出，不替换 combined_v2。
- 风险限制阻断差异见 profile_compare.md。
- 是否更保守需要持续观察，不能自动替换主候选。

## 风险提示

- 数据当前通过 freshness gate。
- 当前策略仍只有三年回测，样本偏短。
- risk_off daily MTM 损失仍明显。
- A 股风格切换可能削弱当前估值和 bucket 逻辑。
- 手工观察期不得扩大仓位。
