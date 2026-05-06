# release status consistency

- status: PASS
- expected_current_release_status: WARN
- generated_at: 2026-05-06T07:49:51.834936+00:00

## observed statuses

- reports/backtest/release/combined_v2_rc_manifest.json `status`: WARN
- reports/backtest/release/combined_v2_rc_manifest.md `status`: WARN
- reports/backtest/release/release_guard_report.md `overall_status`: WARN
- README.md `current_release_status`: WARN
- docs/project_status_2026-05-05.md `current_release_status`: WARN

## expected status reasons

- UNIVERSE_BELOW_TARGET: {'code': 'UNIVERSE_BELOW_TARGET', 'selected_count': 30, 'target_size': 36}
- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: {'code': 'ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION', 'actual': 0.03656597774244833}
- RETAIL_50K_EXECUTION_RATIO_BELOW_25: {'code': 'RETAIL_50K_EXECUTION_RATIO_BELOW_25', 'actual': 0.010480349344978166}
- CORE_SENSITIVITY_NON_BINDING: {'code': 'CORE_SENSITIVITY_NON_BINDING', 'parameters': ['defensive_valuation_threshold', 'grid_step', 'min_holding_days', 'universe_size']}
- MODULE_MAY_BE_DRAG: {'code': 'MODULE_MAY_BE_DRAG', 'modules': ['no_high_dividend_supplement', 'no_trend_stop', 'no_market_state_filter']}
- EVIDENCE_CHAIN_WARN: {'code': 'EVIDENCE_CHAIN_WARN', 'actual': 'WARN'}
- OBSERVATION_READINESS_NOT_READY: {'code': 'OBSERVATION_READINESS_NOT_READY', 'actual': 'NOT_READY'}

## violations

- none
