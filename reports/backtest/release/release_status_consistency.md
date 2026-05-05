# release status consistency

- status: PASS
- expected_current_release_status: WARN
- generated_at: 2026-05-05T12:45:59.485549+00:00

## observed statuses

- reports/backtest/release/combined_v2_rc_manifest.json `status`: WARN
- reports/backtest/release/combined_v2_rc_manifest.md `status`: WARN
- reports/backtest/release/release_guard_report.md `overall_status`: WARN
- README.md `current_release_status`: WARN
- docs/project_status_2026-05-05.md `current_release_status`: WARN

## expected status reasons

- UNIVERSE_BELOW_TARGET: {'code': 'UNIVERSE_BELOW_TARGET', 'selected_count': 30, 'target_size': 36}
- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: {'code': 'ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION', 'actual': 0.11621621621621622}
- CORE_SENSITIVITY_NON_BINDING: {'code': 'CORE_SENSITIVITY_NON_BINDING', 'parameters': ['cyclical_pb_threshold', 'defensive_valuation_threshold', 'grid_step', 'universe_size']}
- MODULE_MAY_BE_DRAG: {'code': 'MODULE_MAY_BE_DRAG', 'modules': ['no_high_dividend_supplement', 'no_trend_stop', 'no_market_state_filter']}
- EVIDENCE_CHAIN_WARN: {'code': 'EVIDENCE_CHAIN_WARN', 'actual': 'WARN'}
- OBSERVATION_READINESS_NOT_READY: {'code': 'OBSERVATION_READINESS_NOT_READY', 'actual': 'NOT_READY'}

## violations

- none
