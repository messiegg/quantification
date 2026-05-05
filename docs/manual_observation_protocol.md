# 手工观察协议

## 运行模式

观察期由 `config/observation.yml` 定义：

- primary_profile: `combined_v2`
- conservative_profile: `combined_v2_1_risk_guard`
- mode: `paper_observation_only`
- allow_broker_connection: `false`
- allow_auto_order: `false`
- allow_llm_decision: `false`
- generate_real_orders: `false`

这个配置只定义观察运行方式，不改变策略交易规则。

## 每日入口

```bash
./.venv/bin/python scripts/run_observation_pipeline.py \
  --as-of-date 2026-05-04 \
  --profile combined_v2 \
  --mode paper \
  --compare-conservative true
```

运行顺序：

1. 用 hash-only 模式验证 combined_v2 RC，不重跑完整回测。
2. 运行配置一致性、universe integrity、数据新鲜度、data quality、evidence chain 和 release guard。
3. 只有所有核心 gate 通过时，才生成观察摘要、动作候选、阻断原因和手工动作清单。
4. 数据过期、universe 低于 floor、硬过滤违规或 evidence chain 缺失时，只输出 blocked / historical review 报告，不输出手工订单清单。

当前 2026-05-04 观察状态：

- 2026-05-04 是非交易日，`target_trading_date = 2026-04-30`。
- `data_max_date / feature_max_date / benchmark_max_date = 2026-04-30`。
- freshness 由 `scripts/audit_data_freshness.py` 校验，字段包括 `requested_date`、`target_trade_date`、`market_data_asof`、`feature_data_asof`、`benchmark_data_asof`、`financial_data_asof`、`effective_financial_date`。
- universe integrity 由 `scripts/audit_universe_integrity.py` 校验；低于 `floor_size=24`、超过 `ceiling_size=48`、超过 `max_per_industry=3` 或违反硬过滤时阻断观察建议。
- data quality 为 `WARN`，当前 WARN 是 `pe_ttm` 缺失率 `0.27451`，0 FAIL。
- 输出只能作为下一交易日人工复核，不是今日实盘执行；任何 gate FAIL 时只能输出阻断报告。

## 纸面账户

首次运行会创建：

- `data/observation/paper_account.yml`
- `data/observation/paper_trades.csv`
- `data/observation/paper_positions.yml`

这三个文件是真实本地纸面账本，属于持续变化的本地产物，已被 `.gitignore` 忽略，不提交。仓库只提交 `fixtures/observation/` 下的 example 模板；首次运行时脚本会从 example 初始化本地文件。

更新纸面账本：

```bash
./.venv/bin/python scripts/update_paper_observation.py --as-of-date 2026-05-04
```

纸面账本只允许三种来源：

- `paper_next_bar_simulated`
- `manual_user_entered`
- `correction`

人工复核状态只允许：

- `pending`
- `approved`
- `rejected`
- `executed_paper`
- `corrected`

## 人工边界

观察报告和手工清单只是人工参考。任何真实交易都必须由人判断、人执行；仓库不连接券商，不自动下单，不生成真实委托。

`combined_v2_1_risk_guard` 会并行输出作保守观察对照，但不得自动替换 `combined_v2`。

## 提交边界

以下文件必须保持本地 ignored，不提交公开仓库：

- `data/observation/paper_account.yml`
- `data/observation/paper_trades.csv`
- `data/observation/paper_positions.yml`
- `reports/observation/*/combined_v2_manual_order_list.csv`
- `reports/observation/*/combined_v2_actions.csv`
- `reports/observation/*/combined_v2_1_risk_guard_actions.csv`

提交前至少运行：

```bash
./.venv/bin/python scripts/run_release_guard.py --ci --as-of-date 2026-05-04 --write-report
./.venv/bin/python scripts/check_forbidden_tracked_files.py --write-report
```

附加审计产物：

- `reports/audit/config_consistency.json`
- `reports/audit/universe_integrity.json`
- `reports/audit/data_freshness.json`
- `reports/observation/<as-of-date>/evidence_chain.json`
