# 50k 整手可买性报告

- status: WARN
- as_of_date: 2026-04-03
- account_profile: retail_50k_lot_aware
- initial_capital: 50000.0
- min_trade_value: 1500.0
- round_lot: 100
- max_single_position_value: 6000.0
- target_position_value: 6250.0

## breakdown

- universe_count: 31
- execution_eligible_for_new_buy_count: 28
- price_too_high_for_50k_lot_count: 3
- cash_insufficient_for_one_lot_count: 0

## execution ineligible

- 600309.sh 万华化学: lot_notional=8238.00, max_single=6000.00, reason=PRICE_TOO_HIGH_FOR_ACCOUNT_LOT
- 002460.sz 赣锋锂业: lot_notional=7975.00, max_single=6000.00, reason=PRICE_TOO_HIGH_FOR_ACCOUNT_LOT
- 600941.sh 中国移动: lot_notional=9302.00, max_single=6000.00, reason=PRICE_TOO_HIGH_FOR_ACCOUNT_LOT
