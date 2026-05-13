# account constraints report

- status: WARN
- generated_at: 2026-05-07T07:21:12.924176+00:00
- git_commit: fcbad4f7fd70542596dcb7537dba4e7ea41a84c9
- config_hash: 834ddfbe25f70220cbe613782bc24cabcc3ddd6159f37aa4fd5bd8848f14aaa3

## runtime profile

- account_profile: retail_50k
- initial_capital: 50000.0
- min_trade_value: 1500.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 12
- portfolio_equal_weight_target_positions: 12

## execution funnel

- raw_buy_signal_count: 1145
- unique_raw_buy_intent_count: 1145
- repeat_raw_buy_intent_count: 0
- repeat_raw_buy_intent_ratio: 0.0
- repeated_blocked_buy_signal_count: 0
- account_feasible_buy_signal_count: 12
- user_visible_buy_recommendation_count: 12
- user_visible_blocked_buy_count: 1133
- pending_buy_intent_count: 0
- raw_sell_signal_count: 9
- executable_buy_count: 12
- executable_sell_count: 9
- executable_raw_buy_ratio: 0.010480349344978166
- executable_unique_raw_intent_ratio: 0.010480349344978166
- executable_account_feasible_buy_ratio: 1.0
- full_portfolio_raw_buy_intent_count: 0
- full_portfolio_raw_buy_intent_ratio: 0.0
- new_position_raw_intent_count: 1111
- add_position_raw_intent_count: 34
- executable_new_position_buy_count: 12
- executable_add_buy_count: 0
- average_cash_ratio: 0.8638
- average_exposure: 0.1485
- max_exposure: 0.2630
- turnover: 40135.57

## denominator notes

- executable_raw_buy_ratio: executable_buy_count / raw_buy_signal_count
- executable_unique_raw_intent_ratio: executable_buy_count / unique_raw_buy_intent_count
- executable_account_feasible_buy_ratio: executable_buy_count / account_feasible_buy_signal_count
- repeat_raw_buy_intent_ratio: repeat_raw_buy_intent_count / raw_buy_signal_count
- full_portfolio_raw_buy_intent_ratio: full_portfolio_raw_buy_intent_count / raw_buy_signal_count
- max_positions_block_ratio: max_positions_block_count / raw_buy_signal_count
- cash_block_ratio: cash_block_count / raw_buy_signal_count; excludes CASH_INSUFFICIENT_FOR_ONE_LOT
- cash_liquidity_block_ratio: (cash_block_count + cash_insufficient_for_one_lot_count) / raw_buy_signal_count
- block_reason_breakdown.count_pct_of_raw: reason_code count / raw_buy_signal_count
- block_reason_breakdown.count_pct_of_blocked: reason_code count / total blocked_signals rows

## blocker ratios

- max_positions_block_count: 0
- max_positions_block_ratio: 0.0
- price_too_high_for_account_lot_count: 0
- price_too_high_for_account_lot_ratio: 0.0
- cash_insufficient_for_one_lot_count: 0
- cash_insufficient_for_one_lot_ratio: 0.0
- lot_size_accumulation_required_count: 0
- lot_size_accumulation_required_ratio: 0.0
- cash_block_count: 0
- cash_block_ratio: 0.0 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_count: 0
- cash_liquidity_block_ratio: 0.0 (cash + one-lot cash blockers)

## block reason breakdown

| reason_code | count | pct_raw | pct_blocked | unique_symbols | trade_dates | dominant_bucket | examples | description |
|---|---:|---:|---:|---:|---:|---|---|---|
| LOT_SIZE_ZERO | 783 | 0.6838427947598253 | 0.6910856134157105 | 19 | 439 | defensive_dividend | 600036.sh,601318.sh,002032.sz,000651.sz,000333.sz,600585.sh,601336.sh,601601.sh,601021.sh,600309.sh | 目标股数低于整手后为零。 |
| MIN_TRADE_AMOUNT | 350 | 0.3056768558951965 | 0.3089143865842895 | 18 | 239 | cyclical_rotation | 000877.sz,601166.sh,600346.sh,600999.sh,601211.sh,601018.sh,000932.sz,600018.sh,600989.sh,600233.sh | 目标成交额低于最小成交额。 |

## blocker_counts

- LOT_SIZE_ZERO: 783
- MIN_TRADE_AMOUNT: 350

## WARN

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.010480349344978166
