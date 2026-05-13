# account suitability report

- status: WARN
- generated_at: 2026-05-07T04:18:44.335380+00:00

## runtime profile

- account_profile: max_positions_12_50k
- initial_capital: 50000.0
- min_trade_value: 1500.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 12
- portfolio_equal_weight_target_positions: 12

## base case

- initial_capital: 50000.0
- min_trade_amount: 1500.0
- raw_buy_signal_count: 481
- unique_raw_buy_intent_count: 131
- repeat_raw_buy_intent_count: 350
- repeat_raw_buy_intent_ratio: 0.7276507276507277
- repeated_blocked_buy_signal_count: 350
- account_feasible_buy_signal_count: 168
- executable_buy_count: 31
- executable_new_position_buy_count: 27
- executable_add_buy_count: 3
- executable_raw_buy_ratio: 0.06444906444906445
- executable_unique_raw_intent_ratio: 0.2366412213740458
- executable_account_feasible_buy_ratio: 0.18452380952380953
- user_visible_buy_recommendation_count: 31
- user_visible_blocked_buy_count: 100
- pending_buy_intent_count: 35
- full_portfolio_raw_buy_intent_count: 132
- full_portfolio_raw_buy_intent_ratio: 0.27442827442827444
- new_position_raw_intent_count: 443
- add_position_raw_intent_count: 38
- estimated_capital_required_to_reach_executable_raw_25: unknown
- estimated_capital_required_to_reach_executable_raw_50: unknown

## base blocker ratios

- min_trade_amount_block_ratio: 0.002079002079002079
- cash_block_ratio: 0.0 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_ratio: 0.48440748440748443 (cash + one-lot cash blockers)
- exposure_block_ratio: 0.0
- max_positions_block_ratio: 0.27442827442827444
- lot_size_block_ratio: 0.0
- price_too_high_for_account_lot_ratio: 0.09563409563409564
- cash_insufficient_for_one_lot_ratio: 0.48440748440748443

## scenario notes

- capital_x0.5_min_trade_x1_target_positions_12: research_only=true estimated_ratio=0.06444906444906445
- capital_x0.5_min_trade_x1_target_positions_12: research_only=true estimated_ratio=0.06444906444906445
- capital_x0.5_min_trade_x1_target_positions_18: research_only=true estimated_ratio=0.06444906444906445
- capital_x0.5_min_trade_x1_target_positions_24: research_only=true estimated_ratio=0.06444906444906445
- capital_x0.5_min_trade_x1_target_positions_30: research_only=true estimated_ratio=0.06444906444906445
- capital_x0.5_min_trade_x0.5_target_positions_12: research_only=true estimated_ratio=0.06444906444906445
- capital_x0.5_min_trade_x0.5_target_positions_12: research_only=true estimated_ratio=0.06444906444906445
- capital_x0.5_min_trade_x0.5_target_positions_18: research_only=true estimated_ratio=0.06444906444906445
- capital_x0.5_min_trade_x0.5_target_positions_24: research_only=true estimated_ratio=0.06444906444906445
- capital_x0.5_min_trade_x0.5_target_positions_30: research_only=true estimated_ratio=0.06444906444906445
- capital_x0.5_min_trade_x0.25_target_positions_12: research_only=true estimated_ratio=0.06444906444906445
- capital_x0.5_min_trade_x0.25_target_positions_12: research_only=true estimated_ratio=0.06444906444906445
- capital_x0.5_min_trade_x0.25_target_positions_18: research_only=true estimated_ratio=0.06444906444906445
- capital_x0.5_min_trade_x0.25_target_positions_24: research_only=true estimated_ratio=0.06444906444906445
- capital_x0.5_min_trade_x0.25_target_positions_30: research_only=true estimated_ratio=0.06444906444906445

## missing data for exact estimate

- per_signal_actual_equity
- per_signal_desired_trade_amount
- per_signal_cash_after_priority_ordering

## warnings

- BASE_CASE_EXECUTION_RATIO_BELOW_OBSERVATION_MINIMUM: actual=0.06444906444906445
