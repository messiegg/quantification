# account suitability report

- status: WARN
- generated_at: 2026-05-07T04:10:22.564732+00:00

## runtime profile

- account_profile: capital_100k_lot_aware
- initial_capital: 100000.0
- min_trade_value: 1500.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 8
- portfolio_equal_weight_target_positions: 8

## base case

- initial_capital: 100000.0
- min_trade_amount: 1500.0
- raw_buy_signal_count: 555
- unique_raw_buy_intent_count: 152
- repeat_raw_buy_intent_count: 403
- repeat_raw_buy_intent_ratio: 0.7261261261261261
- repeated_blocked_buy_signal_count: 403
- account_feasible_buy_signal_count: 531
- executable_buy_count: 28
- executable_new_position_buy_count: 24
- executable_add_buy_count: 4
- executable_raw_buy_ratio: 0.05045045045045045
- executable_unique_raw_intent_ratio: 0.18421052631578946
- executable_account_feasible_buy_ratio: 0.05273069679849341
- user_visible_buy_recommendation_count: 28
- user_visible_blocked_buy_count: 124
- pending_buy_intent_count: 24
- full_portfolio_raw_buy_intent_count: 502
- full_portfolio_raw_buy_intent_ratio: 0.9045045045045045
- new_position_raw_intent_count: 527
- add_position_raw_intent_count: 28
- estimated_capital_required_to_reach_executable_raw_25: unknown
- estimated_capital_required_to_reach_executable_raw_50: unknown

## base blocker ratios

- min_trade_amount_block_ratio: 0.0
- cash_block_ratio: 0.0 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_ratio: 0.0 (cash + one-lot cash blockers)
- exposure_block_ratio: 0.0
- max_positions_block_ratio: 0.9045045045045045
- lot_size_block_ratio: 0.0
- price_too_high_for_account_lot_ratio: 0.0
- cash_insufficient_for_one_lot_ratio: 0.0

## scenario notes

- capital_x0.5_min_trade_x1_target_positions_8: research_only=true estimated_ratio=0.05045045045045045
- capital_x0.5_min_trade_x1_target_positions_12: research_only=true estimated_ratio=0.05045045045045045
- capital_x0.5_min_trade_x1_target_positions_18: research_only=true estimated_ratio=0.05045045045045045
- capital_x0.5_min_trade_x1_target_positions_24: research_only=true estimated_ratio=0.05045045045045045
- capital_x0.5_min_trade_x1_target_positions_30: research_only=true estimated_ratio=0.05045045045045045
- capital_x0.5_min_trade_x0.5_target_positions_8: research_only=true estimated_ratio=0.05045045045045045
- capital_x0.5_min_trade_x0.5_target_positions_12: research_only=true estimated_ratio=0.05045045045045045
- capital_x0.5_min_trade_x0.5_target_positions_18: research_only=true estimated_ratio=0.05045045045045045
- capital_x0.5_min_trade_x0.5_target_positions_24: research_only=true estimated_ratio=0.05045045045045045
- capital_x0.5_min_trade_x0.5_target_positions_30: research_only=true estimated_ratio=0.05045045045045045
- capital_x0.5_min_trade_x0.25_target_positions_8: research_only=true estimated_ratio=0.05045045045045045
- capital_x0.5_min_trade_x0.25_target_positions_12: research_only=true estimated_ratio=0.05045045045045045
- capital_x0.5_min_trade_x0.25_target_positions_18: research_only=true estimated_ratio=0.05045045045045045
- capital_x0.5_min_trade_x0.25_target_positions_24: research_only=true estimated_ratio=0.05045045045045045
- capital_x0.5_min_trade_x0.25_target_positions_30: research_only=true estimated_ratio=0.05045045045045045

## missing data for exact estimate

- per_signal_actual_equity
- per_signal_desired_trade_amount
- per_signal_cash_after_priority_ordering

## warnings

- BASE_CASE_EXECUTION_RATIO_BELOW_OBSERVATION_MINIMUM: actual=0.05045045045045045
