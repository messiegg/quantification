# account constraints report

- status: WARN
- generated_at: 2026-05-07T04:31:32.496147+00:00
- git_commit: fcbad4f7fd70542596dcb7537dba4e7ea41a84c9
- config_hash: aada232920c7afc7a6ceec16938c0246c9196e7d9bf5a900448b580f637d913d

## runtime profile

- account_profile: round_lot_1_upper_bound
- initial_capital: 50000.0
- min_trade_value: 1500.0
- round_lot: 1
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 8
- portfolio_equal_weight_target_positions: 8

## execution funnel

- raw_buy_signal_count: 541
- unique_raw_buy_intent_count: 288
- repeat_raw_buy_intent_count: 253
- repeat_raw_buy_intent_ratio: 0.4676524953789279
- repeated_blocked_buy_signal_count: 253
- account_feasible_buy_signal_count: 541
- user_visible_buy_recommendation_count: 34
- user_visible_blocked_buy_count: 254
- pending_buy_intent_count: 0
- raw_sell_signal_count: 78
- executable_buy_count: 34
- executable_sell_count: 24
- executable_raw_buy_ratio: 0.06284658040665435
- executable_unique_raw_intent_ratio: 0.11805555555555555
- executable_account_feasible_buy_ratio: 0.06284658040665435
- full_portfolio_raw_buy_intent_count: 506
- full_portfolio_raw_buy_intent_ratio: 0.9353049907578558
- new_position_raw_intent_count: 533
- add_position_raw_intent_count: 8
- executable_new_position_buy_count: 24
- executable_add_buy_count: 7
- average_cash_ratio: 0.6912
- average_exposure: 0.3211
- max_exposure: 0.4055
- turnover: 104530.10

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

- max_positions_block_count: 506
- max_positions_block_ratio: 0.9353049907578558
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
| MAX_POSITIONS_LIMIT | 506 | 0.9353049907578558 | 0.8971631205673759 | 29 | 225 | defensive_dividend | 000651.sz,600018.sh,600999.sh,601211.sh,000333.sz,600803.sh,600926.sh,601336.sh,601601.sh,300628.sz | 组合已达到最大持仓数，新的买入意图被阻断。 |
| MIN_TRADE_AMOUNT | 57 | 0.10536044362292052 | 0.10106382978723404 | 3 | 57 | defensive_dividend | 601018.sh,000333.sz,600989.sh | 目标成交额低于最小成交额。 |
| DAILY_NEW_POSITION_LIMIT | 1 | 0.0018484288354898336 | 0.0017730496453900709 | 1 | 1 | defensive_dividend | 601318.sh | 当日新开仓数量达到上限。 |

## blocker_counts

- DAILY_NEW_POSITION_LIMIT: 1
- MAX_POSITIONS_LIMIT: 506
- MIN_TRADE_AMOUNT: 57

## WARN

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.06284658040665435
