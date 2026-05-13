# account constraints report

- status: WARN
- generated_at: 2026-05-08T00:48:20.045981+00:00
- git_commit: fcbad4f7fd70542596dcb7537dba4e7ea41a84c9
- config_hash: 7494b4c011c8b7642354c3401f1bdc689890ae042665484e147a2ba86ef918d5

## runtime profile

- account_profile: capital_500k_maxpos20
- initial_capital: 500000.0
- min_trade_value: 1500.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 20
- portfolio_equal_weight_target_positions: 20

## execution funnel

- raw_buy_signal_count: 268
- unique_raw_buy_intent_count: 114
- repeat_raw_buy_intent_count: 154
- repeat_raw_buy_intent_ratio: 0.5746268656716418
- repeated_blocked_buy_signal_count: 154
- account_feasible_buy_signal_count: 63
- user_visible_buy_recommendation_count: 46
- user_visible_blocked_buy_count: 68
- pending_buy_intent_count: 41
- raw_sell_signal_count: 33
- executable_buy_count: 46
- executable_sell_count: 33
- executable_raw_buy_ratio: 0.17164179104477612
- executable_unique_raw_intent_ratio: 0.40350877192982454
- executable_account_feasible_buy_ratio: 0.7301587301587301
- full_portfolio_raw_buy_intent_count: 17
- full_portfolio_raw_buy_intent_ratio: 0.06343283582089553
- new_position_raw_intent_count: 220
- add_position_raw_intent_count: 48
- executable_new_position_buy_count: 39
- executable_add_buy_count: 6
- average_cash_ratio: 0.5190
- average_exposure: 0.5052
- max_exposure: 0.7464
- turnover: 1434475.68

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

- max_positions_block_count: 17
- max_positions_block_ratio: 0.06343283582089553
- price_too_high_for_account_lot_count: 0
- price_too_high_for_account_lot_ratio: 0.0
- cash_insufficient_for_one_lot_count: 202
- cash_insufficient_for_one_lot_ratio: 0.753731343283582
- lot_size_accumulation_required_count: 0
- lot_size_accumulation_required_ratio: 0.0
- cash_block_count: 3
- cash_block_ratio: 0.011194029850746268 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_count: 205
- cash_liquidity_block_ratio: 0.7649253731343284 (cash + one-lot cash blockers)

## block reason breakdown

| reason_code | count | pct_raw | pct_blocked | unique_symbols | trade_dates | dominant_bucket | examples | description |
|---|---:|---:|---:|---:|---:|---|---|---|
| CASH_INSUFFICIENT_FOR_ONE_LOT | 202 | 0.753731343283582 | 0.905829596412556 | 16 | 61 | defensive_dividend | 600585.sh,600926.sh,601336.sh,601601.sh,601318.sh,000333.sz,601018.sh,000807.sz,600233.sh,300628.sz | 当前可用现金不足以买入一手。 |
| MAX_POSITIONS_LIMIT | 17 | 0.06343283582089553 | 0.07623318385650224 | 6 | 12 | cyclical_rotation | 600585.sh,000708.sz,600426.sh,601688.sh,601601.sh,601021.sh | 组合已达到最大持仓数，新的买入意图被阻断。 |
| CASH_INSUFFICIENT | 3 | 0.011194029850746268 | 0.013452914798206279 | 3 | 2 | cyclical_rotation | 601018.sh,000708.sz,601688.sh | 现金不足以满足目标订单金额。 |
| TOTAL_EXPOSURE_LIMIT | 1 | 0.0037313432835820895 | 0.004484304932735426 | 1 | 1 | defensive_dividend | 000333.sz | 未知或未归类阻断原因。 |

## blocker_counts

- CASH_INSUFFICIENT: 3
- CASH_INSUFFICIENT_FOR_ONE_LOT: 202
- MAX_POSITIONS_LIMIT: 17
- TOTAL_EXPOSURE_LIMIT: 1

## WARN

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.17164179104477612
