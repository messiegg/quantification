# observation 同步审计

## 汇总

- ADD_TO_GIT: 25
- IGNORE_LOCAL_ONLY: 3
- KEEP_TRACKED: 3

## 文件明细

- KEEP_TRACKED | .gitignore | exists=True | tracked=True | ignored=False | 发布和复现所需文件，已被 Git 跟踪。
- KEEP_TRACKED | README.md | exists=True | tracked=True | ignored=False | 发布和复现所需文件，已被 Git 跟踪。
- ADD_TO_GIT | config/observation.yml | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | data/observation/.gitkeep | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- IGNORE_LOCAL_ONLY | data/observation/paper_account.yml | exists=True | tracked=False | ignored=True | 真实纸面账本是本地持续变化产物，不提交公开仓库。
- IGNORE_LOCAL_ONLY | data/observation/paper_positions.yml | exists=True | tracked=False | ignored=True | 真实纸面账本是本地持续变化产物，不提交公开仓库。
- IGNORE_LOCAL_ONLY | data/observation/paper_trades.csv | exists=True | tracked=False | ignored=True | 真实纸面账本是本地持续变化产物，不提交公开仓库。
- ADD_TO_GIT | docs/combined_v2_rc_acceptance.md | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | docs/data_freshness_and_runbook.md | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | docs/manual_observation_protocol.md | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | fixtures/observation/paper_account.example.yml | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | fixtures/observation/paper_positions.example.yml | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | fixtures/observation/paper_trades.example.csv | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | reports/backtest/audit/stale_report_check.csv | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | reports/backtest/audit/stale_report_check.md | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | reports/backtest/release/combined_v2_rc_code_manifest.json | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | reports/backtest/release/combined_v2_rc_verify.csv | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | reports/backtest/release/combined_v2_rc_verify.md | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | reports/backtest/release/observation_sync_check.csv | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | reports/backtest/release/observation_sync_check.md | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | reports/observation/2026-05-04/data_freshness_report.json | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | reports/observation/2026-05-04/data_freshness_report.md | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | reports/observation/2026-05-04/observation_blocked.md | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | reports/observation/2026-05-04/observation_run_manifest.json | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | scripts/check_data_freshness.py | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | scripts/check_report_freshness.py | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | scripts/run_observation_pipeline.py | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | scripts/update_paper_observation.py | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | scripts/verify_combined_v2_rc.py | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- ADD_TO_GIT | tests/test_observation_pipeline.py | exists=True | tracked=False | ignored=False | 发布和复现所需文件，当前未跟踪，需要 git add。
- KEEP_TRACKED | tests/test_release_candidate_consistency.py | exists=True | tracked=True | ignored=False | 发布和复现所需文件，已被 Git 跟踪。
