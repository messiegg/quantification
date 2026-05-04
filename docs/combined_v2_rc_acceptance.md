# combined_v2 RC acceptance

## 主口径

- profile: `combined_v2`
- execution_mode: `next_bar`
- period: `2023-04-03` 到 `2026-04-03`
- annual_return: `0.0713520247687258`
- cumulative_return: `0.2196444045310004`
- max_drawdown: `-0.0936454742991675`
- total_trades: `76`
- final_nav: `243928.8809062001`
- final rating: `PASS_CANDIDATE`

`PASS_CANDIDATE` 只表示“小资金、手动、继续观察候选”。它不是自动实盘批准，也不是券商接入批准。

## 验证方式

```bash
./.venv/bin/python scripts/verify_combined_v2_rc.py
./.venv/bin/python scripts/check_report_freshness.py
```

输出：

- `reports/backtest/release/combined_v2_rc_verify.csv`
- `reports/backtest/release/combined_v2_rc_verify.md`
- `reports/backtest/release/combined_v2_rc_code_manifest.json`
- `reports/backtest/audit/stale_report_check.csv`
- `reports/backtest/audit/stale_report_check.md`

配置 hash 漂移是 `FAIL`。核心策略代码 hash 漂移是 `WARN`，不会直接判定策略失效，但必须重跑完整审计。报告 hash 漂移而严格指标一致时也是 `WARN`，需要刷新报告或解释差异。

## 不得改变的边界

- 不修改 `combined_v2` 买入、卖出、网格、仓位、market regime、cycle_peak_trap、hard_add_ban、fundamental_break 逻辑。
- 不修改 `config/strategy_v2.yml` 与 `config/universe_rules_v2.yml` 的交易含义。
- 不接券商，不自动下单，不让 LLM 决定 `action_enum`。
- 不用 `2026-04-03` 之后的数据改写三年历史回测。
- `combined_v2_1_risk_guard` 只保留为 conservative observation candidate，不替换主策略。

## legacy 记录

`9.14% / 83` 笔属于 legacy pre-PIT 旧记录，只能作为 superseded 历史说明保留。当前主策略复现标准是 PIT `next_bar` 的 `7.1352% / 76` 笔。
