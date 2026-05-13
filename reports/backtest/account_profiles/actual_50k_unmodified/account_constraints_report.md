# account constraints report

- status: WARN
- generated_at: 2026-05-07T07:18:11.513659+00:00
- git_commit: fcbad4f7fd70542596dcb7537dba4e7ea41a84c9
- config_hash: f72a129071ed52358b2fc2f7ccd51f2f9c1ed8dc237ce8f9a3d1546f40cfdc65

## runtime profile

- account_profile: actual_50k_unmodified
- initial_capital: 50000.0
- min_trade_value: 5000.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 20
- portfolio_equal_weight_target_positions: 36

## execution funnel

- raw_buy_signal_count: 1300
- unique_raw_buy_intent_count: 1300
- repeat_raw_buy_intent_count: 0
- repeat_raw_buy_intent_ratio: 0.0
- repeated_blocked_buy_signal_count: 0
- account_feasible_buy_signal_count: 0
- user_visible_buy_recommendation_count: 0
- user_visible_blocked_buy_count: 1300
- pending_buy_intent_count: 0
- raw_sell_signal_count: 0
- executable_buy_count: 0
- executable_sell_count: 0
- executable_raw_buy_ratio: 0.0
- executable_unique_raw_intent_ratio: 0.0
- executable_account_feasible_buy_ratio: None
- full_portfolio_raw_buy_intent_count: 0
- full_portfolio_raw_buy_intent_ratio: 0.0
- new_position_raw_intent_count: 1300
- add_position_raw_intent_count: 0
- executable_new_position_buy_count: 0
- executable_add_buy_count: 0
- average_cash_ratio: 1.0000
- average_exposure: 0.0000
- max_exposure: 0.0000
- turnover: 0.00

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
| LOT_SIZE_ZERO | 783 | 0.6023076923076923 | 0.6023076923076923 | 19 | 439 | defensive_dividend | 600036.sh,601318.sh,002032.sz,000651.sz,000333.sz,600585.sh,601336.sh,601601.sh,601021.sh,600309.sh | 目标股数低于整手后为零。 |
| MIN_TRADE_AMOUNT | 517 | 0.3976923076923077 | 0.3976923076923077 | 24 | 333 | defensive_dividend | 600000.sh,000877.sz,601166.sh,600346.sh,601866.sh,600018.sh,600999.sh,601211.sh,600803.sh,600926.sh | 目标成交额低于最小成交额。 |

## blocker_counts

- LOT_SIZE_ZERO: 783
- MIN_TRADE_AMOUNT: 517

## WARN

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.0
