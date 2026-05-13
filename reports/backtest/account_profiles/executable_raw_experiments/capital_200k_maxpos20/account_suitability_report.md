# account suitability report

- status: WARN
- generated_at: 2026-05-07T04:23:40.505999+00:00

## runtime profile

- account_profile: capital_200k_maxpos20
- initial_capital: 200000.0
- min_trade_value: 1500.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 20
- portfolio_equal_weight_target_positions: 20

## base case

- initial_capital: 200000.0
- min_trade_amount: 1500.0
- raw_buy_signal_count: 264
- unique_raw_buy_intent_count: 112
- repeat_raw_buy_intent_count: 152
- repeat_raw_buy_intent_ratio: 0.5757575757575758
- repeated_blocked_buy_signal_count: 152
- account_feasible_buy_signal_count: 79
- executable_buy_count: 50
- executable_new_position_buy_count: 39
- executable_add_buy_count: 8
- executable_raw_buy_ratio: 0.1893939393939394
- executable_unique_raw_intent_ratio: 0.44642857142857145
- executable_account_feasible_buy_ratio: 0.6329113924050633
- user_visible_buy_recommendation_count: 50
- user_visible_blocked_buy_count: 62
- pending_buy_intent_count: 24
- full_portfolio_raw_buy_intent_count: 29
- full_portfolio_raw_buy_intent_ratio: 0.10984848484848485
- new_position_raw_intent_count: 229
- add_position_raw_intent_count: 35
- estimated_capital_required_to_reach_executable_raw_25: unknown
- estimated_capital_required_to_reach_executable_raw_50: unknown

## base blocker ratios

- min_trade_amount_block_ratio: 0.0
- cash_block_ratio: 0.045454545454545456 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_ratio: 0.7007575757575758 (cash + one-lot cash blockers)
- exposure_block_ratio: 0.003787878787878788
- max_positions_block_ratio: 0.10984848484848485
- lot_size_block_ratio: 0.007575757575757576
- price_too_high_for_account_lot_ratio: 0.0
- cash_insufficient_for_one_lot_ratio: 0.6553030303030303

## scenario notes

- capital_x0.5_min_trade_x1_target_positions_20: research_only=true estimated_ratio=0.1893939393939394
- capital_x0.5_min_trade_x1_target_positions_12: research_only=true estimated_ratio=0.1893939393939394
- capital_x0.5_min_trade_x1_target_positions_18: research_only=true estimated_ratio=0.1893939393939394
- capital_x0.5_min_trade_x1_target_positions_24: research_only=true estimated_ratio=0.1893939393939394
- capital_x0.5_min_trade_x1_target_positions_30: research_only=true estimated_ratio=0.1893939393939394
- capital_x0.5_min_trade_x0.5_target_positions_20: research_only=true estimated_ratio=0.1893939393939394
- capital_x0.5_min_trade_x0.5_target_positions_12: research_only=true estimated_ratio=0.1893939393939394
- capital_x0.5_min_trade_x0.5_target_positions_18: research_only=true estimated_ratio=0.1893939393939394
- capital_x0.5_min_trade_x0.5_target_positions_24: research_only=true estimated_ratio=0.1893939393939394
- capital_x0.5_min_trade_x0.5_target_positions_30: research_only=true estimated_ratio=0.1893939393939394
- capital_x0.5_min_trade_x0.25_target_positions_20: research_only=true estimated_ratio=0.1893939393939394
- capital_x0.5_min_trade_x0.25_target_positions_12: research_only=true estimated_ratio=0.1893939393939394
- capital_x0.5_min_trade_x0.25_target_positions_18: research_only=true estimated_ratio=0.1893939393939394
- capital_x0.5_min_trade_x0.25_target_positions_24: research_only=true estimated_ratio=0.1893939393939394
- capital_x0.5_min_trade_x0.25_target_positions_30: research_only=true estimated_ratio=0.1893939393939394

## missing data for exact estimate

- per_signal_actual_equity
- per_signal_desired_trade_amount
- per_signal_cash_after_priority_ordering

## warnings

- BASE_CASE_EXECUTION_RATIO_BELOW_OBSERVATION_MINIMUM: actual=0.1893939393939394
