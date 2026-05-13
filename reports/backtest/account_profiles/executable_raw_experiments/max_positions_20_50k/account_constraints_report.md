# account constraints report

- status: WARN
- generated_at: 2026-05-07T04:21:10.240111+00:00
- git_commit: fcbad4f7fd70542596dcb7537dba4e7ea41a84c9
- config_hash: 3730b833f6bd91c6784283a425e4c25fcaf8d35da5991fcd7f1f2107e65e22f9

## runtime profile

- account_profile: max_positions_20_50k
- initial_capital: 50000.0
- min_trade_value: 1500.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 20
- portfolio_equal_weight_target_positions: 20

## execution funnel

- raw_buy_signal_count: 371
- unique_raw_buy_intent_count: 116
- repeat_raw_buy_intent_count: 255
- repeat_raw_buy_intent_ratio: 0.6873315363881402
- repeated_blocked_buy_signal_count: 255
- account_feasible_buy_signal_count: 43
- user_visible_buy_recommendation_count: 38
- user_visible_blocked_buy_count: 78
- pending_buy_intent_count: 35
- raw_sell_signal_count: 28
- executable_buy_count: 38
- executable_sell_count: 28
- executable_raw_buy_ratio: 0.10242587601078167
- executable_unique_raw_intent_ratio: 0.3275862068965517
- executable_account_feasible_buy_ratio: 0.8837209302325582
- full_portfolio_raw_buy_intent_count: 0
- full_portfolio_raw_buy_intent_ratio: 0.0
- new_position_raw_intent_count: 333
- add_position_raw_intent_count: 38
- executable_new_position_buy_count: 35
- executable_add_buy_count: 3
- average_cash_ratio: 0.3906
- average_exposure: 0.6227
- max_exposure: 0.9476
- turnover: 167801.43

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
- price_too_high_for_account_lot_count: 51
- price_too_high_for_account_lot_ratio: 0.13746630727762804
- cash_insufficient_for_one_lot_count: 243
- cash_insufficient_for_one_lot_ratio: 0.6549865229110512
- lot_size_accumulation_required_count: 8
- lot_size_accumulation_required_ratio: 0.0215633423180593
- cash_block_count: 0
- cash_block_ratio: 0.0 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_count: 243
- cash_liquidity_block_ratio: 0.6549865229110512 (cash + one-lot cash blockers)

## block reason breakdown

| reason_code | count | pct_raw | pct_blocked | unique_symbols | trade_dates | dominant_bucket | examples | description |
|---|---:|---:|---:|---:|---:|---|---|---|
| CASH_INSUFFICIENT_FOR_ONE_LOT | 243 | 0.6549865229110512 | 0.7297297297297297 | 17 | 100 | defensive_dividend | 000333.sz,600585.sh,600926.sh,601336.sh,601601.sh,601018.sh,000807.sz,300628.sz,600036.sh,600690.sh | 当前可用现金不足以买入一手。 |
| PRICE_TOO_HIGH_FOR_ACCOUNT_LOT | 51 | 0.13746630727762804 | 0.15315315315315314 | 3 | 48 | cyclical_rotation | 601021.sh,600309.sh,000333.sz | 按当前账户和单票上限，一手金额过高。 |
| PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY | 26 | 0.07008086253369272 | 0.07807807807807808 | 3 | 25 | defensive_dividend | 601318.sh,600233.sh,300628.sz | 剩余单票容量不足以容纳一手或目标加仓。 |
| LOT_SIZE_ACCUMULATION_REQUIRED | 8 | 0.0215633423180593 | 0.024024024024024024 | 1 | 8 | cyclical_rotation | 600018.sh | 加仓目标差额、现金或剩余单票容量尚未满足一手。 |
| DAILY_NEW_POSITION_LIMIT | 5 | 0.013477088948787063 | 0.015015015015015015 | 5 | 4 | defensive_dividend | 601318.sh,600999.sh,601021.sh,600036.sh,601838.sh | 当日新开仓数量达到上限。 |

## blocker_counts

- CASH_INSUFFICIENT_FOR_ONE_LOT: 243
- DAILY_NEW_POSITION_LIMIT: 5
- LOT_SIZE_ACCUMULATION_REQUIRED: 8
- PRICE_TOO_HIGH_FOR_ACCOUNT_LOT: 51
- PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY: 26

## WARN

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.10242587601078167
