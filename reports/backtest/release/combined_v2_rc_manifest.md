# combined_v2 RC manifest

- status: FAIL
- branch: codex/combined-v2-rc-release
- git_commit: f0cd73e15a915b7af4373421dbb57797de0dea83
- generated_at: 2026-05-05T09:09:37.143764+00:00
- config_hash: f5d49ea7f9c40f4eb3708c86ba3cc84b5c4b7dea513e7002602215c025dce616
- data_hash: b51fa02fe73514c8b49ebb4f7697840fecaa3a75f648afab04beb1c7d98106bf
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
- universe_integrity: FAIL
- data_freshness: PASS
- account_constraints: WARN
- evidence_chain: FAIL

## risk section

- ACCOUNT_CONSTRAINTS_DOMINATE_BUY_EXECUTION: account constraints dominate buy execution actual=0.11621621621621622
- MIN_TRADE_AMOUNT_DOMINATES_EXECUTION: min_trade_amount dominates execution actual=0.5945945945945946

## release guard checks

- PASS | MODE-001 | release guard mode | actual=ci hash-only checks
- PASS | RG-CONFIG-001 | config consistency audit | actual=PASS
- FAIL | RG-UNIVERSE-001 | universe integrity audit | actual=FAIL
- PASS | RG-DATA-001 | data freshness audit | actual=PASS
- WARN | RG-ACCOUNT-001 | account constraints report | actual=WARN
- FAIL | RG-EVIDENCE-001 | observation evidence chain | actual=FAIL
- PASS | RG-LOOKAHEAD-001 | lookahead audit has no confirmed violations | actual=0
- FAIL | RG-SENS-001 | sensitivity report binds or classifies core parameters | actual=status=FAIL; non_binding=0; unknown=0
- FAIL | RG-BASELINE-001 | baseline comparison report exists and is not failing | actual=FAIL
- PASS | RG-TESTS-001 | latest pytest status is recorded | actual=PASS
- FAIL | RG-001 | report freshness check | actual=PASS=8 WARN=0 FAIL=5
- PASS | RG-002 | release sync consistency check | actual=PASS=27 WARN=0 FAIL=0
- PASS | RG-003 | report path sanitization check | actual=PASS=37 WARN=0 FAIL=0
- FAIL | RG-004 | observation gate consistency check | actual=PASS=3 WARN=0 FAIL=4
- WARN | RG-005 | combined_v2 RC hash-only verification | actual=PASS=18 WARN=6 FAIL=0
- PASS | RG-006 | forbidden tracked files check | actual=PASS=6 WARN=0 FAIL=0
- PASS | GIT-MANUAL-001 | manual order and action files are not tracked | actual=none
- PASS | GIT-LEDGER-001 | real paper ledger files are not tracked | actual=none
- PASS | OBS-CONFLICT-001 | observation report does not keep allowed and blocked current reports together | actual=allowed=True; summary_exists=False; blocked_current=True
- PASS | OBS-WORDING-001 | observation summary has no active execution wording | actual=none
- PASS | CFG-HASH-strategy_v2 | config/strategy_v2.yml hash matches RC manifest | actual=7957dae7b8671c0c19cad3712f02d642e684a8be3c445f73c8b32455543c7ccb
- PASS | CFG-HASH-universe_rules_v2 | config/universe_rules_v2.yml hash matches RC manifest | actual=edf1b3ed04cd63dca1ca546f1a07641e84e1f3808aac166abef34e895264c2a8
