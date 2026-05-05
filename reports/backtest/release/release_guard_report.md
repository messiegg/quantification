# release guard report

- overall_status: WARN
- as_of_date: 2026-05-04
- mode: ci
- strict: false
- fail_count: 0
- warn_count: 6

## checks

- PASS | MODE-001 | release guard mode | actual=ci hash-only checks | evidence=scripts/run_release_guard.py | CI 模式不重跑完整回测，不写行情数据，不生成真实订单。
- PASS | RG-CONFIG-001 | config consistency audit | actual=PASS | evidence=scripts/audit_config_consistency.py | 运行配置之间冲突必须 FAIL；README 冲突只作为 DOC_MISMATCH WARN。
- WARN | RG-UNIVERSE-001 | universe integrity audit | actual=WARN | evidence=scripts/audit_universe_integrity.py | 股票池低于 floor、突破硬过滤或 override 无依据时必须 FAIL。
- PASS | RG-DATA-001 | data freshness audit | actual=PASS | evidence=scripts/audit_data_freshness.py | target_trade_date 晚于数据 asof 时必须 FAIL。
- WARN | RG-ACCOUNT-001 | account constraints report | actual=WARN | evidence=scripts/build_account_constraints_report.py | 账户约束 WARN 不自动阻断 release，但必须进入 manifest risk section.
- WARN | RG-EVIDENCE-001 | observation evidence chain | actual=WARN | evidence=scripts/build_observation_evidence_chain.py | 若 observation/release 声称可执行，必须同时存在 evidence_chain。
- PASS | RG-LOOKAHEAD-001 | lookahead audit has no confirmed violations | actual=0 | evidence=reports/backtest/audit/lookahead_audit.csv | 前视审计缺失或存在 confirmed violation 时，release 必须 FAIL。
- WARN | RG-SENS-001 | sensitivity report binds or classifies core parameters | actual=status=WARN; mode=ci; non_binding=4; unknown=0; errors=0 | evidence=reports/backtest/robustness/sensitivity_report.json | release guard 只认可 --mode ci 结果；参数变化未绑定、计算 ERROR 或原因 UNKNOWN 不能计入鲁棒性 PASS。
- WARN | RG-BASELINE-001 | baseline comparison report exists and is not failing | actual=WARN | evidence=reports/backtest/controls/baseline_comparison.json | 必须区分 documented dianjinshu-like baseline、combined_v2 和模块消融。
- PASS | RG-TESTS-001 | latest pytest status is recorded | actual=PASS | evidence=reports/backtest/release/test_status.json | release manifest 必须记录本轮自动化测试状态；缺失时 fail closed。
- PASS | RG-001 | report freshness check | actual=PASS=14 WARN=0 FAIL=0 | evidence=scripts/check_report_freshness.py | 刷新有旧口径或自相矛盾的报告。
- PASS | RG-002 | release sync consistency check | actual=PASS=31 WARN=0 FAIL=0 | evidence=scripts/check_release_sync_consistency.py | 发布同步报告不得含过期结论。
- PASS | RG-003 | report path sanitization check | actual=PASS=40 WARN=0 FAIL=0 | evidence=scripts/check_report_path_sanitization.py | 公开报告不得包含本机路径或 secret。
- PASS | RG-004 | observation gate consistency check | actual=PASS=13 WARN=0 FAIL=0 | evidence=scripts/check_observation_gate_consistency.py | observation allowed/blocked 状态必须一致。
- WARN | RG-005 | combined_v2 RC hash-only verification | actual=PASS=18 WARN=6 FAIL=0 | evidence=scripts/verify_combined_v2_rc.py --mode hash-only | CI 只验证 manifest/hash/已提交小型报告，不重跑完整回测。
- PASS | RG-006 | forbidden tracked files check | actual=PASS=6 WARN=0 FAIL=0 | evidence=scripts/check_forbidden_tracked_files.py | 移除大体量数据、真实账本、订单文件或 secret。
- PASS | GIT-MANUAL-001 | manual order and action files are not tracked | actual=none | evidence=git ls-files reports/observation/* action/manual pathspecs | 手工清单和 actions 是本地观察产物，不得进入公开提交。
- PASS | GIT-LEDGER-001 | real paper ledger files are not tracked | actual=none | evidence=git ls-files data/observation/paper_* | 真实 paper ledger 必须保持本地 ignored，只提交 fixtures/observation 示例模板。
- PASS | OBS-CONFLICT-001 | observation report does not keep allowed and blocked current reports together | actual=allowed=True; summary_exists=True; blocked_current=False | evidence=reports/observation/2026-05-04 | freshness 允许观察时，当前主路径不得同时保留 blocked 报告。
- PASS | OBS-WORDING-001 | observation summary has no active execution wording | actual=none | evidence=reports/observation/2026-05-04/observation_summary.md | 观察报告只能作为手工复核材料，不得写成今日实盘执行或自动下单。
- PASS | CFG-HASH-strategy_v2 | config/strategy_v2.yml hash matches RC manifest | actual=7957dae7b8671c0c19cad3712f02d642e684a8be3c445f73c8b32455543c7ccb | evidence=config/strategy_v2.yml | 配置 hash 漂移意味着 RC 口径不再冻结，必须停止发布。
- PASS | CFG-HASH-universe_rules_v2 | config/universe_rules_v2.yml hash matches RC manifest | actual=edf1b3ed04cd63dca1ca546f1a07641e84e1f3808aac166abef34e895264c2a8 | evidence=config/universe_rules_v2.yml | 配置 hash 漂移意味着 RC 口径不再冻结，必须停止发布。
