# account constraints report

- status: WARN
- generated_at: 2026-05-07T04:10:22.256593+00:00
- git_commit: fcbad4f7fd70542596dcb7537dba4e7ea41a84c9
- config_hash: 68f8e835ff7caf6074d4c7f64858b1d52032f7e01ff3c3ac70aeae4f9980fab2

## runtime profile

- account_profile: capital_100k_lot_aware
- initial_capital: 100000.0
- min_trade_value: 1500.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 8
- portfolio_equal_weight_target_positions: 8

## execution funnel

- raw_buy_signal_count: 555
- unique_raw_buy_intent_count: 152
- repeat_raw_buy_intent_count: 403
- repeat_raw_buy_intent_ratio: 0.7261261261261261
- repeated_blocked_buy_signal_count: 403
- account_feasible_buy_signal_count: 531
- user_visible_buy_recommendation_count: 28
- user_visible_blocked_buy_count: 124
- pending_buy_intent_count: 24
- raw_sell_signal_count: 22
- executable_buy_count: 28
- executable_sell_count: 22
- executable_raw_buy_ratio: 0.05045045045045045
- executable_unique_raw_intent_ratio: 0.18421052631578946
- executable_account_feasible_buy_ratio: 0.05273069679849341
- full_portfolio_raw_buy_intent_count: 502
- full_portfolio_raw_buy_intent_ratio: 0.9045045045045045
- new_position_raw_intent_count: 527
- add_position_raw_intent_count: 28
- executable_new_position_buy_count: 24
- executable_add_buy_count: 4
- average_cash_ratio: 0.7000
- average_exposure: 0.3072
- max_exposure: 0.3996
- turnover: 169020.05

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

- max_positions_block_count: 502
- max_positions_block_ratio: 0.9045045045045045
- price_too_high_for_account_lot_count: 0
- price_too_high_for_account_lot_ratio: 0.0
- cash_insufficient_for_one_lot_count: 0
- cash_insufficient_for_one_lot_ratio: 0.0
- lot_size_accumulation_required_count: 20
- lot_size_accumulation_required_ratio: 0.036036036036036036
- cash_block_count: 0
- cash_block_ratio: 0.0 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_count: 0
- cash_liquidity_block_ratio: 0.0 (cash + one-lot cash blockers)

## block reason breakdown

| reason_code | count | pct_raw | pct_blocked | unique_symbols | trade_dates | dominant_bucket | examples | description |
|---|---:|---:|---:|---:|---:|---|---|---|
| MAX_POSITIONS_LIMIT | 502 | 0.9045045045045045 | 0.952561669829222 | 29 | 225 | defensive_dividend | 000651.sz,600018.sh,600999.sh,601211.sh,000333.sz,600803.sh,600926.sh,601336.sh,601601.sh,300628.sz | 组合已达到最大持仓数，新的买入意图被阻断。 |
| LOT_SIZE_ACCUMULATION_REQUIRED | 20 | 0.036036036036036036 | 0.03795066413662239 | 3 | 20 | defensive_dividend | 601318.sh,000333.sz,002032.sz | 加仓目标差额、现金或剩余单票容量尚未满足一手。 |
| PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY | 4 | 0.007207207207207207 | 0.007590132827324478 | 1 | 4 | cyclical_rotation | 601021.sh | 剩余单票容量不足以容纳一手或目标加仓。 |
| DAILY_NEW_POSITION_LIMIT | 1 | 0.0018018018018018018 | 0.0018975332068311196 | 1 | 1 | defensive_dividend | 601318.sh | 当日新开仓数量达到上限。 |

## blocker_counts

- DAILY_NEW_POSITION_LIMIT: 1
- LOT_SIZE_ACCUMULATION_REQUIRED: 20
- MAX_POSITIONS_LIMIT: 502
- PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY: 4

## WARN

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.05045045045045045
