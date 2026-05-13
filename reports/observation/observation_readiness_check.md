# observation readiness smoke check

- status: READY_FOR_OBSERVATION
- manifest_status: WARN
- default_account_profile: retail_50k_lot_aware
- rc_verify_status: PASS
- rc_verify_fail_count: 0
- release_guard_status: WARN
- release_guard_fail_count: 0
- code_hash_drift: false
- config_hash_drift: false
- manual_review_required: true
- paper_trading_only: true
- release_pass_approved: false
- auto_trading_approved: false
- broker_integration_enabled: false
- llm_decision_allowed: false

READY_FOR_OBSERVATION only means the existing reports are internally consistent enough for manual observation/paper trading. It is not release PASS and not live-trading approval.

## checks

- PASS | OBS-FILE-MANIFEST | expected=manifest exists | actual=/Users/meseg/shu/stocks/quantile/reports/backtest/release/combined_v2_rc_manifest.json
- PASS | OBS-FILE-VERIFY | expected=verify csv exists | actual=/Users/meseg/shu/stocks/quantile/reports/backtest/release/combined_v2_rc_verify.csv
- PASS | OBS-FILE-GUARD | expected=release guard csv exists | actual=/Users/meseg/shu/stocks/quantile/reports/backtest/release/release_guard_report.csv
- PASS | OBS-MANIFEST-STATUS | expected=['PASS_CANDIDATE', 'WARN'] | actual=WARN
- PASS | OBS-DEFAULT-ACCOUNT | expected=['actual_50k_lot_aware', 'retail_50k_lot_aware'] | actual=retail_50k_lot_aware
- PASS | OBS-RC-VERIFY-PASS | expected=PASS | actual=PASS
- PASS | OBS-RC-VERIFY-NO-FAIL | expected=0 | actual=0
- PASS | OBS-RELEASE-GUARD-NO-FAIL | expected=0 | actual=0
- PASS | OBS-CODE-HASH-DRIFT | expected=no code drift | actual=none
- PASS | OBS-CONFIG-HASH-DRIFT | expected=no config drift | actual=none
- PASS | OBS-SAFETY-BOUNDARY | expected=manual-only; no broker; no LLM decisions | actual={'auto_trading_approved': False, 'broker_integration_enabled': False, 'llm_decision_allowed': False}

## not ready reasons

- none
