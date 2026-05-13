# account constraints report

- status: WARN
- generated_at: 2026-05-07T04:14:12.023324+00:00
- git_commit: fcbad4f7fd70542596dcb7537dba4e7ea41a84c9
- config_hash: 1c8bcd4180e9af0f3c736fc541c34d938bc462def0e7a10dd56ee22f712654aa

## runtime profile

- account_profile: capital_200k_lot_aware
- initial_capital: 200000.0
- min_trade_value: 1500.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 8
- portfolio_equal_weight_target_positions: 8

## execution funnel

- raw_buy_signal_count: 538
- unique_raw_buy_intent_count: 158
- repeat_raw_buy_intent_count: 380
- repeat_raw_buy_intent_ratio: 0.7063197026022305
- repeated_blocked_buy_signal_count: 380
- account_feasible_buy_signal_count: 538
- user_visible_buy_recommendation_count: 31
- user_visible_blocked_buy_count: 127
- pending_buy_intent_count: 0
- raw_sell_signal_count: 24
- executable_buy_count: 31
- executable_sell_count: 24
- executable_raw_buy_ratio: 0.05762081784386617
- executable_unique_raw_intent_ratio: 0.1962025316455696
- executable_account_feasible_buy_ratio: 0.05762081784386617
- full_portfolio_raw_buy_intent_count: 506
- full_portfolio_raw_buy_intent_ratio: 0.9405204460966543
- new_position_raw_intent_count: 531
- add_position_raw_intent_count: 7
- executable_new_position_buy_count: 24
- executable_add_buy_count: 7
- average_cash_ratio: 0.7384
- average_exposure: 0.2692
- max_exposure: 0.3653
- turnover: 367578.08

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
- max_positions_block_ratio: 0.9405204460966543
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
| MAX_POSITIONS_LIMIT | 506 | 0.9405204460966543 | 0.9980276134122288 | 29 | 225 | defensive_dividend | 000651.sz,600018.sh,600999.sh,601211.sh,000333.sz,600803.sh,600926.sh,601336.sh,601601.sh,300628.sz | 组合已达到最大持仓数，新的买入意图被阻断。 |
| DAILY_NEW_POSITION_LIMIT | 1 | 0.0018587360594795538 | 0.0019723865877712033 | 1 | 1 | defensive_dividend | 601318.sh | 当日新开仓数量达到上限。 |

## blocker_counts

- DAILY_NEW_POSITION_LIMIT: 1
- MAX_POSITIONS_LIMIT: 506

## WARN

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.05762081784386617
