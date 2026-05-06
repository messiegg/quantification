# observation readiness report

- status: NOT_READY
- observation_trading_days: 0
- manual_review_required: true
- auto_trading_approved: false
- broker_integration_enabled: false
- llm_decision_allowed: false

## runtime profile

- account_profile: retail_50k_lot_aware
- initial_capital: 50000.0
- min_trade_value: 1500.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 8
- portfolio_equal_weight_target_positions: 8

## checks

- WARN | READY-OBS-DAYS | expected=60 | actual=0
- WARN | READY-MANUAL-LOG | expected=manual review log exists | actual=missing
- PASS | READY-HARD-FAILS | expected=0 | actual=0
- PASS | READY-SENS-UNKNOWN | expected=0 | actual=0
- PASS | READY-SENS-NOT-WIRED | expected=0 | actual=0
- WARN | READY-EXEC-RATIO | expected=0.25 | actual=0.03656597774244833
- PASS | READY-EVIDENCE-CHAIN | expected=evidence chain present | actual=present

## not ready reasons

- READY-OBS-DAYS: actual=0
- READY-MANUAL-LOG: actual=missing
- READY-EXEC-RATIO: actual=0.03656597774244833
