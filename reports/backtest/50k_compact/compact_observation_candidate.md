# 50k compact observation candidate

- candidate_variant: mp6_tr1_tu8_cr15_add0
- profile: combined_v2_50k_compact
- research_only: true
- frozen_for: paper_trading_observation_only
- neighborhood_robustness: FRAGILE
- auto_trading_approved: false
- broker_integration_enabled: false
- llm_decision_allowed: false

## selected metrics

- capital: 50000
- max_positions: 6
- max_tranches: 1
- target_universe_size: 8
- cash_reserve_ratio: 15.00%
- max_adds_per_day: 0
- annual_return: 7.31%
- cumulative_return: 22.55%
- max_drawdown: -10.62%
- max_exposure: 79.62%
- total_trades: 20
- executable_buy_count: 12
- strategy_eligible_count: 240
- account_actionable_buy_count: 12
- watch_only_count: 228
- executable_account_actionable_ratio: 100.00%

## why selected

- 适配 50k 资金规模
- 不超过 6 个持仓
- 单档建仓
- 15% 现金预留
- 不加仓，避免小账户现金被切碎
- 最大暴露低于 85%
- account actionable buy 基本可执行

## risks

- 样本交易少
- watch-only 很高
- 最大回撤比默认 50k combined_v2 更深
- 可能存在行业集中
- 回测成交假设仍需纸面观察验证

## observation conclusion

- 只能进入 paper trading / observation
- 不得自动实盘
- 不得替换 release 默认口径
- 不得视为 PASS

## daily monitoring metrics

- `generated_signal_count`
- `account_actionable_buy_count`
- `watch_only_count`
- `executable_buy_count`
- `top_watch_only_reasons`
- `current_positions_count`
- `current_exposure`
- `current_cash_ratio`
- `industry_concentration`
- `skipped_signal_reason`
- `actual_paper_fill_price`
- `paper_slippage_vs_next_open`
- `paper_slippage_vs_close`
- `manual_override_flag`
- `manual_override_reason`
