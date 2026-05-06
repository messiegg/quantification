# reference_200k_current account profile backtest

- status: WARN
- research_only: true
- initial_capital: 200000.0
- min_trade_value: 5000.0
- portfolio_max_positions: 20
- portfolio_equal_weight_target_positions: 36
- universe_target_size: 36
- universe_selected_count: 30
- lot_aware_sizing: false
- raw_buy_signal_count: 370
- unique_raw_buy_intent_count: 370
- repeated_blocked_buy_signal_count: 0
- account_feasible_buy_signal_count: 116
- executable_buy_count: 43
- executable_raw_buy_ratio: 0.11621621621621622
- executable_account_feasible_buy_ratio: 0.3706896551724138
- user_visible_buy_recommendation_count: 43
- user_visible_blocked_buy_count: 327
- pending_buy_intent_count: 0
- min_trade_amount_block_ratio: 0.5945945945945946
- lot_size_zero_block_count: 4
- lot_size_zero_block_ratio: 0.010810810810810811
- price_too_high_for_account_lot_count: 0
- cash_block_ratio: 0.23783783783783785
- max_positions_block_ratio: 0.013513513513513514
- average_positions: 12.287878787878787
- max_positions_seen: 20
- annual_return: 0.07135202476872582
- cumulative_return: 0.21964440453100043
- max_drawdown: -0.09364547429916759
- Sharpe: 0.7782204340639889
- turnover: 2.7762431675
- transaction_cost_pct: 0.0028855954689998554

## warnings

- ACCOUNT_CONSTRAINTS_DOMINATE_EXECUTION: actual=0.11621621621621622 expected=>=0.25
- MIN_TRADE_AMOUNT_BLOCK_RATIO_HIGH: actual=0.5945945945945946 expected=<=0.40

## violations

- none
