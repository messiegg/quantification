# A 股半自动规则研究项目

这是一个面向 A 股 long-only 的半自动研究工程。系统只生成规则驱动的股票池、每日动作建议和手动执行清单；不接券商、不自动交易、不把买卖裁决交给 LLM。

## 当前原则

- Python 规则引擎决定 `action_enum`、目标仓位、目标金额。
- LLM 只允许解释已有结果、检查异常、辅助审阅，不允许重算或改写 `action_enum`。
- `config/universe.yml` 是自动生成的 effective universe 产物，不再手工编辑。
- `data/ledger/trades.csv` 是逐笔成交账本；`config/positions.yml` 建议由账本重建，而不是手工逐笔改。
- `config/account.yml` 用于金额与仓位货币化约束；缺失时只输出方向性建议。

## 关键对象

### candidate pool

通过硬过滤并完成打分的候选集合。

### effective universe

当前再平衡周期允许新开仓/加仓的正式有效池，由 `scripts/refresh_universe.py --apply` 自动生成。该入口默认使用 `config/universe_rules_v2.yml` 生成 combined_v2 active universe；如需旧 baseline universe，必须显式传入 `--universe-rules-config config/universe_rules.yml`。

### current holdings scope

真实持仓范围。每日决策作用域始终是：

`effective_universe ∪ current_holdings`

因此，持仓即使已被踢出有效池，也不会从日常风控里消失。

## universe 生成逻辑

- 默认频率：月度；也支持季度。
- 再平衡日：月末或季末收盘后生成新一期 effective universe，下一交易日生效。
- 非再平衡日：复用当前 effective universe，不重建。
- `combined_v2` 当前运行规则：`target_size=36`、`floor_size=24`、`ceiling_size=48`、`max_per_industry=3`。
- 稳定器：`combined_v2` 老成员依据 `retained_min_score`、`retained_industry_rank`、`retained_any_rank_score` 保留；新成员依据 `new_min_score`、`new_industry_rank` 进入。
- universe integrity 审计默认开启；当前池低于 floor、超过 ceiling、超过行业上限、违反硬过滤或 manual override 无配置依据时，release/observation 必须 fail closed。
- 输出：
  - `config/universe.yml`
  - `reports/universe/latest.md`
  - `reports/universe/latest.json`
  - `data/curated/universe_history/`

## 持仓状态机

### ACTIVE

当前在 effective universe 中。允许 `BUY_1 / BUY_2 / BUY_3 / HOLD / REDUCE / SELL_ALL`。

### FROZEN

当前不在 effective universe 中，但真实持仓仍在。只允许 `HOLD_FROZEN / REDUCE / SELL_ALL`。

被踢出池子不会立刻卖出，因为“失去入池资格”不等于“必须立即退出”。系统先冻结，继续做风险控制与减仓判断，避免月月大换血。

### FORCE_EXIT

命中 ST、fundamental break、退市风险、长期数据失真、长期停牌等硬规则。必须 `SELL_ALL`。

## 账户与金额约束

- 回测读取 `config/account.yml -> account.initial_capital`，因为回测需要从明确初始资金开始模拟净值与仓位演化。
- 日常执行读取 `current_cash`、`reserved_cash`、`latest_total_equity`，因为现实账户的可买金额取决于当前现金和当前总权益，而不是历史初始资金。
- `target_position_tranches -> target_weight` 的映射由 `config/account.yml -> position_sizing.tranche_weights` 决定。
- orders 会显式输出 `target_shares`、`delta_shares`、`rounded_lots`、`estimated_turnover`、`estimated_commission`、`estimated_stamp_duty`、`estimated_total_cash_impact`、`target_price_reference`。
- 若整手约束、最小成交额或现金不足导致不可执行，`action_enum` 会改为 `BLOCKED`，并写入 `blocked_reason`。
- 若缺少 `account.yml` 或关键字段缺失，系统仍输出 `action_enum`，但 orders 会进入 degraded mode：
  - 不输出精确 `target_order_value`
  - 报告显式提示“仅有方向性建议，未完成金额约束”

## 日度动作

固定动作枚举：

- `BUY_1`
- `BUY_2`
- `BUY_3`
- `HOLD`
- `HOLD_FROZEN`
- `REDUCE`
- `SELL_ALL`
- `EMPTY`
- `BLOCKED`
- `DATA_ERROR`

每日 orders 至少包含：

- 当前/目标 tranche
- 当前/目标权重
- 目标仓位变化
- 当前/目标股数与整手数
- `target_order_value`
- `priority_score`
- `blocked_reason`
- `reason_codes`
- `risk_flags`

## 运行流程

### 1. 更新数据

实际写数据前先走安全 preflight；只有人工确认后才允许加 `--execute`：

```bash
./.venv/bin/python scripts/update_market_data_safe.py --as-of-date 2026-05-04 --preflight-only --write-report
./.venv/bin/python scripts/update_market_data_safe.py --as-of-date 2026-05-04 --dry-run --write-report
```

数据刷新后会同步写出：

- `provider_health/latest.json`
- `data_quality/latest.json`

### 2. 构建特征

```bash
./.venv/bin/python scripts/build_features.py
```

默认输出：

- `data/features/daily_features/`
- `data/features/latest_feature_snapshot.parquet`

### 3. 重建 effective universe

```bash
./.venv/bin/python scripts/refresh_universe.py --as-of-date 2026-04-30 --apply
```

### 4. 生成 snapshot

```bash
./.venv/bin/python scripts/prepare_snapshot.py --as-of-date 2026-04-30
```

### 5. 生成 orders 与日报

```bash
./.venv/bin/python scripts/render_report.py --snapshot-json data/snapshots/latest.json
```

### 6. 导入真实成交并重建持仓

```bash
./.venv/bin/python scripts/import_fills.py --fills-csv /path/to/manual_fills.csv
./.venv/bin/python scripts/reconcile_positions.py
```

### 7. 跑固定 demo

```bash
bash scripts/run_demo.sh
```

固定输出：

- `reports/daily/latest.json`
- `reports/daily/latest.md`
- `reports/daily/orders_latest.json`
- `reports/daily/orders_latest.csv`
- `data/curated/run_manifest.json`

## 回测说明

- 回测复用同一套 action enum、仓位段数和 tranche weight。
- `refresh_universe.py --apply` 会把每期 effective universe 写入 `data/curated/universe_history/`。
- 回测可按历史 effective universe 回放；若历史池缺失，会显式标记 `approximate_backtest`。
- 即使历史 effective universe 不完整，回测仍会保留已持仓标的的风险控制逻辑，不把“脱池”直接等同于“立刻清仓”。

### baseline 诊断与 combined_v2 对比

正式三年诊断固定使用本地已验证数据窗口 `2023-04-03` 到 `2026-04-03`，不读取或假定 `2026-04-03` 之后的数据。baseline 仍使用 `config/strategy.yml` 与 `config/universe_rules.yml`；新策略使用独立的 `config/strategy_v2.yml` 与 `config/universe_rules_v2.yml`，不覆盖旧逻辑。

单独跑 baseline 诊断：

```bash
./.venv/bin/python scripts/backtest.py \
  --bucket combined \
  --start-date 2023-04-03 \
  --end-date 2026-04-03 \
  --historical-universe-dir data/curated/universe_history \
  --diagnostics-prefix baseline
```

跑 baseline 与 combined_v2 对比：

```bash
./.venv/bin/python scripts/run_backtest_compare.py \
  --start-date 2023-04-03 \
  --end-date 2026-04-03
```

对比脚本会生成：

- `reports/backtest/baseline_signal_funnel.csv`
- `reports/backtest/baseline_universe_funnel.csv`
- `reports/backtest/baseline_blocked_signals.csv`
- `reports/backtest/baseline_trades_detailed.csv`
- `reports/backtest/baseline_diagnostic_report.md`
- `reports/backtest/combined_v2_signal_funnel.csv`
- `reports/backtest/combined_v2_universe_funnel.csv`
- `reports/backtest/combined_v2_blocked_signals.csv`
- `reports/backtest/combined_v2_trades_detailed.csv`
- `reports/backtest/combined_v2_candidate_scores.csv`
- `reports/backtest/combined_v2_diagnostic_report.md`
- `reports/backtest/compare_combined_vs_v2_metrics.csv`
- `reports/backtest/compare_combined_vs_v2.md`

### combined_v2 严格审计与鲁棒性报告

审计固定使用 `2023-04-03` 到 `2026-04-03`，不读取 `2026-04-03` 之后的数据；主口径为 `execution_mode=next_bar`，即 t 日收盘后形成信号，下一交易日按 open 成交，缺少 open 时退回下一交易日 close。`same_close` 只作为乐观成交价对照。

运行完整性、前视、配置一致性、universe 完整性、数据新鲜度、执行口径、walk-forward、敏感性、成本、账户约束、control baseline 和归因审计：

```bash
./.venv/bin/python scripts/audit_backtest_integrity.py
./.venv/bin/python scripts/audit_backtest_lookahead.py
./.venv/bin/python scripts/audit_config_consistency.py
./.venv/bin/python scripts/audit_universe_integrity.py
./.venv/bin/python scripts/audit_data_freshness.py --as-of-date 2026-05-04
./.venv/bin/python scripts/run_backtest_execution_compare.py
./.venv/bin/python scripts/run_backtest_walkforward.py
./.venv/bin/python scripts/run_backtest_sensitivity.py --mode ci
./.venv/bin/python scripts/run_backtest_cost_stress.py
./.venv/bin/python scripts/build_account_constraints_report.py
./.venv/bin/python scripts/run_backtest_attribution.py
./.venv/bin/python scripts/run_backtest_controls.py
./.venv/bin/python scripts/build_baseline_comparison_report.py
./.venv/bin/python scripts/run_backtest_v2_1_risk_guard.py
./.venv/bin/python scripts/build_combined_v2_release_candidate.py
./.venv/bin/python scripts/build_combined_v2_audit_summary.py
```

关键输出：

- `reports/backtest/audit/integrity_audit.md`
- `reports/backtest/audit/lookahead_audit.md`
- `reports/audit/config_consistency.md`
- `reports/audit/universe_integrity.md`
- `reports/audit/data_freshness.md`
- `reports/backtest/audit/universe_pit_audit.csv`
- `reports/backtest/audit/execution_mode_compare.md`
- `reports/backtest/robustness/walkforward_report.md`
- `reports/backtest/robustness/sensitivity_report.md`
- `reports/backtest/robustness/sensitivity_report.json`
- `reports/backtest/robustness/cost_stress_report.md`
- `reports/backtest/account_constraints_report.md`
- `reports/backtest/attribution/combined_v2_attribution_report.md`
- `reports/backtest/attribution/combined_v2_monthly_returns_check.csv`
- `reports/backtest/attribution/combined_v2_signal_attribution.csv`
- `reports/backtest/attribution/combined_v2_daily_regime_attribution.csv`
- `reports/backtest/controls/control_baselines_report.md`
- `reports/backtest/controls/baseline_comparison.md`
- `reports/backtest/controls/random_placebo_metrics.csv`

`run_backtest_sensitivity.py --mode ci` 是 release guard 使用的有界核心参数敏感性检查；`--mode full` 保留为本地完整研究口径，会写入 `sensitivity_report_full.*`。`run_backtest_controls.py` 默认复用已有真实 control/placebo 结果，只补算缺失消融；使用 `--refresh-all` 才会重跑全部 control。
- `reports/backtest/v2_1/compare_v2_vs_v2_1_risk_guard.md`
- `reports/backtest/audit/report_consistency_check.csv`
- `reports/backtest/audit/lookahead_valuation_field_resolution.csv`
- `reports/backtest/release/combined_v2_rc_manifest.json`
- `reports/backtest/release/combined_v2_rc_manifest.md`
- `reports/backtest/audit/combined_v2_audit_summary.md`
- `reports/backtest/audit/combined_v2_rc_summary.md`

当前严格主口径：`combined_v2 PIT next_bar`。PIT 修正后的 combined_v2 next_bar 年化为 `7.14%`、累计收益 `21.96%`、最大回撤 `-9.36%`、成交 `76` 笔。上一轮 `9.14%`、`83` 笔是 legacy pre-PIT 旧口径，已由 `INT-012-LEGACY` 标记为 superseded，不再作为当前主策略必须复现的 PASS/FAIL 标准。当前复现检查为 `INT-013-CURRENT-PIT-STRICT`。

归因报告已修正三项口径：

- 月度收益用连续 NAV 链计算，`combined_v2_monthly_returns_check.csv` 最后一行复合累计与 final NAV 累计差异应小于 `1e-8`。
- 未平仓持仓的持有天数统计到回测结束日，并输出 `is_open_position`、`open_position_days`、`realized_holding_days`、`total_holding_days_to_end`。
- signal attribution 拆为 entry signal、exit signal、entry-exit pair；regime attribution 拆为成交/兑现口径和 daily MTM 口径。
- 估值分位审计不再检查不存在的泛型字段，而是记录 resolver 实际使用的 stock/industry source field、metric 和 source date；release manifest 冻结当前 next_bar 主口径、配置路径、核心绩效和关键输出哈希。

control baseline 固定三年窗口、next_bar、同一账户成本，不覆盖正式 v2 配置。`base_dianjinshu_like` 是仓库配置中定义的“点金术风格基线”，不是对外部作者原文的严格复刻；模块消融只做解释，不自动修改主策略。`combined_v2_1_risk_guard` 是独立候选 profile，只改 market regime 风险侧买入限制，沿用 v2 universe，不替换 combined_v2 主口径。

### combined_v2 RC 与观察期运行

当前发布候选主口径冻结为：

- profile: `combined_v2`
- execution_mode: `next_bar`
- period: `2023-04-03` 到 `2026-04-03`
- annual_return: `0.0713520247687258`
- cumulative_return: `0.2196444045310004`
- max_drawdown: `-0.0936454742991675`
- total_trades: `76`
- final_nav: `243928.8809062001`
- release guard best possible rating: `PASS_CANDIDATE`
- current_release_status: `WARN`

`PASS_CANDIDATE` 只代表小资金、手动、严格复核观察/试运行候选；它不是自动实盘策略批准。仓库仍禁止接券商、禁止自动下单、禁止让 LLM 决定买卖。若 config consistency、universe integrity、data freshness、lookahead、sensitivity、evidence chain、baseline comparison 或 tests 任一核心审计 FAIL，release guard 必须输出 `FAIL`。

当前 `WARN` 不是硬阻断，但仍不能写成 `PASS_CANDIDATE`：effective universe 当前 30 只，高于 `floor_size=24` 但低于 `target_size=36`；账户约束仍主导买入执行；sensitivity 仍有核心参数在 CI 窗口 NON_BINDING；baseline 消融里仍有模块需要人工解释风险收益权衡；观察期 readiness 尚未满足 60 个交易日人工复核日志要求。新增报告入口：

- `reports/audit/universe_shortfall.md`
- `reports/backtest/account_suitability_report.md`
- `reports/backtest/robustness/sensitivity_trigger_coverage.md`
- `reports/backtest/controls/module_contribution_report.md`
- `reports/observation/readiness_report.md`

2026-05-04 当前 observation 示例状态：

- `as_of_date`: `2026-05-04`，非交易日。
- `target_trading_date`: `2026-04-30`。
- `data_max_date` / `feature_max_date` / `benchmark_max_date`: `2026-04-30`。
- freshness: 由 `scripts/audit_data_freshness.py` 与 observation pipeline 共同判定。
- universe integrity: 若当前 `config/universe.yml` 低于 `floor_size=24` 或有硬过滤违规，observation pipeline 必须生成阻断报告，不得生成可执行买卖建议。
- data quality: `WARN`，当前主要 WARN 是 `pe_ttm` 缺失率偏高。
- 结论：只允许下一交易日人工复核；在 universe/data/evidence 任一 gate FAIL 时，只输出阻断报告，不代表今日实盘执行。

### 观察期准入规则

观察期准入由 `config/observation_readiness.yml` 和 `scripts/evaluate_observation_readiness.py` 判定。当前策略即使没有硬 FAIL，也必须满足至少 60 个观察交易日、每日报告 evidence chain、人工复核日志、无数据新鲜度 FAIL、无 universe floor FAIL、无 UNKNOWN/PARAM_NOT_WIRED sensitivity 参数，并且 base case 买入 executable/raw 比例达到配置阈值，才可能从 `WARN` 进入 `PASS_CANDIDATE`。真实人工复核日志路径 `data/observation/manual_review_log.csv` 必须保持本地 ignored；仓库只提交 `fixtures/observation/manual_review_log_template.csv` 模板。

验证 RC 的 CI 轻量口径：

```bash
./.venv/bin/python scripts/verify_combined_v2_rc.py --mode hash-only
```

本地完整数据环境验证 RC：

```bash
./.venv/bin/python scripts/verify_combined_v2_rc.py --mode full
```

检查旧报告残留：

```bash
./.venv/bin/python scripts/check_report_freshness.py
```

检查 observation 发布同步报告是否仍含提交前状态残留：

```bash
./.venv/bin/python scripts/check_release_sync_consistency.py
```

交易日感知数据新鲜度与安全更新计划：

```bash
./.venv/bin/python scripts/check_data_freshness.py --as-of-date 2026-05-04 --write-report
./.venv/bin/python scripts/audit_data_freshness.py --as-of-date 2026-05-04
./.venv/bin/python scripts/audit_universe_integrity.py
./.venv/bin/python scripts/build_observation_evidence_chain.py --as-of-date 2026-05-04
./.venv/bin/python scripts/run_data_update_preflight.py --as-of-date 2026-05-04 --write-report
./.venv/bin/python scripts/update_market_data_safe.py --as-of-date 2026-05-04 --dry-run --write-report
./.venv/bin/python scripts/check_observation_gate_consistency.py --as-of-date 2026-05-04
```

### CI / 发布保护

GitHub Actions 分两层默认运行：

- Layer 1 轻量测试：

```bash
python -m pytest -q -m "not data_required and not full_backtest"
```

- Layer 2 report guard：

```bash
python scripts/run_release_guard.py --ci --as-of-date 2026-05-04
```

CI 不跑完整数据回测，不更新行情数据，不生成真实订单。完整本地验证仍在有本地数据的环境运行：

```bash
./.venv/bin/python scripts/verify_combined_v2_rc.py --mode full
./.venv/bin/python scripts/check_data_freshness.py --as-of-date 2026-05-04 --write-report
./.venv/bin/python scripts/check_data_quality_for_observation.py --as-of-date 2026-05-04 --write-report
./.venv/bin/python scripts/run_observation_pipeline.py --as-of-date 2026-05-04 --profile combined_v2 --mode paper --compare-conservative true
```

本地 pre-commit 风格检查不强制安装 hook，提交前手动运行：

```bash
./.venv/bin/python scripts/run_release_guard.py --ci --as-of-date 2026-05-04 --write-report
./.venv/bin/python scripts/check_forbidden_tracked_files.py --write-report
./.venv/bin/python scripts/verify_combined_v2_rc.py --mode hash-only
./.venv/bin/python -m pytest -q -m "not data_required and not full_backtest"
```

发布保护报告：

- `reports/backtest/release/release_guard_report.md`
- `reports/backtest/release/release_guard_report.csv`
- `reports/backtest/release/forbidden_tracked_files_check.md`
- `reports/backtest/release/forbidden_tracked_files_check.csv`

真实 paper ledger 仍只保留在本地 ignored 文件中；`combined_v2_manual_order_list.csv` 和 observation actions 也是 ignored local artifact，不提交公开仓库。小型 demo fixture 如需保留，必须写入 `config/release_file_allowlist.yml`，并声明原因、大小上限和 `may_contain_sensitive_data: false`。

更多流程见：

- `docs/ci_and_local_validation.md`
- `docs/release_checklist.md`
- `docs/pr_checklist.md`

关键输出：

- `reports/backtest/release/combined_v2_rc_verify.csv`
- `reports/backtest/release/combined_v2_rc_verify.md`
- `reports/backtest/release/combined_v2_rc_code_manifest.json`
- `reports/backtest/audit/stale_report_check.csv`
- `reports/backtest/audit/stale_report_check.md`
- `reports/backtest/release/observation_sync_check.csv`
- `reports/backtest/release/observation_sync_check.md`
- `reports/backtest/release/observation_release_sync_summary.md`
- `reports/backtest/release/release_sync_consistency_check.csv`
- `reports/backtest/release/release_sync_consistency_check.md`
- `reports/data_update/2026-05-04/market_data_update_plan.md`
- `reports/data_update/2026-05-04/market_data_update_plan.json`
- `reports/data_update/provider_preflight/data_update_cli_audit.md`
- `reports/data_update/provider_preflight/provider_readiness_report.md`
- `reports/data_update/provider_preflight/data_update_preflight_summary.md`
- `reports/observation/2026-05-04/observation_gate_consistency_check.md`

### 数据新鲜度守门

```bash
./.venv/bin/python scripts/check_data_freshness.py --as-of-date 2026-05-04 --write-report
```

`2026-05-04` 是 A 股劳动节休市期间，交易日感知 gate 会先映射到最近目标交易日 `2026-04-30`。如果 `data_max_date`、`feature_max_date` 和 `benchmark_max_date` 都已经覆盖到 `target_trading_date`，则非交易日自然增加的 `stale_calendar_days` 只作为 warning，不作为硬阻断；硬门槛是目标交易日覆盖和 `stale_trading_days`。

数据覆盖目标交易日时正确动作：

- `allowed_actions: observation_report_allowed`。
- `blocking_reason: NONE`。
- `calendar_staleness_blocking: false`。
- 输出 `reports/observation/<as_of_date>/observation_summary.md`。
- 非交易日 summary 必须包含 `MARKET_CLOSED_AS_OF_DATE`，并明确只允许下一交易日人工复核，不自动下单。

数据 stale 时正确动作：

- 只允许 historical review。
- 输出 `reports/observation/<as_of_date>/data_freshness_report.md`。
- 输出 `reports/observation/<as_of_date>/observation_blocked.md`。
- 不生成 `combined_v2_manual_order_list.csv`。

### observation pipeline

```bash
./.venv/bin/python scripts/run_observation_pipeline.py \
  --as-of-date 2026-05-04 \
  --profile combined_v2 \
  --mode paper \
  --compare-conservative true
```

全流程会先验证 RC，再检查报告 freshness、release sync、一致性和数据 freshness。任何 `RC_VERIFY_FAIL`、`REPORT_STALE_OR_CONFLICTING`、`RELEASE_SYNC_CONSISTENCY_FAIL`、`STALE_DATA_BLOCKED` 或 `DATA_QUALITY_FAIL` 都会阻断日度动作输出。数据质量为 `WARN` 时可以生成观察报告，但报告必须列出 WARN 摘要并保留人工复核标记。通过时才生成：

- `reports/observation/<as_of_date>/observation_summary.md`
- `reports/observation/<as_of_date>/combined_v2_actions.csv`
- `reports/observation/<as_of_date>/combined_v2_blocked_signals.csv`
- `reports/observation/<as_of_date>/combined_v2_manual_order_list.csv`
- `reports/observation/<as_of_date>/combined_v2_1_risk_guard_actions.csv`
- `reports/observation/<as_of_date>/profile_compare.md`
- `reports/observation/<as_of_date>/observation_run_manifest.json`

`combined_v2_1_risk_guard` 只作为 conservative profile 并行观察，不替换 `combined_v2`。

非交易日如果生成 `combined_v2_manual_order_list.csv`，它仍是本地人工复核产物，不是真实订单；每行必须标记 `NEXT_TRADING_DAY_MANUAL_REVIEW_ONLY`、`auto_order_allowed=false`、`broker_connected=false`、`requires_human_review=true`，并继续由 `.gitignore` 保护。

### paper ledger

首次观察会创建：

- `data/observation/paper_account.yml`
- `data/observation/paper_trades.csv`
- `data/observation/paper_positions.yml`

这三个文件是真实本地纸面账本，已在 `.gitignore` 中忽略，不提交到公开仓库。仓库只提交 `fixtures/observation/` 下的 example 模板；`scripts/update_paper_observation.py` 首次运行时会从 example 初始化本地账本。

更新纸面账本：

```bash
./.venv/bin/python scripts/update_paper_observation.py --as-of-date 2026-05-04
```

纸面账本只记录人工确认或模拟成交，不连接券商，不自动下单。即使生成观察报告，也只是手工观察和手工执行参考。

详细说明见：

- `docs/combined_v2_rc_acceptance.md`
- `docs/manual_observation_protocol.md`
- `docs/data_freshness_and_runbook.md`
- `docs/project_status_2026-05-05.md`

## 对账与可复现

- `scripts/run_demo.sh` 使用 `fixtures/demo_case/` 的固定输入，重建一致的 `config/universe.yml`、`reports/daily/orders_latest.json` 和 `data/curated/run_manifest.json`。
- `run_manifest.json` 会记录 git commit、配置哈希、输入文件哈希、`as_of_date` 和数据源信息。
- `provider_health/latest.json` 记录数据源调用成功/失败和回退路径。
- `data_quality/latest.json` 记录核心表的行数、日期范围、缺失率与 stale 状态。

## 数据源

- 免费数据源优先。
- `JQData` 仅在环境变量存在时启用。
- 数据源失败时必须显式降级，不允许静默填假数据。
- `scripts/update_market_data.py` 每次运行都会先清理请求级缓存目录，避免历史缓存无限堆积；正式主表仍保留在 `data/raw/*.parquet`。

### 数据源 preflight

实际写数据前必须先跑：

```bash
./.venv/bin/python scripts/audit_data_update_cli.py --write-report
./.venv/bin/python scripts/check_provider_readiness.py --as-of-date 2026-05-04 --write-report
./.venv/bin/python scripts/update_market_data_safe.py --as-of-date 2026-05-04 --preflight-only --write-report
./.venv/bin/python scripts/run_data_update_preflight.py --as-of-date 2026-05-04 --write-report
```

`update_market_data_safe.py` 不带 `--execute` 时不会写行情、特征或缓存数据。provider readiness 只记录 token 是否存在，不输出 token 原文。只有 CLI audit 可生成合法命令、provider readiness 通过、输出路径可写，并且人工确认后，才允许使用 `--execute` 进入真实数据更新；该命令仍然不连接券商、不自动下单。

## 存储约定

- 原始主表长期保留：`data/raw/price_daily.parquet`、`data/raw/stock_valuation.parquet`、`data/raw/financials.parquet` 等。
- 请求级缓存按运行清空：当前默认清理 `data/raw/akshare/`。
- 日频特征默认按年份分区写入 `data/features/daily_features/`，例如 `2025.parquet`、`2026.parquet`。
- `scripts/prepare_snapshot.py`、`scripts/refresh_universe.py`、`scripts/backtest.py` 默认直接读取这个分区目录，无需手工拼接。

## 约束

- 禁止自动交易、自动下单、券商接入。
- 规则长期写在代码与配置中，不允许在 prompt 中临场决定交易动作。
- 修改策略阈值时必须同步更新配置、README 与测试。
