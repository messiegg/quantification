# account suitability report

- status: WARN
- generated_at: 2026-05-07T04:28:23.733387+00:00

## runtime profile

- account_profile: tranche_5_10_15_max15
- initial_capital: 50000.0
- min_trade_value: 1500.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 6
- portfolio_equal_weight_target_positions: 6

## base case

- initial_capital: 50000.0
- min_trade_amount: 1500.0
- raw_buy_signal_count: 849
- unique_raw_buy_intent_count: 190
- repeat_raw_buy_intent_count: 659
- repeat_raw_buy_intent_ratio: 0.7762073027090695
- repeated_blocked_buy_signal_count: 659
- account_feasible_buy_signal_count: 811
- executable_buy_count: 24
- executable_new_position_buy_count: 19
- executable_add_buy_count: 3
- executable_raw_buy_ratio: 0.028268551236749116
- executable_unique_raw_intent_ratio: 0.12631578947368421
- executable_account_feasible_buy_ratio: 0.029593094944512947
- user_visible_buy_recommendation_count: 24
- user_visible_blocked_buy_count: 166
- pending_buy_intent_count: 11
- full_portfolio_raw_buy_intent_count: 785
- full_portfolio_raw_buy_intent_ratio: 0.9246171967020024
- new_position_raw_intent_count: 835
- add_position_raw_intent_count: 14
- estimated_capital_required_to_reach_executable_raw_25: unknown
- estimated_capital_required_to_reach_executable_raw_50: unknown

## base blocker ratios

- min_trade_amount_block_ratio: 0.001177856301531213
- cash_block_ratio: 0.0 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_ratio: 0.009422850412249705 (cash + one-lot cash blockers)
- exposure_block_ratio: 0.0
- max_positions_block_ratio: 0.9246171967020024
- lot_size_block_ratio: 0.001177856301531213
- price_too_high_for_account_lot_ratio: 0.02237926972909305
- cash_insufficient_for_one_lot_ratio: 0.009422850412249705

## scenario notes

- capital_x0.5_min_trade_x1_target_positions_6: research_only=true estimated_ratio=0.028268551236749116
- capital_x0.5_min_trade_x1_target_positions_12: research_only=true estimated_ratio=0.028268551236749116
- capital_x0.5_min_trade_x1_target_positions_18: research_only=true estimated_ratio=0.028268551236749116
- capital_x0.5_min_trade_x1_target_positions_24: research_only=true estimated_ratio=0.028268551236749116
- capital_x0.5_min_trade_x1_target_positions_30: research_only=true estimated_ratio=0.028268551236749116
- capital_x0.5_min_trade_x0.5_target_positions_6: research_only=true estimated_ratio=0.028268551236749116
- capital_x0.5_min_trade_x0.5_target_positions_12: research_only=true estimated_ratio=0.028268551236749116
- capital_x0.5_min_trade_x0.5_target_positions_18: research_only=true estimated_ratio=0.028268551236749116
- capital_x0.5_min_trade_x0.5_target_positions_24: research_only=true estimated_ratio=0.028268551236749116
- capital_x0.5_min_trade_x0.5_target_positions_30: research_only=true estimated_ratio=0.028268551236749116
- capital_x0.5_min_trade_x0.25_target_positions_6: research_only=true estimated_ratio=0.028268551236749116
- capital_x0.5_min_trade_x0.25_target_positions_12: research_only=true estimated_ratio=0.028268551236749116
- capital_x0.5_min_trade_x0.25_target_positions_18: research_only=true estimated_ratio=0.028268551236749116
- capital_x0.5_min_trade_x0.25_target_positions_24: research_only=true estimated_ratio=0.028268551236749116
- capital_x0.5_min_trade_x0.25_target_positions_30: research_only=true estimated_ratio=0.028268551236749116

## missing data for exact estimate

- per_signal_actual_equity
- per_signal_desired_trade_amount
- per_signal_cash_after_priority_ordering

## warnings

- BASE_CASE_EXECUTION_RATIO_BELOW_OBSERVATION_MINIMUM: actual=0.028268551236749116
