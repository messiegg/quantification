# account suitability report

- status: WARN
- generated_at: 2026-05-08T00:48:20.255032+00:00

## runtime profile

- account_profile: capital_500k_maxpos20
- initial_capital: 500000.0
- min_trade_value: 1500.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 20
- portfolio_equal_weight_target_positions: 20

## base case

- initial_capital: 500000.0
- min_trade_amount: 1500.0
- raw_buy_signal_count: 268
- unique_raw_buy_intent_count: 114
- repeat_raw_buy_intent_count: 154
- repeat_raw_buy_intent_ratio: 0.5746268656716418
- repeated_blocked_buy_signal_count: 154
- account_feasible_buy_signal_count: 63
- executable_buy_count: 46
- executable_new_position_buy_count: 39
- executable_add_buy_count: 6
- executable_raw_buy_ratio: 0.17164179104477612
- executable_unique_raw_intent_ratio: 0.40350877192982454
- executable_account_feasible_buy_ratio: 0.7301587301587301
- user_visible_buy_recommendation_count: 46
- user_visible_blocked_buy_count: 68
- pending_buy_intent_count: 41
- full_portfolio_raw_buy_intent_count: 17
- full_portfolio_raw_buy_intent_ratio: 0.06343283582089553
- new_position_raw_intent_count: 220
- add_position_raw_intent_count: 48
- estimated_capital_required_to_reach_executable_raw_25: unknown
- estimated_capital_required_to_reach_executable_raw_50: unknown

## base blocker ratios

- min_trade_amount_block_ratio: 0.0
- cash_block_ratio: 0.011194029850746268 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_ratio: 0.7649253731343284 (cash + one-lot cash blockers)
- exposure_block_ratio: 0.0037313432835820895
- max_positions_block_ratio: 0.06343283582089553
- lot_size_block_ratio: 0.0
- price_too_high_for_account_lot_ratio: 0.0
- cash_insufficient_for_one_lot_ratio: 0.753731343283582

## scenario notes

- capital_x0.5_min_trade_x1_target_positions_20: research_only=true estimated_ratio=0.17164179104477612
- capital_x0.5_min_trade_x1_target_positions_12: research_only=true estimated_ratio=0.17164179104477612
- capital_x0.5_min_trade_x1_target_positions_18: research_only=true estimated_ratio=0.17164179104477612
- capital_x0.5_min_trade_x1_target_positions_24: research_only=true estimated_ratio=0.17164179104477612
- capital_x0.5_min_trade_x1_target_positions_30: research_only=true estimated_ratio=0.17164179104477612
- capital_x0.5_min_trade_x0.5_target_positions_20: research_only=true estimated_ratio=0.17164179104477612
- capital_x0.5_min_trade_x0.5_target_positions_12: research_only=true estimated_ratio=0.17164179104477612
- capital_x0.5_min_trade_x0.5_target_positions_18: research_only=true estimated_ratio=0.17164179104477612
- capital_x0.5_min_trade_x0.5_target_positions_24: research_only=true estimated_ratio=0.17164179104477612
- capital_x0.5_min_trade_x0.5_target_positions_30: research_only=true estimated_ratio=0.17164179104477612
- capital_x0.5_min_trade_x0.25_target_positions_20: research_only=true estimated_ratio=0.17164179104477612
- capital_x0.5_min_trade_x0.25_target_positions_12: research_only=true estimated_ratio=0.17164179104477612
- capital_x0.5_min_trade_x0.25_target_positions_18: research_only=true estimated_ratio=0.17164179104477612
- capital_x0.5_min_trade_x0.25_target_positions_24: research_only=true estimated_ratio=0.17164179104477612
- capital_x0.5_min_trade_x0.25_target_positions_30: research_only=true estimated_ratio=0.17164179104477612

## missing data for exact estimate

- per_signal_actual_equity
- per_signal_desired_trade_amount
- per_signal_cash_after_priority_ordering

## warnings

- BASE_CASE_EXECUTION_RATIO_BELOW_OBSERVATION_MINIMUM: actual=0.17164179104477612
