# PR 检查清单

提交 PR 前请逐项确认，并在 PR 描述中保留适用项。

## 策略与执行边界

- 我没有修改 `combined_v2` 交易规则；如果修改了，已明确说明改动内容和审计影响。
- 我没有接券商、没有新增券商 API、没有自动下单能力。
- 我没有让 LLM 参与 `action_enum`、买卖裁决或仓位裁决。
- 我没有把 `combined_v2_1_risk_guard` 替换成主策略。

## 文件与隐私边界

- 我没有提交真实 paper ledger。
- 我没有提交 provider token、password、secret、券商账号或真实账户信息。
- 我没有提交大体量数据、parquet、sqlite、duckdb、cache、`data/features/**` 或 `data/raw/**`；小型 fixture 例外必须在 `config/release_file_allowlist.yml` 写明原因和大小上限。
- 我没有提交 `combined_v2_manual_order_list.csv` 或 observation actions 文件。

## 验证

- 我运行了 release guard：

```bash
./.venv/bin/python scripts/run_release_guard.py --ci --as-of-date 2026-05-04 --write-report
```

- 我运行了 pytest：

```bash
./.venv/bin/python -m pytest -q -m "not data_required and not full_backtest"
```

- 如涉及完整数据或完整回测，我运行了：

```bash
./.venv/bin/python scripts/verify_combined_v2_rc.py --mode full
./.venv/bin/python -m pytest -q
```

## observation 说明

- 如果涉及 observation report，说明 `as_of_date`、`target_trading_date`、freshness、blocking_reason 和 data quality 状态。
- 如果涉及数据更新，说明 provider readiness、data quality、是否有降级数据源。
- 如果 data quality 为 WARN，说明 WARN 内容和人工复核要求。
- 如果 `as_of_date` 是非交易日，说明报告仅用于下一交易日人工复核，不是今日实盘执行。
