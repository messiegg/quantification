# account suitability report

- status: WARN
- generated_at: 2026-05-07T04:05:43.618367+00:00

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

## base case

- initial_capital: 50000.0
- min_trade_amount: 1000.0
- raw_buy_signal_count: 674
- unique_raw_buy_intent_count: 164
- repeat_raw_buy_intent_count: 510
- repeat_raw_buy_intent_ratio: 0.7566765578635015
- repeated_blocked_buy_signal_count: 510
- account_feasible_buy_signal_count: 482
- executable_buy_count: 22
- executable_new_position_buy_count: 19
- executable_add_buy_count: 3
- executable_raw_buy_ratio: 0.032640949554896145
- executable_unique_raw_intent_ratio: 0.13414634146341464
- executable_account_feasible_buy_ratio: 0.04564315352697095
- user_visible_buy_recommendation_count: 22
- user_visible_blocked_buy_count: 142
- pending_buy_intent_count: 34
- full_portfolio_raw_buy_intent_count: 459
- full_portfolio_raw_buy_intent_ratio: 0.6810089020771514
- new_position_raw_intent_count: 637
- add_position_raw_intent_count: 37
- estimated_capital_required_to_reach_executable_raw_25: unknown
- estimated_capital_required_to_reach_executable_raw_50: unknown

## base blocker ratios

- min_trade_amount_block_ratio: 0.020771513353115726
- cash_block_ratio: 0.0 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_ratio: 0.22403560830860533 (cash + one-lot cash blockers)
- exposure_block_ratio: 0.0
- max_positions_block_ratio: 0.6810089020771514
- lot_size_block_ratio: 0.0
- price_too_high_for_account_lot_ratio: 0.04451038575667656
- cash_insufficient_for_one_lot_ratio: 0.22403560830860533

## scenario notes

- capital_x0.5_min_trade_x1_target_positions_8: research_only=true estimated_ratio=0.032640949554896145
- capital_x0.5_min_trade_x1_target_positions_12: research_only=true estimated_ratio=0.032640949554896145
- capital_x0.5_min_trade_x1_target_positions_18: research_only=true estimated_ratio=0.032640949554896145
- capital_x0.5_min_trade_x1_target_positions_24: research_only=true estimated_ratio=0.032640949554896145
- capital_x0.5_min_trade_x1_target_positions_30: research_only=true estimated_ratio=0.032640949554896145
- capital_x0.5_min_trade_x0.5_target_positions_8: research_only=true estimated_ratio=0.032640949554896145
- capital_x0.5_min_trade_x0.5_target_positions_12: research_only=true estimated_ratio=0.032640949554896145
- capital_x0.5_min_trade_x0.5_target_positions_18: research_only=true estimated_ratio=0.032640949554896145
- capital_x0.5_min_trade_x0.5_target_positions_24: research_only=true estimated_ratio=0.032640949554896145
- capital_x0.5_min_trade_x0.5_target_positions_30: research_only=true estimated_ratio=0.032640949554896145
- capital_x0.5_min_trade_x0.25_target_positions_8: research_only=true estimated_ratio=0.032640949554896145
- capital_x0.5_min_trade_x0.25_target_positions_12: research_only=true estimated_ratio=0.032640949554896145
- capital_x0.5_min_trade_x0.25_target_positions_18: research_only=true estimated_ratio=0.032640949554896145
- capital_x0.5_min_trade_x0.25_target_positions_24: research_only=true estimated_ratio=0.032640949554896145
- capital_x0.5_min_trade_x0.25_target_positions_30: research_only=true estimated_ratio=0.032640949554896145

## missing data for exact estimate

- per_signal_actual_equity
- per_signal_desired_trade_amount
- per_signal_cash_after_priority_ordering

## warnings

- BASE_CASE_EXECUTION_RATIO_BELOW_OBSERVATION_MINIMUM: actual=0.032640949554896145
