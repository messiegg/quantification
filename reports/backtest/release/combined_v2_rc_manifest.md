# combined_v2 RC manifest

- status: WARN
- branch: codex/cleanup-stale-artifacts
- git_commit: c368f718e365edd1ce6ad8f2bd9bb6bc8a074cad
- generated_at: 2026-05-06T07:49:51.887765+00:00
- config_hash: 77fab057ca5cee090e85267b1dc7d0bf4e489f66913f3cc2ace187529a0373f7
- data_hash: c6a0a1d723bdacc2afc0d397ee004a858ddb729d4c7e0f1cdc0ee4b33a1444c1
- requested_date: 2026-05-04
- target_trade_date: 2026-04-30
- account_profile: retail_50k_lot_aware
- lot_aware_sizing_enabled: true
- initial_capital: 50000.0
- min_trade_value: 1500.0
- round_lot: 100
- raw_buy_signal_count: 629
- unique_raw_buy_intent_count: 159
- executable_buy_count: 23
- executable_raw_buy_ratio: 0.03656597774244833
- executable_account_feasible_buy_ratio: 0.0539906103286385
- lot_size_zero_block_count: 0
- price_too_high_for_account_lot_count: 30
- repeated_blocked_buy_signal_count: 470
- pending_buy_intent_count: 47
- portfolio_max_positions: 8
- portfolio_equal_weight_target_positions: 8
- universe_target_size: 36
- universe_selected_count: 30
- account_profile_comparison_status: WARN
- market_data_asof: 2026-04-30
- feature_data_asof: 2026-04-30
- benchmark_data_asof: 2026-04-30
- manual_review_required: true
- auto_trading_approved: false
- broker_integration_enabled: false
- llm_decision_allowed: false
- release_scope: 小资金、手动、严格复核观察/试运行候选；不是自动交易批准。

## audit statuses

- config_consistency: PASS
- universe_integrity: WARN
- universe_shortfall: WARN
- data_freshness: PASS
- account_constraints: WARN
- account_suitability: WARN
- account_profile_comparison: WARN
- evidence_chain: WARN
- sensitivity: WARN
- sensitivity_trigger_coverage: WARN
- baseline_comparison: WARN
- module_contribution: WARN
- observation_readiness: NOT_READY
- release_status_consistency: PASS

## risk section

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.03656597774244833
- universe_shortfall_to_target: 6
- account_suitability_base_executable_raw_buy_ratio: 0.03656597774244833
- observation_readiness_status: NOT_READY
- sensitivity universe_size: NO_SIGNAL_COVERAGE
- sensitivity defensive_valuation_threshold: NO_SIGNAL_COVERAGE
- sensitivity min_holding_days: NO_SIGNAL_COVERAGE
- sensitivity grid_step: NO_SIGNAL_COVERAGE
- module high_dividend_supplement: POSSIBLE_DRAG
- module trend_stop: POSSIBLE_DRAG
- module market_state_filter: RISK_REDUCER

## release guard checks

- PASS | MODE-001 | release guard mode | actual=ci hash-only checks
- PASS | RG-CONFIG-001 | config consistency audit | actual=PASS
- WARN | RG-UNIVERSE-001 | universe integrity audit | actual=WARN
- WARN | RG-UNIVERSE-002 | universe shortfall explanation | actual=WARN
- PASS | RG-DATA-001 | data freshness audit | actual=PASS
- WARN | RG-ACCOUNT-001 | account constraints report | actual=WARN
- WARN | RG-ACCOUNT-002 | account suitability report | actual=WARN
- WARN | RG-ACCOUNT-003 | account profile comparison uses configured default profile | actual=default=actual_50k_lot_aware; ratio=0.03656597774244833; report_status=WARN
- WARN | RG-EVIDENCE-001 | observation evidence chain | actual=WARN
- PASS | RG-LOOKAHEAD-001 | lookahead audit has no confirmed violations | actual=0
- WARN | RG-SENS-001 | sensitivity report binds or classifies core parameters | actual=status=WARN; mode=ci; non_binding=4; unknown=0; errors=0
- WARN | RG-SENS-002 | sensitivity trigger coverage | actual=WARN
- WARN | RG-BASELINE-001 | baseline comparison report exists and is not failing | actual=WARN
- WARN | RG-BASELINE-002 | module contribution report | actual=WARN
- PASS | RG-TESTS-001 | latest pytest status is recorded | actual=PASS
- PASS | RG-001 | report freshness check | actual=PASS=14 WARN=0 FAIL=0
- PASS | RG-002 | release sync consistency check | actual=PASS=31 WARN=0 FAIL=0
- PASS | RG-003 | report path sanitization check | actual=PASS=41 WARN=0 FAIL=0
- PASS | RG-004 | observation gate consistency check | actual=PASS=13 WARN=0 FAIL=0
- WARN | RG-005 | combined_v2 RC hash-only verification | actual=PASS=22 WARN=10 FAIL=0
- PASS | RG-006 | forbidden tracked files check | actual=PASS=6 WARN=0 FAIL=0
- PASS | GIT-MANUAL-001 | manual order and action files are not tracked | actual=none
- PASS | GIT-LEDGER-001 | real paper ledger files are not tracked | actual=none
- PASS | OBS-CONFLICT-001 | observation report does not keep allowed and blocked current reports together | actual=allowed=True; summary_exists=True; blocked_current=False
- PASS | OBS-WORDING-001 | observation summary has no active execution wording | actual=none
- WARN | RG-READY-001 | observation readiness policy | actual=NOT_READY
- PASS | CFG-HASH-strategy_v2 | config/strategy_v2.yml hash matches RC manifest | actual=eec5115615258c7c9f1e189d1da1a013dd86d9156d86f7f6dc5aa9f7858920f9
- PASS | CFG-HASH-universe_rules_v2 | config/universe_rules_v2.yml hash matches RC manifest | actual=edf1b3ed04cd63dca1ca546f1a07641e84e1f3808aac166abef34e895264c2a8
- PASS | RG-STATUS-001 | release status consistency | actual=WARN
