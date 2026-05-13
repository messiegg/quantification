# account constraints report

- status: WARN
- generated_at: 2026-05-07T04:28:23.470627+00:00
- git_commit: fcbad4f7fd70542596dcb7537dba4e7ea41a84c9
- config_hash: db870a6286086d458549fe9afee5f56eb0d42ffdeef9232ccebcd2bc346049fc

## runtime profile

- account_profile: tranche_5_10_15_max15
- initial_capital: 50000.0
- min_trade_value: 1500.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 6
- portfolio_equal_weight_target_positions: 6

## execution funnel

- raw_buy_signal_count: 849
- unique_raw_buy_intent_count: 190
- repeat_raw_buy_intent_count: 659
- repeat_raw_buy_intent_ratio: 0.7762073027090695
- repeated_blocked_buy_signal_count: 659
- account_feasible_buy_signal_count: 811
- user_visible_buy_recommendation_count: 24
- user_visible_blocked_buy_count: 166
- pending_buy_intent_count: 11
- raw_sell_signal_count: 17
- executable_buy_count: 24
- executable_sell_count: 17
- executable_raw_buy_ratio: 0.028268551236749116
- executable_unique_raw_intent_ratio: 0.12631578947368421
- executable_account_feasible_buy_ratio: 0.029593094944512947
- full_portfolio_raw_buy_intent_count: 785
- full_portfolio_raw_buy_intent_ratio: 0.9246171967020024
- new_position_raw_intent_count: 835
- add_position_raw_intent_count: 14
- executable_new_position_buy_count: 19
- executable_add_buy_count: 3
- average_cash_ratio: 0.6421
- average_exposure: 0.3678
- max_exposure: 0.4391
- turnover: 103824.42

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

- max_positions_block_count: 785
- max_positions_block_ratio: 0.9246171967020024
- price_too_high_for_account_lot_count: 19
- price_too_high_for_account_lot_ratio: 0.02237926972909305
- cash_insufficient_for_one_lot_count: 8
- cash_insufficient_for_one_lot_ratio: 0.009422850412249705
- lot_size_accumulation_required_count: 0
- lot_size_accumulation_required_ratio: 0.0
- cash_block_count: 0
- cash_block_ratio: 0.0 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_count: 8
- cash_liquidity_block_ratio: 0.009422850412249705 (cash + one-lot cash blockers)

## block reason breakdown

| reason_code | count | pct_raw | pct_blocked | unique_symbols | trade_dates | dominant_bucket | examples | description |
|---|---:|---:|---:|---:|---:|---|---|---|
| MAX_POSITIONS_LIMIT | 785 | 0.9246171967020024 | 0.9492140266021766 | 34 | 377 | defensive_dividend | 601866.sh,002032.sz,000651.sz,600018.sh,600999.sh,601211.sh,000333.sz,600803.sh,600926.sh,601336.sh | 组合已达到最大持仓数，新的买入意图被阻断。 |
| PRICE_TOO_HIGH_FOR_ACCOUNT_LOT | 19 | 0.02237926972909305 | 0.022974607013301087 | 2 | 16 | cyclical_rotation | 601021.sh,600309.sh | 按当前账户和单票上限，一手金额过高。 |
| PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY | 11 | 0.012956419316843345 | 0.013301088270858524 | 1 | 11 | defensive_dividend | 601318.sh | 剩余单票容量不足以容纳一手或目标加仓。 |
| CASH_INSUFFICIENT_FOR_ONE_LOT | 8 | 0.009422850412249705 | 0.009673518742442563 | 2 | 8 | defensive_dividend | 000333.sz,002032.sz | 当前可用现金不足以买入一手。 |
| DAILY_NEW_POSITION_LIMIT | 2 | 0.002355712603062426 | 0.0024183796856106408 | 2 | 2 | defensive_dividend | 601318.sh,601018.sh | 当日新开仓数量达到上限。 |
| LOT_SIZE_ZERO | 1 | 0.001177856301531213 | 0.0012091898428053204 | 1 | 1 | defensive_dividend | 000333.sz | 目标股数低于整手后为零。 |
| MIN_TRADE_AMOUNT | 1 | 0.001177856301531213 | 0.0012091898428053204 | 1 | 1 | cyclical_rotation | 601018.sh | 目标成交额低于最小成交额。 |

## blocker_counts

- CASH_INSUFFICIENT_FOR_ONE_LOT: 8
- DAILY_NEW_POSITION_LIMIT: 2
- LOT_SIZE_ZERO: 1
- MAX_POSITIONS_LIMIT: 785
- MIN_TRADE_AMOUNT: 1
- PRICE_TOO_HIGH_FOR_ACCOUNT_LOT: 19
- PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY: 11

## WARN

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.028268551236749116
