# account suitability report

- status: WARN
- generated_at: 2026-05-06T03:55:17.544655+00:00

## runtime profile

- account_profile: actual_50k_unmodified
- initial_capital: 50000.0
- min_trade_value: 5000.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 20
- portfolio_equal_weight_target_positions: 36

## base case

- initial_capital: 50000.0
- min_trade_amount: 5000.0
- raw_buy_signal_count: 1300
- unique_raw_buy_intent_count: 1300
- repeated_blocked_buy_signal_count: 0
- account_feasible_buy_signal_count: 0
- executable_buy_count: 0
- executable_raw_buy_ratio: 0.0
- executable_account_feasible_buy_ratio: None
- user_visible_buy_recommendation_count: 0
- user_visible_blocked_buy_count: 1300
- pending_buy_intent_count: 0
- estimated_capital_required_to_reach_executable_raw_25: unknown
- estimated_capital_required_to_reach_executable_raw_50: unknown

## base blocker ratios

- min_trade_amount_block_ratio: 0.3976923076923077
- cash_block_ratio: 0.0
- exposure_block_ratio: 0.0
- max_positions_block_ratio: 0.0
- lot_size_block_ratio: 0.6023076923076923
- price_too_high_for_account_lot_ratio: 0.0
- cash_insufficient_for_one_lot_ratio: 0.0

## scenario notes

- capital_x0.5_min_trade_x1_target_positions_20: research_only=true estimated_ratio=0.0
- capital_x0.5_min_trade_x1_target_positions_12: research_only=true estimated_ratio=0.0
- capital_x0.5_min_trade_x1_target_positions_18: research_only=true estimated_ratio=0.0
- capital_x0.5_min_trade_x1_target_positions_24: research_only=true estimated_ratio=0.0
- capital_x0.5_min_trade_x1_target_positions_30: research_only=true estimated_ratio=0.0
- capital_x0.5_min_trade_x0.5_target_positions_20: research_only=true estimated_ratio=0.0
- capital_x0.5_min_trade_x0.5_target_positions_12: research_only=true estimated_ratio=0.0
- capital_x0.5_min_trade_x0.5_target_positions_18: research_only=true estimated_ratio=0.0
- capital_x0.5_min_trade_x0.5_target_positions_24: research_only=true estimated_ratio=0.0
- capital_x0.5_min_trade_x0.5_target_positions_30: research_only=true estimated_ratio=0.0
- capital_x0.5_min_trade_x0.25_target_positions_20: research_only=true estimated_ratio=0.0
- capital_x0.5_min_trade_x0.25_target_positions_12: research_only=true estimated_ratio=0.0
- capital_x0.5_min_trade_x0.25_target_positions_18: research_only=true estimated_ratio=0.0
- capital_x0.5_min_trade_x0.25_target_positions_24: research_only=true estimated_ratio=0.0
- capital_x0.5_min_trade_x0.25_target_positions_30: research_only=true estimated_ratio=0.0

## missing data for exact estimate

- per_signal_actual_equity
- per_signal_desired_trade_amount
- per_signal_cash_after_priority_ordering

## warnings

- BASE_CASE_EXECUTION_RATIO_BELOW_OBSERVATION_MINIMUM: actual=0.0
