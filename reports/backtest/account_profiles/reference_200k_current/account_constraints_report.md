# account constraints report

- status: WARN
- generated_at: 2026-05-07T07:15:14.827908+00:00
- git_commit: fcbad4f7fd70542596dcb7537dba4e7ea41a84c9
- config_hash: ed82d7ec91fd9bc96eccdc5c74dff68ecd5b2ae6d1744ea4dd0e0c03c4ad8c3b

## runtime profile

- account_profile: reference_200k_current
- initial_capital: 200000.0
- min_trade_value: 5000.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 20
- portfolio_equal_weight_target_positions: 36

## execution funnel

- raw_buy_signal_count: 370
- unique_raw_buy_intent_count: 370
- repeat_raw_buy_intent_count: 0
- repeat_raw_buy_intent_ratio: 0.0
- repeated_blocked_buy_signal_count: 0
- account_feasible_buy_signal_count: 116
- user_visible_buy_recommendation_count: 43
- user_visible_blocked_buy_count: 327
- pending_buy_intent_count: 0
- raw_sell_signal_count: 91
- executable_buy_count: 43
- executable_sell_count: 33
- executable_raw_buy_ratio: 0.11621621621621622
- executable_unique_raw_intent_ratio: 0.11621621621621622
- executable_account_feasible_buy_ratio: 0.3706896551724138
- full_portfolio_raw_buy_intent_count: 5
- full_portfolio_raw_buy_intent_ratio: 0.013513513513513514
- new_position_raw_intent_count: 300
- add_position_raw_intent_count: 70
- executable_new_position_buy_count: 39
- executable_add_buy_count: 4
- average_cash_ratio: 0.5561
- average_exposure: 0.4694
- max_exposure: 0.7569
- turnover: 555248.63

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

- max_positions_block_count: 5
- max_positions_block_ratio: 0.013513513513513514
- price_too_high_for_account_lot_count: 0
- price_too_high_for_account_lot_ratio: 0.0
- cash_insufficient_for_one_lot_count: 0
- cash_insufficient_for_one_lot_ratio: 0.0
- lot_size_accumulation_required_count: 0
- lot_size_accumulation_required_ratio: 0.0
- cash_block_count: 88
- cash_block_ratio: 0.23783783783783785 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_count: 88
- cash_liquidity_block_ratio: 0.23783783783783785 (cash + one-lot cash blockers)

## block reason breakdown

| reason_code | count | pct_raw | pct_blocked | unique_symbols | trade_dates | dominant_bucket | examples | description |
|---|---:|---:|---:|---:|---:|---|---|---|
| MIN_TRADE_AMOUNT | 220 | 0.5945945945945946 | 0.5714285714285714 | 9 | 196 | defensive_dividend | 002032.sz,000333.sz,600585.sh,601318.sh,600018.sh,600989.sh,600233.sh,002352.sz,601018.sh | 目标成交额低于最小成交额。 |
| CASH_INSUFFICIENT | 88 | 0.23783783783783785 | 0.22857142857142856 | 11 | 24 | defensive_dividend | 601601.sh,601336.sh,000807.sz,300628.sz,600036.sh,600690.sh,600803.sh,601838.sh,000333.sz,600346.sh | 现金不足以满足目标订单金额。 |
| TOTAL_EXPOSURE_LIMIT | 68 | 0.1837837837837838 | 0.17662337662337663 | 13 | 39 | defensive_dividend | 600585.sh,600926.sh,601336.sh,601601.sh,601018.sh,000807.sz,600036.sh,600690.sh,600803.sh,601838.sh | 未知或未归类阻断原因。 |
| MAX_POSITIONS_LIMIT | 5 | 0.013513513513513514 | 0.012987012987012988 | 1 | 5 | cyclical_rotation | 601021.sh | 组合已达到最大持仓数，新的买入意图被阻断。 |
| LOT_SIZE_ZERO | 4 | 0.010810810810810811 | 0.01038961038961039 | 1 | 4 | cyclical_rotation | 600309.sh | 目标股数低于整手后为零。 |

## blocker_counts

- CASH_INSUFFICIENT: 88
- LOT_SIZE_ZERO: 4
- MAX_POSITIONS_LIMIT: 5
- MIN_TRADE_AMOUNT: 220
- TOTAL_EXPOSURE_LIMIT: 68

## WARN

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.11621621621621622
- MIN_TRADE_AMOUNT_DOMINATES_EXECUTION: min_trade_amount dominates execution actual=0.5945945945945946
