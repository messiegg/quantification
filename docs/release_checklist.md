# combined_v2 发布检查清单

本清单用于 `combined_v2` RC 观察期发布前确认。它不授权自动交易，也不改变策略规则。

## 必须确认

1. 确认没有修改 `combined_v2` 交易规则、买入卖出阈值、仓位、网格、market regime、cycle_peak_trap、hard_add_ban 或 fundamental_break。
2. 确认 `reports/backtest/release/combined_v2_rc_manifest.json` 中的配置 hash 仍与 `config/strategy_v2.yml`、`config/universe_rules_v2.yml` 一致。
3. 运行 release guard：

```bash
./.venv/bin/python scripts/run_release_guard.py --ci --as-of-date 2026-05-04 --write-report
```

4. 运行轻量 pytest：

```bash
./.venv/bin/python -m pytest -q -m "not data_required and not full_backtest"
```

5. 本地完整数据环境需要运行 full-data 验证：

```bash
./.venv/bin/python scripts/verify_combined_v2_rc.py --mode full
./.venv/bin/python -m pytest -q
```

6. 如果更新了数据，确认未提交大体量行情数据、parquet、sqlite、duckdb、cache 或 `data/features/**`、`data/raw/**`。
7. 如果生成 observation report，确认当前主路径不存在 allowed 和 blocked 报告并存。
8. 确认公开报告不含 `/Users`、`/private` 等本地绝对路径。
9. 确认公开报告和配置不含 provider token、password、secret、券商账号或真实账户信息。
10. 确认 `combined_v2_manual_order_list.csv` 未被 Git 跟踪。
11. 确认不能自动下单、没有券商 API、没有真实订单执行能力。
12. 确认真实 paper ledger 仍为 ignored local artifact。
13. 确认 GitHub Actions PASS。

## 通过标准

- release guard 没有 FAIL；严格发布时 `--strict` 下也不能有 WARN。
- `combined_v2 next_bar` 指标保持：
  - annual_return = `0.0713520247687258`
  - cumulative_return = `0.2196444045310004`
  - max_drawdown = `-0.0936454742991675`
  - total_trades = `76`
  - final_nav = `243928.8809062001`
- observation 报告只能作为下一交易日人工复核材料，不能写成“今日实盘执行”。
