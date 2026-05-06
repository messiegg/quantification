# account constraints report

- status: WARN
- generated_at: 2026-05-06T03:58:23.747912+00:00
- git_commit: c368f718e365edd1ce6ad8f2bd9bb6bc8a074cad
- config_hash: 98d128a06d4b76e3a52714f8a10933a8ff9c31ba47b08fe17d27d36ee7028c89

## runtime profile

- account_profile: retail_50k
- initial_capital: 50000.0
- min_trade_value: 1500.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 12
- portfolio_equal_weight_target_positions: 12

## execution funnel

- raw_buy_signal_count: 1145
- unique_raw_buy_intent_count: 1145
- repeated_blocked_buy_signal_count: 0
- account_feasible_buy_signal_count: 12
- user_visible_buy_recommendation_count: 12
- user_visible_blocked_buy_count: 1133
- pending_buy_intent_count: 0
- raw_sell_signal_count: 9
- executable_buy_count: 12
- executable_sell_count: 9
- executable_raw_buy_ratio: 0.010480349344978166
- executable_account_feasible_buy_ratio: 1.0
- average_cash_ratio: 0.8638
- average_exposure: 0.1485
- max_exposure: 0.2630
- turnover: 40135.57

## blocker_counts

- LOT_SIZE_ZERO: 783
- MIN_TRADE_AMOUNT: 350

## WARN

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.010480349344978166
