# account suitability report

- status: WARN
- generated_at: 2026-05-07T04:26:04.155676+00:00

## runtime profile

- account_profile: max_single_20pct
- initial_capital: 50000.0
- min_trade_value: 1500.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 8
- portfolio_equal_weight_target_positions: 8

## base case

- initial_capital: 50000.0
- min_trade_amount: 1500.0
- raw_buy_signal_count: 629
- unique_raw_buy_intent_count: 159
- repeat_raw_buy_intent_count: 470
- repeat_raw_buy_intent_ratio: 0.7472178060413355
- repeated_blocked_buy_signal_count: 470
- account_feasible_buy_signal_count: 426
- executable_buy_count: 23
- executable_new_position_buy_count: 20
- executable_add_buy_count: 3
- executable_raw_buy_ratio: 0.03656597774244833
- executable_unique_raw_intent_ratio: 0.14465408805031446
- executable_account_feasible_buy_ratio: 0.0539906103286385
- user_visible_buy_recommendation_count: 23
- user_visible_blocked_buy_count: 136
- pending_buy_intent_count: 47
- full_portfolio_raw_buy_intent_count: 402
- full_portfolio_raw_buy_intent_ratio: 0.6391096979332274
- new_position_raw_intent_count: 579
- add_position_raw_intent_count: 50
- estimated_capital_required_to_reach_executable_raw_25: unknown
- estimated_capital_required_to_reach_executable_raw_50: unknown

## base blocker ratios

- min_trade_amount_block_ratio: 0.0
- cash_block_ratio: 0.0 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_ratio: 0.22098569157392686 (cash + one-lot cash blockers)
- exposure_block_ratio: 0.0
- max_positions_block_ratio: 0.6391096979332274
- lot_size_block_ratio: 0.0
- price_too_high_for_account_lot_ratio: 0.04769475357710652
- cash_insufficient_for_one_lot_ratio: 0.22098569157392686

## scenario notes

- capital_x0.5_min_trade_x1_target_positions_8: research_only=true estimated_ratio=0.03656597774244833
- capital_x0.5_min_trade_x1_target_positions_12: research_only=true estimated_ratio=0.03656597774244833
- capital_x0.5_min_trade_x1_target_positions_18: research_only=true estimated_ratio=0.03656597774244833
- capital_x0.5_min_trade_x1_target_positions_24: research_only=true estimated_ratio=0.03656597774244833
- capital_x0.5_min_trade_x1_target_positions_30: research_only=true estimated_ratio=0.03656597774244833
- capital_x0.5_min_trade_x0.5_target_positions_8: research_only=true estimated_ratio=0.03656597774244833
- capital_x0.5_min_trade_x0.5_target_positions_12: research_only=true estimated_ratio=0.03656597774244833
- capital_x0.5_min_trade_x0.5_target_positions_18: research_only=true estimated_ratio=0.03656597774244833
- capital_x0.5_min_trade_x0.5_target_positions_24: research_only=true estimated_ratio=0.03656597774244833
- capital_x0.5_min_trade_x0.5_target_positions_30: research_only=true estimated_ratio=0.03656597774244833
- capital_x0.5_min_trade_x0.25_target_positions_8: research_only=true estimated_ratio=0.03656597774244833
- capital_x0.5_min_trade_x0.25_target_positions_12: research_only=true estimated_ratio=0.03656597774244833
- capital_x0.5_min_trade_x0.25_target_positions_18: research_only=true estimated_ratio=0.03656597774244833
- capital_x0.5_min_trade_x0.25_target_positions_24: research_only=true estimated_ratio=0.03656597774244833
- capital_x0.5_min_trade_x0.25_target_positions_30: research_only=true estimated_ratio=0.03656597774244833

## missing data for exact estimate

- per_signal_actual_equity
- per_signal_desired_trade_amount
- per_signal_cash_after_priority_ordering

## warnings

- BASE_CASE_EXECUTION_RATIO_BELOW_OBSERVATION_MINIMUM: actual=0.03656597774244833
