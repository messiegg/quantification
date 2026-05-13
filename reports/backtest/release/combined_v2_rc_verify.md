# combined_v2 RC verify

- overall_status: PASS
- mode: hash-only
- profile: combined_v2
- execution_mode: next_bar
- period: 2023-04-03 to 2026-04-03
- annual_return: 0.0248462204114119
- cumulative_return: 0.0732656206920001
- max_drawdown: -0.0887660570697639
- total_trades: 41
- final_nav: 53663.281034600004

## checks

- PASS | MODE-001 | verification mode | expected=hash-only | actual=hash-only | hash-only 使用已提交的小型报告与 manifest，不重跑完整回测；full 仅用于本地完整数据环境。
- PASS | CFG-002 | config/strategy_v2.yml sha256 matches RC manifest | expected=2b7e55141e2629ffe9a1385794eeaa026bbb50757d8de43d9f12e46b97257f3b | actual=2b7e55141e2629ffe9a1385794eeaa026bbb50757d8de43d9f12e46b97257f3b | 配置未漂移。
- PASS | CFG-003 | config/universe_rules_v2.yml sha256 matches RC manifest | expected=edf1b3ed04cd63dca1ca546f1a07641e84e1f3808aac166abef34e895264c2a8 | actual=edf1b3ed04cd63dca1ca546f1a07641e84e1f3808aac166abef34e895264c2a8 | 配置未漂移。
- PASS | MET-annual_return | annual_return strict RC metric | expected=0.024846220411411934 | actual=0.0248462204114119 | annual_return 必须在容差 1e-10 内复现。
- PASS | MET-cumulative_return | cumulative_return strict RC metric | expected=0.07326562069200016 | actual=0.0732656206920001 | cumulative_return 必须在容差 1e-10 内复现。
- PASS | MET-max_drawdown | max_drawdown strict RC metric | expected=-0.08876605706976393 | actual=-0.0887660570697639 | max_drawdown 必须在容差 1e-10 内复现。
- PASS | MET-final_nav | final_nav strict RC metric | expected=53663.281034600004 | actual=53663.281034600004 | final_nav 必须在容差 1e-06 内复现。
- PASS | MET-total_trades | total_trades strict RC metric | expected=41 | actual=41 | total_trades 必须等于 41。
- PASS | OUT-001 | combined_v2 trades detailed hash | expected=34a6eaaddba006b4122093ee0932e47bc094fa9e8e605ca8c3a43ac1af7f05a9 | actual=34a6eaaddba006b4122093ee0932e47bc094fa9e8e605ca8c3a43ac1af7f05a9 | 交易明细文件 hash 漂移但严格指标一致时标记 WARN；若指标也漂移则整体 FAIL。
- PASS | OUT-010 | config/account.yml key output hash | expected=6482e45ec46ba0609ecf5fa9ca7069fe3a586a017843bf0947239e79728322fd | actual=6482e45ec46ba0609ecf5fa9ca7069fe3a586a017843bf0947239e79728322fd | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-011 | config/metric_map.yml key output hash | expected=5d01eaf16b945566c3686dd66fd2c52f6184ee7afa2712890571982fd35901ce | actual=5d01eaf16b945566c3686dd66fd2c52f6184ee7afa2712890571982fd35901ce | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-012 | config/observation.yml key output hash | expected=d8c632ef4363e733065213a98a8b9b328b87281745ec7cd67d98582448b6e31b | actual=d8c632ef4363e733065213a98a8b9b328b87281745ec7cd67d98582448b6e31b | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-013 | config/observation_readiness.yml key output hash | expected=d3cd1f8ab42f5cc939b809ea9091af5c8ade3e2e8827c5a5235b779a3866d8ce | actual=d3cd1f8ab42f5cc939b809ea9091af5c8ade3e2e8827c5a5235b779a3866d8ce | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-014 | reports/audit/config_consistency.json key output hash | expected=0106bea7084d0f25deaf00b8d93bc1d4221bed236667ed82c22eaa3a5c51eae3 | actual=0106bea7084d0f25deaf00b8d93bc1d4221bed236667ed82c22eaa3a5c51eae3 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-015 | reports/audit/data_freshness.json key output hash | expected=a6f695ae50d2e34e1e276bc94af4f53b5487a9f2e340a4b6d314c9a010fa7edb | actual=a6f695ae50d2e34e1e276bc94af4f53b5487a9f2e340a4b6d314c9a010fa7edb | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-016 | reports/audit/universe_integrity.json key output hash | expected=99fdeff376ffb75c475ec5401c10f892a7735346268373c05eca70fb2fba9290 | actual=99fdeff376ffb75c475ec5401c10f892a7735346268373c05eca70fb2fba9290 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-017 | reports/audit/universe_shortfall.json key output hash | expected=0cb8017e95adf16afafcf5c990325708353530d6905dd9b7a0423b014709e875 | actual=0cb8017e95adf16afafcf5c990325708353530d6905dd9b7a0423b014709e875 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-018 | reports/backtest/account_constraints_report.json key output hash | expected=6675c7ecffb99a3989c6d887053b56f592b52f495a89eaac755d5614dc47312a | actual=6675c7ecffb99a3989c6d887053b56f592b52f495a89eaac755d5614dc47312a | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-019 | reports/backtest/account_profiles/account_profile_comparison.json key output hash | expected=628f52665ec092bc3b15bc6c5a840ffce205bb658e6408982aadf4a99cd4c664 | actual=628f52665ec092bc3b15bc6c5a840ffce205bb658e6408982aadf4a99cd4c664 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-020 | reports/backtest/account_suitability_report.json key output hash | expected=459209785ba31c664fdd4d96f36ccdb7837fa8b2507e47fdda5cac0347e8b444 | actual=459209785ba31c664fdd4d96f36ccdb7837fa8b2507e47fdda5cac0347e8b444 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-021 | reports/backtest/audit/integrity_audit.csv key output hash | expected=4df2259561eaaa487c1ee8037e4803d819ad3173f007ea74ae55efae3b66ea17 | actual=4df2259561eaaa487c1ee8037e4803d819ad3173f007ea74ae55efae3b66ea17 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-022 | reports/backtest/audit/lookahead_audit.csv key output hash | expected=4984aa99257da132f0fd2b622faa3bb976b8ad91a6b1878f94858dca27d1f8a6 | actual=4984aa99257da132f0fd2b622faa3bb976b8ad91a6b1878f94858dca27d1f8a6 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-023 | reports/backtest/combined_v2_candidate_scores.csv key output hash | expected=e73c8e531d8777ee511d657241d689196a61e7dd62c8b6db3e8ad45b6d9b97bc | actual=e73c8e531d8777ee511d657241d689196a61e7dd62c8b6db3e8ad45b6d9b97bc | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-024 | reports/backtest/combined_v2_retail_50k_metrics.csv key output hash | expected=e0bc24922d92f449256c0ed3660a65bf0ec1f38ff0362ec80f318790353ad2c6 | actual=e0bc24922d92f449256c0ed3660a65bf0ec1f38ff0362ec80f318790353ad2c6 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-025 | reports/backtest/combined_v2_signal_funnel.csv key output hash | expected=d4ea5b59f5af7d927fefc3dcc03f2b2568a4aa253eac72baa4458adc46b73eae | actual=d4ea5b59f5af7d927fefc3dcc03f2b2568a4aa253eac72baa4458adc46b73eae | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-026 | reports/backtest/controls/baseline_comparison.json key output hash | expected=6631e90bbd549967ca254a334bc563e184b0af7072c270c480236d6f2850a3c6 | actual=6631e90bbd549967ca254a334bc563e184b0af7072c270c480236d6f2850a3c6 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-027 | reports/backtest/controls/module_contribution_report.json key output hash | expected=014f9e8ccd503027cd9fbe56a705eebc9987ba731f6f955bf683690a7b492565 | actual=014f9e8ccd503027cd9fbe56a705eebc9987ba731f6f955bf683690a7b492565 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-028 | reports/backtest/robustness/sensitivity_report.json key output hash | expected=3b42cd511bf36149f3b2300b3dfb69e8d9e24202909386c83a8df923adcaea63 | actual=3b42cd511bf36149f3b2300b3dfb69e8d9e24202909386c83a8df923adcaea63 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-029 | reports/backtest/robustness/sensitivity_trigger_coverage.json key output hash | expected=82fc4e834cebcd2f6dcf95be691b0b6b758816c8278c5affbf44e158fa7decd7 | actual=82fc4e834cebcd2f6dcf95be691b0b6b758816c8278c5affbf44e158fa7decd7 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-030 | reports/observation/2026-05-04/evidence_chain.json key output hash | expected=f4e93116388473864f5024bf8fdf7213a6112c1718b027312e4f418823044aca | actual=f4e93116388473864f5024bf8fdf7213a6112c1718b027312e4f418823044aca | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-031 | reports/observation/readiness_report.json key output hash | expected=f05b26496c34b4360262648fce41350afad9b2698dbafc9f5f7de93554a990bd | actual=f05b26496c34b4360262648fce41350afad9b2698dbafc9f5f7de93554a990bd | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | CODE-001 | strategy code hash drift | expected=no drift | actual=no drift | 代码哈希与 RC code manifest 一致。
