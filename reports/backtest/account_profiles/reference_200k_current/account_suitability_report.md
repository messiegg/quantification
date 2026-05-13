# account suitability report

- status: WARN
- generated_at: 2026-05-07T07:15:15.118689+00:00

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

## base case

- initial_capital: 200000.0
- min_trade_amount: 5000.0
- raw_buy_signal_count: 370
- unique_raw_buy_intent_count: 370
- repeat_raw_buy_intent_count: 0
- repeat_raw_buy_intent_ratio: 0.0
- repeated_blocked_buy_signal_count: 0
- account_feasible_buy_signal_count: 116
- executable_buy_count: 43
- executable_new_position_buy_count: 39
- executable_add_buy_count: 4
- executable_raw_buy_ratio: 0.11621621621621622
- executable_unique_raw_intent_ratio: 0.11621621621621622
- executable_account_feasible_buy_ratio: 0.3706896551724138
- user_visible_buy_recommendation_count: 43
- user_visible_blocked_buy_count: 327
- pending_buy_intent_count: 0
- full_portfolio_raw_buy_intent_count: 5
- full_portfolio_raw_buy_intent_ratio: 0.013513513513513514
- new_position_raw_intent_count: 300
- add_position_raw_intent_count: 70
- estimated_capital_required_to_reach_executable_raw_25: unknown
- estimated_capital_required_to_reach_executable_raw_50: unknown

## base blocker ratios

- min_trade_amount_block_ratio: 0.5945945945945946
- cash_block_ratio: 0.23783783783783785 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_ratio: 0.23783783783783785 (cash + one-lot cash blockers)
- exposure_block_ratio: 0.1837837837837838
- max_positions_block_ratio: 0.013513513513513514
- lot_size_block_ratio: 0.010810810810810811
- price_too_high_for_account_lot_ratio: 0.0
- cash_insufficient_for_one_lot_ratio: 0.0

## scenario notes

- capital_x0.5_min_trade_x1_target_positions_20: research_only=true estimated_ratio=0.11621621621621622
- capital_x0.5_min_trade_x1_target_positions_12: research_only=true estimated_ratio=0.11621621621621622
- capital_x0.5_min_trade_x1_target_positions_18: research_only=true estimated_ratio=0.11621621621621622
- capital_x0.5_min_trade_x1_target_positions_24: research_only=true estimated_ratio=0.11621621621621622
- capital_x0.5_min_trade_x1_target_positions_30: research_only=true estimated_ratio=0.11621621621621622
- capital_x0.5_min_trade_x0.5_target_positions_20: research_only=true estimated_ratio=0.46216216216216216
- capital_x0.5_min_trade_x0.5_target_positions_12: research_only=true estimated_ratio=0.46216216216216216
- capital_x0.5_min_trade_x0.5_target_positions_18: research_only=true estimated_ratio=0.46216216216216216
- capital_x0.5_min_trade_x0.5_target_positions_24: research_only=true estimated_ratio=0.46216216216216216
- capital_x0.5_min_trade_x0.5_target_positions_30: research_only=true estimated_ratio=0.46216216216216216
- capital_x0.5_min_trade_x0.25_target_positions_20: research_only=true estimated_ratio=0.5540540540540541
- capital_x0.5_min_trade_x0.25_target_positions_12: research_only=true estimated_ratio=0.5540540540540541
- capital_x0.5_min_trade_x0.25_target_positions_18: research_only=true estimated_ratio=0.5540540540540541
- capital_x0.5_min_trade_x0.25_target_positions_24: research_only=true estimated_ratio=0.5540540540540541
- capital_x0.5_min_trade_x0.25_target_positions_30: research_only=true estimated_ratio=0.5540540540540541

## missing data for exact estimate

- per_signal_actual_equity
- per_signal_desired_trade_amount
- per_signal_cash_after_priority_ordering

## warnings

- BASE_CASE_EXECUTION_RATIO_BELOW_OBSERVATION_MINIMUM: actual=0.11621621621621622
- MIN_TRADE_AMOUNT_DOMINATES_BASE_CASE: actual=0.5945945945945946
