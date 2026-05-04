# release sync consistency check

- overall_status: PASS
- generated_at: 2026-05-04T10:30:50.307083+00:00
- fail_count: 0
- warn_count: 0

任一 FAIL 时，不能把发布同步状态视为完成。

## checks

- PASS | SYNC-MD-001 | observation_sync_check.md stale phrase absent | actual=absent | 重新生成 observation_sync_check.md，确保报告来自当前 Git 跟踪状态。
- PASS | SYNC-MD-002 | observation_sync_check.md stale phrase absent | actual=absent | 重新生成 observation_sync_check.md，确保报告来自当前 Git 跟踪状态。
- PASS | SYNC-MD-003 | observation_sync_check.md stale phrase absent | actual=absent | 重新生成 observation_sync_check.md，确保报告来自当前 Git 跟踪状态。
- PASS | SYNC-MD-004 | observation_sync_check.md stale phrase absent | actual=absent | 重新生成 observation_sync_check.md，确保报告来自当前 Git 跟踪状态。
- PASS | SUMMARY-MD-001 | observation_release_sync_summary.md old conclusion absent | actual=absent | 刷新发布同步总结，避免提交前状态结论进入发布分支。
- PASS | SUMMARY-MD-002 | observation_release_sync_summary.md old conclusion absent | actual=absent | 刷新发布同步总结，避免提交前状态结论进入发布分支。
- PASS | SUMMARY-MD-003 | observation_release_sync_summary.md old conclusion absent | actual=absent | 刷新发布同步总结，避免提交前状态结论进入发布分支。
- PASS | SUMMARY-MD-004 | observation_release_sync_summary.md old conclusion absent | actual=absent | 刷新发布同步总结，避免提交前状态结论进入发布分支。
- PASS | SUMMARY-MD-005 | observation_release_sync_summary.md old conclusion absent | actual=absent | 刷新发布同步总结，避免提交前状态结论进入发布分支。
- PASS | SUMMARY-MD-006 | observation_release_sync_summary.md old conclusion absent | actual=absent | 刷新发布同步总结，避免提交前状态结论进入发布分支。
- PASS | SYNC-CSV-FORBIDDEN-ACTION-1 | observation_sync_check.csv forbidden action count | actual=0 | 当前发布同步报告不得要求补 git add 或人工调查。
- PASS | SYNC-CSV-FORBIDDEN-ACTION-2 | observation_sync_check.csv forbidden action count | actual=0 | 当前发布同步报告不得要求补 git add 或人工调查。
- PASS | SYNC-CSV-LEDGER-paper_account | data/observation/paper_account.yml action | actual=IGNORE_LOCAL_ONLY | 真实 paper ledger 必须保持本地忽略，不进入公开提交。
- PASS | SYNC-CSV-LEDGER-paper_trades | data/observation/paper_trades.csv action | actual=IGNORE_LOCAL_ONLY | 真实 paper ledger 必须保持本地忽略，不进入公开提交。
- PASS | SYNC-CSV-LEDGER-paper_positions | data/observation/paper_positions.yml action | actual=IGNORE_LOCAL_ONLY | 真实 paper ledger 必须保持本地忽略，不进入公开提交。
- PASS | SYNC-CSV-TRACKED-observation.yml | config/observation.yml action | actual=KEEP_TRACKED | 发布和复现所需文件必须保持 Git 跟踪。
- PASS | SYNC-CSV-TRACKED-verify_combined_v2_rc.py | scripts/verify_combined_v2_rc.py action | actual=KEEP_TRACKED | 发布和复现所需文件必须保持 Git 跟踪。
- PASS | SYNC-CSV-TRACKED-run_observation_pipeline.py | scripts/run_observation_pipeline.py action | actual=KEEP_TRACKED | 发布和复现所需文件必须保持 Git 跟踪。
- PASS | SYNC-CSV-TRACKED-manual_observation_protocol.md | docs/manual_observation_protocol.md action | actual=KEEP_TRACKED | 发布和复现所需文件必须保持 Git 跟踪。
- PASS | SUMMARY-REQ-001 | observation_release_sync_summary.md required current conclusion | actual=present | 发布同步总结必须保留 stale data 阻断、RC PASS 和禁止手工订单结论。
- PASS | SUMMARY-REQ-002 | observation_release_sync_summary.md required current conclusion | actual=present | 发布同步总结必须保留 stale data 阻断、RC PASS 和禁止手工订单结论。
- PASS | SUMMARY-REQ-003 | observation_release_sync_summary.md required current conclusion | actual=present | 发布同步总结必须保留 stale data 阻断、RC PASS 和禁止手工订单结论。
- PASS | SUMMARY-REQ-004 | observation_release_sync_summary.md required current conclusion | actual=present | 发布同步总结必须保留 stale data 阻断、RC PASS 和禁止手工订单结论。
- PASS | SUMMARY-REQ-005 | observation_release_sync_summary.md required current conclusion | actual=present | 发布同步总结必须保留 stale data 阻断、RC PASS 和禁止手工订单结论。
