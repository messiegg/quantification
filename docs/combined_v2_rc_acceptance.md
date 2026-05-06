# combined_v2 RC acceptance

## 主口径

- profile: `combined_v2`
- execution_mode: `next_bar`
- default account profile: `retail_50k_lot_aware`
- period: `2023-04-03` 到 `2026-04-03`
- annual_return: `0.024846220411411934`
- cumulative_return: `0.07326562069200016`
- max_drawdown: `-0.08876605706976393`
- total_trades: `41`
- buy_trades: `23`
- best possible rating: `PASS_CANDIDATE`

`PASS_CANDIDATE` 只表示“小资金、手动、严格复核观察/试运行候选”。它不是自动实盘批准，也不是券商接入批准。当前 release guard 会整合配置一致性、universe integrity、数据新鲜度、前视审计、sensitivity、账户约束、账户 profile 对比、evidence chain、baseline comparison 和测试状态；任一核心审计 FAIL 时，release 必须为 `FAIL`。`actual_50k_lot_aware` 当前 executable/raw 约 3.66%，低于 25% 门槛，因此当前只能保持 `WARN`。

## 验证方式

CI / 发布保护使用 hash-only 口径，不重跑完整回测：

```bash
./.venv/bin/python scripts/verify_combined_v2_rc.py --mode hash-only
./.venv/bin/python scripts/audit_config_consistency.py
./.venv/bin/python scripts/audit_universe_integrity.py
./.venv/bin/python scripts/audit_data_freshness.py --as-of-date 2026-05-04
./.venv/bin/python scripts/run_account_profile_backtests.py
./.venv/bin/python scripts/run_backtest_sensitivity.py --mode ci
./.venv/bin/python scripts/run_backtest_controls.py
./.venv/bin/python scripts/build_baseline_comparison_report.py
./.venv/bin/python scripts/run_release_guard.py --ci --as-of-date 2026-05-04
./.venv/bin/python scripts/check_forbidden_tracked_files.py --write-report
./.venv/bin/python scripts/check_report_freshness.py
```

本地完整数据环境才使用 full 口径：

```bash
./.venv/bin/python scripts/verify_combined_v2_rc.py --mode full
./.venv/bin/python scripts/run_backtest_sensitivity.py --mode full
./.venv/bin/python scripts/run_backtest_controls.py --refresh-all
```

`run_backtest_sensitivity.py --mode ci` 必须真实覆盖核心参数并输出 BINDING / NON_BINDING / ERROR 分类；release guard 只认可 `mode=ci` 的 sensitivity 报告。`run_backtest_controls.py` 默认增量复用已有真实 control/placebo 结果，只补齐缺失消融；不会把缺失消融跳过为 PASS。

当前 WARN 拆解必须同时刷新这些解释型报告：

- `scripts/build_universe_shortfall_report.py`
- `scripts/run_account_profile_backtests.py`
- `scripts/build_account_suitability_report.py`
- `scripts/build_sensitivity_trigger_coverage_report.py`
- `scripts/build_module_contribution_report.py`
- `scripts/evaluate_observation_readiness.py`
- `scripts/check_release_status_consistency.py`

这些报告只解释 WARN 来源，不放宽 universe、账户、sensitivity 或 baseline 审计门槛；真实风险仍必须进入 release manifest risk section。

输出：

- `reports/backtest/release/combined_v2_rc_verify.csv`
- `reports/backtest/release/combined_v2_rc_verify.md`
- `reports/backtest/release/combined_v2_rc_code_manifest.json`
- `reports/audit/config_consistency.json`
- `reports/audit/universe_integrity.json`
- `reports/audit/data_freshness.json`
- `reports/observation/2026-05-04/evidence_chain.json`
- `reports/backtest/account_constraints_report.json`
- `reports/backtest/account_profiles/account_profile_comparison.json`
- `reports/backtest/account_profiles/account_profile_comparison.md`
- `reports/backtest/account_profiles/lot_affordability_report.json`
- `reports/backtest/account_profiles/lot_affordability_report.md`
- `reports/backtest/controls/baseline_comparison.json`
- `reports/backtest/release/release_guard_report.md`
- `reports/backtest/release/forbidden_tracked_files_check.md`
- `reports/backtest/audit/stale_report_check.csv`
- `reports/backtest/audit/stale_report_check.md`

配置 hash 漂移是 `FAIL`。核心策略代码 hash 漂移过去作为 `WARN` 处理；当前发布保护阶段要求先通过 `release_guard`，再决定是否需要本地 full 复核。报告 hash 漂移而严格指标一致时也是 `WARN`，需要刷新报告或解释差异。

截至当前发布保护口径：

- latest commit: `f0cd73e15a915b7af4373421dbb57797de0dea83`
- `verify_combined_v2_rc --mode hash-only`: PASS
- `run_release_guard --ci --as-of-date 2026-05-04`: 由当前审计产物决定；若 universe 低于 floor 或硬过滤违规，必须 FAIL。
- `check_forbidden_tracked_files`: PASS

## 不得改变的边界

- 不修改 `combined_v2` 买入、卖出、网格、market regime、cycle_peak_trap、hard_add_ban、fundamental_break 逻辑。
- 不修改 `config/universe_rules_v2.yml` 的选股硬规则；小账户只调整组合执行层容量。
- 不接券商，不自动下单，不让 LLM 决定 `action_enum`。
- 不允许在 universe/data/evidence 任一 gate FAIL 时生成“可执行买卖建议”；只能生成阻断报告。
- 不用 `2026-04-03` 之后的数据改写三年历史回测。
- `combined_v2_1_risk_guard` 只保留为 conservative observation candidate，不替换主策略。

## legacy 记录

`9.14% / 83` 笔属于 legacy pre-PIT 旧记录，只能作为 superseded 历史说明保留。`reference_200k_current` 的 PIT `next_bar` 研究对照是 `7.1352% / 76` 笔；当前默认 release 账户是 `retail_50k_lot_aware`，不是 200k 参考口径。
