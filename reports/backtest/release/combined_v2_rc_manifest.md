# combined_v2 RC manifest

- status: WARN
- branch: codex/combined-v2-rc-release
- git_commit: 2d64f444960ceb631de8430a8f406b14d0703010
- generated_at: 2026-05-05T12:45:59.530475+00:00
- config_hash: 737f7484fbffc7d8084cd990831e73048187ea298be039a784f0a2550145d8d2
- data_hash: 2d3b46f11646b501ccf291979d554e3216c3199b8735ade5126a398552fb469b
- requested_date: 2026-05-04
- target_trade_date: 2026-04-30
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
- evidence_chain: WARN
- sensitivity: WARN
- sensitivity_trigger_coverage: WARN
- baseline_comparison: WARN
- module_contribution: WARN
- observation_readiness: NOT_READY
- release_status_consistency: PASS

## risk section

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.11621621621621622
- MIN_TRADE_AMOUNT_DOMINATES_EXECUTION: min_trade_amount dominates execution actual=0.5945945945945946
- universe_shortfall_to_target: 6
- account_suitability_base_executable_raw_buy_ratio: 0.11621621621621622
- observation_readiness_status: NOT_READY
- sensitivity universe_size: NO_SIGNAL_COVERAGE
- sensitivity defensive_valuation_threshold: NO_SIGNAL_COVERAGE
- sensitivity cyclical_pb_threshold: NO_SIGNAL_COVERAGE
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
- WARN | RG-005 | combined_v2 RC hash-only verification | actual=PASS=20 WARN=10 FAIL=0
- PASS | RG-006 | forbidden tracked files check | actual=PASS=6 WARN=0 FAIL=0
- PASS | GIT-MANUAL-001 | manual order and action files are not tracked | actual=none
- PASS | GIT-LEDGER-001 | real paper ledger files are not tracked | actual=none
- PASS | OBS-CONFLICT-001 | observation report does not keep allowed and blocked current reports together | actual=allowed=True; summary_exists=True; blocked_current=False
- PASS | OBS-WORDING-001 | observation summary has no active execution wording | actual=none
- WARN | RG-READY-001 | observation readiness policy | actual=NOT_READY
- PASS | CFG-HASH-strategy_v2 | config/strategy_v2.yml hash matches RC manifest | actual=7957dae7b8671c0c19cad3712f02d642e684a8be3c445f73c8b32455543c7ccb
- PASS | CFG-HASH-universe_rules_v2 | config/universe_rules_v2.yml hash matches RC manifest | actual=edf1b3ed04cd63dca1ca546f1a07641e84e1f3808aac166abef34e895264c2a8
- PASS | RG-STATUS-001 | release status consistency | actual=WARN
