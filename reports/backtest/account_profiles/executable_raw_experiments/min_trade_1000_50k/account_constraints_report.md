# account constraints report

- status: WARN
- generated_at: 2026-05-07T04:05:43.332145+00:00
- git_commit: fcbad4f7fd70542596dcb7537dba4e7ea41a84c9
- config_hash: 13907f879bc7b066f1be6cfb012ad02f9a07ff4d282f3984731a3d56967d8e7d

## runtime profile

- account_profile: min_trade_1000_50k
- initial_capital: 50000.0
- min_trade_value: 1000.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 8
- portfolio_equal_weight_target_positions: 8

## execution funnel

- raw_buy_signal_count: 674
- unique_raw_buy_intent_count: 164
- repeat_raw_buy_intent_count: 510
- repeat_raw_buy_intent_ratio: 0.7566765578635015
- repeated_blocked_buy_signal_count: 510
- account_feasible_buy_signal_count: 482
- user_visible_buy_recommendation_count: 22
- user_visible_blocked_buy_count: 142
- pending_buy_intent_count: 34
- raw_sell_signal_count: 31
- executable_buy_count: 22
- executable_sell_count: 17
- executable_raw_buy_ratio: 0.032640949554896145
- executable_unique_raw_intent_ratio: 0.13414634146341464
- executable_account_feasible_buy_ratio: 0.04564315352697095
- full_portfolio_raw_buy_intent_count: 459
- full_portfolio_raw_buy_intent_ratio: 0.6810089020771514
- new_position_raw_intent_count: 637
- add_position_raw_intent_count: 37
- executable_new_position_buy_count: 19
- executable_add_buy_count: 3
- average_cash_ratio: 0.6160
- average_exposure: 0.4257
- max_exposure: 0.5552
- turnover: 84440.03

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

- max_positions_block_count: 459
- max_positions_block_ratio: 0.6810089020771514
- price_too_high_for_account_lot_count: 30
- price_too_high_for_account_lot_ratio: 0.04451038575667656
- cash_insufficient_for_one_lot_count: 151
- cash_insufficient_for_one_lot_ratio: 0.22403560830860533
- lot_size_accumulation_required_count: 0
- lot_size_accumulation_required_ratio: 0.0
- cash_block_count: 0
- cash_block_ratio: 0.0 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_count: 151
- cash_liquidity_block_ratio: 0.22403560830860533 (cash + one-lot cash blockers)

## block reason breakdown

| reason_code | count | pct_raw | pct_blocked | unique_symbols | trade_dates | dominant_bucket | examples | description |
|---|---:|---:|---:|---:|---:|---|---|---|
| MAX_POSITIONS_LIMIT | 459 | 0.6810089020771514 | 0.6891891891891891 | 27 | 226 | defensive_dividend | 000651.sz,600018.sh,600999.sh,601211.sh,000333.sz,600803.sh,600233.sh,601021.sh,000807.sz,600036.sh | 组合已达到最大持仓数，新的买入意图被阻断。 |
| CASH_INSUFFICIENT_FOR_ONE_LOT | 151 | 0.22403560830860533 | 0.22672672672672672 | 9 | 65 | defensive_dividend | 600585.sh,000333.sz,000651.sz,600926.sh,601336.sh,601601.sh,000932.sz,600018.sh,300628.sz | 当前可用现金不足以买入一手。 |
| PRICE_TOO_HIGH_FOR_ACCOUNT_LOT | 30 | 0.04451038575667656 | 0.04504504504504504 | 2 | 27 | cyclical_rotation | 601021.sh,600309.sh | 按当前账户和单票上限，一手金额过高。 |
| MIN_TRADE_AMOUNT | 14 | 0.020771513353115726 | 0.021021021021021023 | 1 | 14 | defensive_dividend | 601018.sh | 目标成交额低于最小成交额。 |
| PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY | 11 | 0.016320474777448073 | 0.016516516516516516 | 1 | 11 | defensive_dividend | 601318.sh | 剩余单票容量不足以容纳一手或目标加仓。 |
| DAILY_NEW_POSITION_LIMIT | 1 | 0.001483679525222552 | 0.0015015015015015015 | 1 | 1 | defensive_dividend | 601318.sh | 当日新开仓数量达到上限。 |

## blocker_counts

- CASH_INSUFFICIENT_FOR_ONE_LOT: 151
- DAILY_NEW_POSITION_LIMIT: 1
- MAX_POSITIONS_LIMIT: 459
- MIN_TRADE_AMOUNT: 14
- PRICE_TOO_HIGH_FOR_ACCOUNT_LOT: 30
- PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY: 11

## WARN

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.032640949554896145
