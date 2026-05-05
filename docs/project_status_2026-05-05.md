# 项目现状说明（2026-05-05）

本文记录当前仓库代码、数据、观察期和发布保护状态。它取代 `docs/project_status_2026-04-05.md` 作为最新状态说明。

## 1. 代码状态

- 当前分支：`codex/combined-v2-rc-release`
- 本轮修改前 HEAD：`ceafa39e41a279d9f40b97e4004aa86c2f80cad9`
- `combined_v2` 交易规则未改。
- `config/strategy_v2.yml` 未改。
- `config/universe_rules_v2.yml` 未改。
- `combined_v2_1_risk_guard` 仍只是 conservative observation candidate，不替换主策略。
- 仓库仍禁止接券商、自动下单、真实订单生成和 LLM 决定 `action_enum`。

## 2. 当前数据与观察状态

2026-05-04 是非交易日，观察期 gate 使用最近目标交易日：

- `requested_as_of_date: 2026-05-04`
- `requested_as_of_is_trading_day: false`
- `target_trading_date: 2026-04-30`
- `data_max_date: 2026-04-30`
- `feature_max_date: 2026-04-30`
- `benchmark_max_date: 2026-04-30`
- `allowed_actions: observation_report_allowed`
- `blocking_reason: NONE`

数据质量当前为 `WARN`：

- 0 FAIL
- 1 WARN
- WARN 来源：`CORE-pe_ttm`
- `pe_ttm` 缺失率：`0.27451`

这意味着可以生成 observation report，但只能作为下一交易日人工复核材料，不能写成当日实盘执行。

## 3. RC 主口径

当前冻结的严格主口径仍是：

- profile: `combined_v2`
- execution_mode: `next_bar`
- period: `2023-04-03` 到 `2026-04-03`
- annual_return: `0.0713520247687258`
- cumulative_return: `0.2196444045310004`
- max_drawdown: `-0.0936454742991675`
- total_trades: `76`
- final_nav: `243928.8809062001`

旧的 `9.14% / 83` 笔是 legacy pre-PIT 旧口径，只能作为历史说明保留。

## 4. 发布保护状态

当前发布保护已接入：

- GitHub Actions Layer 1：轻量测试 `not data_required and not full_backtest`
- GitHub Actions Layer 2：`scripts/run_release_guard.py --ci --as-of-date 2026-05-04`
- `scripts/verify_combined_v2_rc.py --mode hash-only`
- `scripts/check_forbidden_tracked_files.py`
- `config/release_file_allowlist.yml`
- PR / release / CI 与本地验证 checklist

当前报告状态：

- current_release_status: `WARN`
- `reports/backtest/release/release_guard_report.md`: WARN
- `reports/backtest/release/forbidden_tracked_files_check.md`: PASS
- `reports/backtest/release/combined_v2_rc_verify.md`: WARN
- `reports/backtest/release/release_sync_consistency_check.md`: PASS
- `reports/observation/2026-05-04/observation_gate_consistency_check.md`: PASS

主要 WARN 来源：

- `universe_integrity`: selected_count=30，高于 floor=24，但低于 target=36；无硬过滤违规、无缺关键字段。
- `account_constraints`: raw buy 370，executable buy 43，执行比例约 11.6%；min_trade_amount 阻断占比约 59.5%。
- `sensitivity`: `--mode ci` 可完成，但 universe_size、defensive valuation、cyclical PB、grid_step 在当前 CI 窗口为 NON_BINDING。
- `baseline_comparison`: no_high_dividend_supplement、no_trend_stop、no_market_state_filter 优于 combined_v2，标记 MODULE_MAY_BE_DRAG，不自动改策略。
- `observation_readiness`: NOT_READY；尚未形成 60 个观察交易日的人工复核日志，当前不能进入 PASS_CANDIDATE。

新增 WARN 拆解报告：

- `reports/audit/universe_shortfall.md`
- `reports/backtest/account_suitability_report.md`
- `reports/backtest/robustness/sensitivity_trigger_coverage.md`
- `reports/backtest/controls/module_contribution_report.md`
- `reports/observation/readiness_report.md`

## 5. Git 与文件边界

允许提交的是代码、小型配置、文档、fixture 和审计报告。禁止提交：

- 大体量行情数据；
- `data/raw/**`；
- `data/features/**`；
- parquet / sqlite / duckdb / cache；
- provider token、券商账号、真实账户信息；
- 真实 paper ledger；
- observation actions 和 manual order list。

以下文件必须保持 ignored local artifact：

- `data/observation/paper_account.yml`
- `data/observation/paper_trades.csv`
- `data/observation/paper_positions.yml`
- `reports/observation/*/combined_v2_manual_order_list.csv`
- `reports/observation/*/combined_v2_actions.csv`
- `reports/observation/*/combined_v2_1_risk_guard_actions.csv`

仓库中允许保留的 parquet 仅限 `config/release_file_allowlist.yml` 里声明的小型 demo fixture。

## 6. 关于 data gaps 报告

`reports/data_gaps/latest.md` 是全市场严格缺口审计，和 observation gate 不是同一个判定口径。它会继续提示行业数据、估值历史或全市场字段覆盖不足；这些提示不等同于 2026-05-04 observation report 被阻断。

当前是否允许 observation report，应以这些文件为准：

- `reports/observation/2026-05-04/data_freshness_report.json`
- `reports/observation/2026-05-04/data_quality_observation_report.json`
- `reports/observation/2026-05-04/observation_gate_consistency_check.md`
- `reports/backtest/release/release_guard_report.md`

## 7. 提交前验证命令

```bash
./.venv/bin/python scripts/run_release_guard.py --ci --as-of-date 2026-05-04 --write-report
./.venv/bin/python scripts/run_backtest_sensitivity.py --mode ci
./.venv/bin/python scripts/run_backtest_controls.py
./.venv/bin/python scripts/build_baseline_comparison_report.py
./.venv/bin/python scripts/check_forbidden_tracked_files.py --write-report
./.venv/bin/python scripts/verify_combined_v2_rc.py --mode hash-only
./.venv/bin/python -m pytest -q -m "not data_required and not full_backtest"
```

完整本地数据验证再运行：

```bash
./.venv/bin/python scripts/verify_combined_v2_rc.py --mode full
./.venv/bin/python scripts/run_backtest_sensitivity.py --mode full
./.venv/bin/python scripts/run_backtest_controls.py --refresh-all
./.venv/bin/python -m pytest -q
```
