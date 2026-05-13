# account constraints report

- status: WARN
- generated_at: 2026-05-07T04:18:44.110756+00:00
- git_commit: fcbad4f7fd70542596dcb7537dba4e7ea41a84c9
- config_hash: a5af602c8845d3132c8b301d7b6d36ff3b37dba4f6366f381c67eb5f5a1dea52

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

## execution funnel

- raw_buy_signal_count: 481
- unique_raw_buy_intent_count: 131
- repeat_raw_buy_intent_count: 350
- repeat_raw_buy_intent_ratio: 0.7276507276507277
- repeated_blocked_buy_signal_count: 350
- account_feasible_buy_signal_count: 168
- user_visible_buy_recommendation_count: 31
- user_visible_blocked_buy_count: 100
- pending_buy_intent_count: 35
- raw_sell_signal_count: 24
- executable_buy_count: 31
- executable_sell_count: 24
- executable_raw_buy_ratio: 0.06444906444906445
- executable_unique_raw_intent_ratio: 0.2366412213740458
- executable_account_feasible_buy_ratio: 0.18452380952380953
- full_portfolio_raw_buy_intent_count: 132
- full_portfolio_raw_buy_intent_ratio: 0.27442827442827444
- new_position_raw_intent_count: 443
- add_position_raw_intent_count: 38
- executable_new_position_buy_count: 27
- executable_add_buy_count: 3
- average_cash_ratio: 0.4814
- average_exposure: 0.5318
- max_exposure: 0.7060
- turnover: 134129.81

## denominator notes

- executable_raw_buy_ratio: executable_buy_count / raw_buy_signal_count
- executable_unique_raw_intent_ratio: executable_buy_count / unique_raw_buy_intent_count
- executable_account_feasible_buy_ratio: executable_buy_count / account_feasible_buy_signal_count
- repeat_raw_buy_intent_ratio: repeat_raw_buy_intent_count / raw_buy_signal_count
- full_portfolio_raw_buy_intent_ratio: full_portfolio_raw_buy_intent_count / raw_buy_signal_count
- max_positions_block_ratio: max_positions_block_count / raw_buy_signal_count
- cash_block_ratio: cash_block_count / raw_buy_signal_count; excludes CASH_INSUFFICIENT_FOR_ONE_LOT
- cash_liquidity_block_ratio: (cash_block_count + cash_insufficient_for_one_lot_count) / raw_buy_signal_count
- block_reason_breakdown.count_pct_of_raw: reason_code count / raw_buy_signal_count
- block_reason_breakdown.count_pct_of_blocked: reason_code count / total blocked_signals rows

## blocker ratios

- max_positions_block_count: 132
- max_positions_block_ratio: 0.27442827442827444
- price_too_high_for_account_lot_count: 46
- price_too_high_for_account_lot_ratio: 0.09563409563409564
- cash_insufficient_for_one_lot_count: 233
- cash_insufficient_for_one_lot_ratio: 0.48440748440748443
- lot_size_accumulation_required_count: 8
- lot_size_accumulation_required_ratio: 0.016632016632016633
- cash_block_count: 0
- cash_block_ratio: 0.0 (direct CASH_INSUFFICIENT only)
- cash_liquidity_block_count: 233
- cash_liquidity_block_ratio: 0.48440748440748443 (cash + one-lot cash blockers)

## block reason breakdown

| reason_code | count | pct_raw | pct_blocked | unique_symbols | trade_dates | dominant_bucket | examples | description |
|---|---:|---:|---:|---:|---:|---|---|---|
| CASH_INSUFFICIENT_FOR_ONE_LOT | 233 | 0.48440748440748443 | 0.516629711751663 | 14 | 96 | defensive_dividend | 000333.sz,600585.sh,600926.sh,601336.sh,601601.sh,601018.sh,000807.sz,300628.sz,600036.sh,600690.sh | 当前可用现金不足以买入一手。 |
| MAX_POSITIONS_LIMIT | 132 | 0.27442827442827444 | 0.2926829268292683 | 14 | 82 | defensive_dividend | 600176.sh,002532.sz,000001.sz,603799.sh,600926.sh,600027.sh,600011.sh,600585.sh,000708.sz,600426.sh | 组合已达到最大持仓数，新的买入意图被阻断。 |
| PRICE_TOO_HIGH_FOR_ACCOUNT_LOT | 46 | 0.09563409563409564 | 0.10199556541019955 | 3 | 43 | cyclical_rotation | 601021.sh,600309.sh,000333.sz | 按当前账户和单票上限，一手金额过高。 |
| PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY | 26 | 0.05405405405405406 | 0.057649667405764965 | 3 | 25 | defensive_dividend | 601318.sh,600233.sh,300628.sz | 剩余单票容量不足以容纳一手或目标加仓。 |
| LOT_SIZE_ACCUMULATION_REQUIRED | 8 | 0.016632016632016633 | 0.017738359201773836 | 1 | 8 | cyclical_rotation | 600018.sh | 加仓目标差额、现金或剩余单票容量尚未满足一手。 |
| DAILY_NEW_POSITION_LIMIT | 5 | 0.010395010395010396 | 0.011086474501108648 | 5 | 4 | defensive_dividend | 601318.sh,600999.sh,601021.sh,600036.sh,601838.sh | 当日新开仓数量达到上限。 |
| MIN_TRADE_AMOUNT | 1 | 0.002079002079002079 | 0.0022172949002217295 | 1 | 1 | cyclical_rotation | 600176.sh | 目标成交额低于最小成交额。 |

## blocker_counts

- CASH_INSUFFICIENT_FOR_ONE_LOT: 233
- DAILY_NEW_POSITION_LIMIT: 5
- LOT_SIZE_ACCUMULATION_REQUIRED: 8
- MAX_POSITIONS_LIMIT: 132
- MIN_TRADE_AMOUNT: 1
- PRICE_TOO_HIGH_FOR_ACCOUNT_LOT: 46
- PRICE_TOO_HIGH_FOR_REMAINING_CAPACITY: 26

## WARN

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.06444906444906445
