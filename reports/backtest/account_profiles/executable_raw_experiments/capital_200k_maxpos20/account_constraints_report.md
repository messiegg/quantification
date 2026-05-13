# account constraints report

- status: WARN
- generated_at: 2026-05-07T04:23:40.256190+00:00
- git_commit: fcbad4f7fd70542596dcb7537dba4e7ea41a84c9
- config_hash: eef37eadd12e4332818ddd7eec035f50834e159ac14db6a42d10124e09aba9db

## runtime profile

- account_profile: capital_200k_maxpos20
- initial_capital: 200000.0
- min_trade_value: 1500.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 20
- portfolio_equal_weight_target_positions: 20

## execution funnel

- raw_buy_signal_count: 264
- unique_raw_buy_intent_count: 112
- repeat_raw_buy_intent_count: 152
- repeat_raw_buy_intent_ratio: 0.5757575757575758
- repeated_blocked_buy_signal_count: 152
- account_feasible_buy_signal_count: 79
- user_visible_buy_recommendation_count: 50
- user_visible_blocked_buy_count: 62
- pending_buy_intent_count: 24
- raw_sell_signal_count: 32
- executable_buy_count: 50
- executable_sell_count: 32
- executable_raw_buy_ratio: 0.1893939393939394
- executable_unique_raw_intent_ratio: 0.44642857142857145
- executable_account_feasible_buy_ratio: 0.6329113924050633
- full_portfolio_raw_buy_intent_count: 29
- full_portfolio_raw_buy_intent_ratio: 0.10984848484848485
- new_position_raw_intent_count: 229
- add_position_raw_intent_count: 35
- executable_new_position_buy_count: 39
- executable_add_buy_count: 8
- average_cash_ratio: 0.5555
- average_exposure: 0.4671
- max_exposure: 0.6831
- turnover: 545264.32

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

- max_positions_block_count: 29
- max_positions_block_ratio: 0.10984848484848485
- price_too_high_for_account_lot_count: 0
- price_too_high_for_account_lot_ratio: 0.0
- cash_insufficient_for_one_lot_count: 173
- cash_insufficient_for_one_lot_ratio: 0.6553030303030303
- lot_size_accumulation_required_count: 0
- lot_size_accumulation_required_ratio: 0.0
- cash_block_count: 12
- cash_block_ratio: 0.045454545454545456 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_count: 185
- cash_liquidity_block_ratio: 0.7007575757575758 (cash + one-lot cash blockers)

## block reason breakdown

| reason_code | count | pct_raw | pct_blocked | unique_symbols | trade_dates | dominant_bucket | examples | description |
|---|---:|---:|---:|---:|---:|---|---|---|
| CASH_INSUFFICIENT_FOR_ONE_LOT | 173 | 0.6553030303030303 | 0.7972350230414746 | 15 | 56 | defensive_dividend | 600585.sh,600926.sh,601336.sh,601601.sh,601318.sh,000333.sz,000807.sz,600233.sh,300628.sz,600036.sh | 当前可用现金不足以买入一手。 |
| MAX_POSITIONS_LIMIT | 29 | 0.10984848484848485 | 0.1336405529953917 | 5 | 23 | defensive_dividend | 000708.sz,600426.sh,601688.sh,601601.sh,601021.sh | 组合已达到最大持仓数，新的买入意图被阻断。 |
| CASH_INSUFFICIENT | 12 | 0.045454545454545456 | 0.055299539170506916 | 5 | 7 | cyclical_rotation | 601018.sh,000807.sz,600346.sh,600926.sh,601838.sh | 现金不足以满足目标订单金额。 |
| LOT_SIZE_ZERO | 2 | 0.007575757575757576 | 0.009216589861751152 | 2 | 2 | defensive_dividend | 000333.sz,600233.sh | 目标股数低于整手后为零。 |
| TOTAL_EXPOSURE_LIMIT | 1 | 0.003787878787878788 | 0.004608294930875576 | 1 | 1 | defensive_dividend | 601318.sh | 未知或未归类阻断原因。 |

## blocker_counts

- CASH_INSUFFICIENT: 12
- CASH_INSUFFICIENT_FOR_ONE_LOT: 173
- LOT_SIZE_ZERO: 2
- MAX_POSITIONS_LIMIT: 29
- TOTAL_EXPOSURE_LIMIT: 1

## WARN

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.1893939393939394
