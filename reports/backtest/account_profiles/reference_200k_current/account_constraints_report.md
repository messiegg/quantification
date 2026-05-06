# account constraints report

- status: WARN
- generated_at: 2026-05-06T03:52:23.850322+00:00
- git_commit: c368f718e365edd1ce6ad8f2bd9bb6bc8a074cad
- config_hash: 098ddb69f56c5752f13f3475d04e33b530172a91e765322d86841789255a4321

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
- repeated_blocked_buy_signal_count: 0
- account_feasible_buy_signal_count: 116
- user_visible_buy_recommendation_count: 43
- user_visible_blocked_buy_count: 327
- pending_buy_intent_count: 0
- raw_sell_signal_count: 91
- executable_buy_count: 43
- executable_sell_count: 33
- executable_raw_buy_ratio: 0.11621621621621622
- executable_account_feasible_buy_ratio: 0.3706896551724138
- average_cash_ratio: 0.5561
- average_exposure: 0.4694
- max_exposure: 0.7569
- turnover: 555248.63

## blocker_counts

- CASH_INSUFFICIENT: 88
- LOT_SIZE_ZERO: 4
- MAX_POSITIONS_LIMIT: 5
- MIN_TRADE_AMOUNT: 220
- TOTAL_EXPOSURE_LIMIT: 68

## WARN

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.11621621621621622
- MIN_TRADE_AMOUNT_DOMINATES_EXECUTION: min_trade_amount dominates execution actual=0.5945945945945946
