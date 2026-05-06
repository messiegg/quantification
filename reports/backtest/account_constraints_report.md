# account constraints report

- status: WARN
- generated_at: 2026-05-06T07:49:50.605387+00:00
- git_commit: c368f718e365edd1ce6ad8f2bd9bb6bc8a074cad
- config_hash: 77fab057ca5cee090e85267b1dc7d0bf4e489f66913f3cc2ace187529a0373f7

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
- repeated_blocked_buy_signal_count: 470
- account_feasible_buy_signal_count: 426
- user_visible_buy_recommendation_count: 23
- user_visible_blocked_buy_count: 136
- pending_buy_intent_count: 47
- raw_sell_signal_count: 18
- executable_buy_count: 23
- executable_sell_count: 18
- executable_raw_buy_ratio: 0.03656597774244833
- executable_account_feasible_buy_ratio: 0.0539906103286385
- average_cash_ratio: 0.5757
- average_exposure: 0.4454
- max_exposure: 0.5501
- turnover: 102109.96

## blocker_counts

- CASH_INSUFFICIENT_FOR_ONE_LOT: 139
- DAILY_NEW_POSITION_LIMIT: 1
- LOT_SIZE_ACCUMULATION_REQUIRED: 18
- MAX_POSITIONS_LIMIT: 402
- PRICE_TOO_HIGH_FOR_ACCOUNT_LOT: 30
- PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY: 16

## WARN

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.03656597774244833
