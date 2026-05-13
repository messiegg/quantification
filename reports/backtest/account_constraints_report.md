# account constraints report

- status: WARN
- generated_at: 2026-05-08T01:30:46.083755+00:00
- git_commit: fcbad4f7fd70542596dcb7537dba4e7ea41a84c9
- config_hash: 6817ac43cf178fea81d0976750c1269eba0c1b2f4a2e0e6c4f4e7c1f16eaf1d5

## runtime profile

- account_profile: retail_50k_lot_aware
- initial_capital: 50000.0
- min_trade_value: 1500.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 8
- portfolio_equal_weight_target_positions: 8

## execution funnel

- raw_buy_signal_count: 629
- unique_raw_buy_intent_count: 159
- repeat_raw_buy_intent_count: 470
- repeat_raw_buy_intent_ratio: 0.7472178060413355
- repeated_blocked_buy_signal_count: 470
- account_feasible_buy_signal_count: 426
- user_visible_buy_recommendation_count: 23
- user_visible_blocked_buy_count: 136
- pending_buy_intent_count: 47
- raw_sell_signal_count: 18
- executable_buy_count: 23
- executable_sell_count: 18
- executable_raw_buy_ratio: 0.03656597774244833
- executable_unique_raw_intent_ratio: 0.14465408805031446
- executable_account_feasible_buy_ratio: 0.0539906103286385
- full_portfolio_raw_buy_intent_count: 402
- full_portfolio_raw_buy_intent_ratio: 0.6391096979332274
- new_position_raw_intent_count: 579
- add_position_raw_intent_count: 50
- executable_new_position_buy_count: 20
- executable_add_buy_count: 3
- average_cash_ratio: 0.5757
- average_exposure: 0.4454
- max_exposure: 0.5501
- turnover: 102109.96

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

- max_positions_block_count: 402
- max_positions_block_ratio: 0.6391096979332274
- price_too_high_for_account_lot_count: 30
- price_too_high_for_account_lot_ratio: 0.04769475357710652
- cash_insufficient_for_one_lot_count: 139
- cash_insufficient_for_one_lot_ratio: 0.22098569157392686
- lot_size_accumulation_required_count: 18
- lot_size_accumulation_required_ratio: 0.028616852146263912
- cash_block_count: 0
- cash_block_ratio: 0.0 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_count: 139
- cash_liquidity_block_ratio: 0.22098569157392686 (cash + one-lot cash blockers)

## block reason breakdown

| reason_code | count | pct_raw | pct_blocked | unique_symbols | trade_dates | dominant_bucket | examples | description |
|---|---:|---:|---:|---:|---:|---|---|---|
| MAX_POSITIONS_LIMIT | 402 | 0.6391096979332274 | 0.6633663366336634 | 26 | 183 | defensive_dividend | 000651.sz,600018.sh,600999.sh,601211.sh,000333.sz,600803.sh,601021.sh,000807.sz,600036.sh,600690.sh | 组合已达到最大持仓数，新的买入意图被阻断。 |
| CASH_INSUFFICIENT_FOR_ONE_LOT | 139 | 0.22098569157392686 | 0.22937293729372937 | 10 | 59 | defensive_dividend | 600585.sh,000333.sz,000651.sz,600926.sh,601336.sh,601601.sh,601018.sh,600018.sh,600233.sh,300628.sz | 当前可用现金不足以买入一手。 |
| PRICE_TOO_HIGH_FOR_ACCOUNT_LOT | 30 | 0.04769475357710652 | 0.04950495049504951 | 2 | 27 | cyclical_rotation | 601021.sh,600309.sh | 按当前账户和单票上限，一手金额过高。 |
| LOT_SIZE_ACCUMULATION_REQUIRED | 18 | 0.028616852146263912 | 0.0297029702970297 | 1 | 18 | cyclical_rotation | 600018.sh | 加仓目标差额、现金或剩余单票容量尚未满足一手。 |
| PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY | 16 | 0.025437201907790145 | 0.026402640264026403 | 2 | 16 | defensive_dividend | 601318.sh,600233.sh | 剩余单票容量不足以容纳一手或目标加仓。 |
| DAILY_NEW_POSITION_LIMIT | 1 | 0.001589825119236884 | 0.0016501650165016502 | 1 | 1 | defensive_dividend | 601318.sh | 当日新开仓数量达到上限。 |

## blocker_counts

- CASH_INSUFFICIENT_FOR_ONE_LOT: 139
- DAILY_NEW_POSITION_LIMIT: 1
- LOT_SIZE_ACCUMULATION_REQUIRED: 18
- MAX_POSITIONS_LIMIT: 402
- PRICE_TOO_HIGH_FOR_ACCOUNT_LOT: 30
- PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY: 16

## WARN

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.03656597774244833
