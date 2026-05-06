# combined_v2 RC verify

- overall_status: WARN
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
- PASS | CFG-002 | config/strategy_v2.yml sha256 matches RC manifest | expected=eec5115615258c7c9f1e189d1da1a013dd86d9156d86f7f6dc5aa9f7858920f9 | actual=eec5115615258c7c9f1e189d1da1a013dd86d9156d86f7f6dc5aa9f7858920f9 | 配置未漂移。
- PASS | CFG-003 | config/universe_rules_v2.yml sha256 matches RC manifest | expected=edf1b3ed04cd63dca1ca546f1a07641e84e1f3808aac166abef34e895264c2a8 | actual=edf1b3ed04cd63dca1ca546f1a07641e84e1f3808aac166abef34e895264c2a8 | 配置未漂移。
- PASS | MET-annual_return | annual_return strict RC metric | expected=0.024846220411411934 | actual=0.0248462204114119 | annual_return 必须在容差 1e-10 内复现。
- PASS | MET-cumulative_return | cumulative_return strict RC metric | expected=0.07326562069200016 | actual=0.0732656206920001 | cumulative_return 必须在容差 1e-10 内复现。
- PASS | MET-max_drawdown | max_drawdown strict RC metric | expected=-0.08876605706976393 | actual=-0.0887660570697639 | max_drawdown 必须在容差 1e-10 内复现。
- PASS | MET-final_nav | final_nav strict RC metric | expected=53663.281034600004 | actual=53663.281034600004 | final_nav 必须在容差 1e-06 内复现。
- PASS | MET-total_trades | total_trades strict RC metric | expected=41 | actual=41 | total_trades 必须等于 76。
- PASS | OUT-001 | combined_v2 trades detailed hash | expected=34a6eaaddba006b4122093ee0932e47bc094fa9e8e605ca8c3a43ac1af7f05a9 | actual=34a6eaaddba006b4122093ee0932e47bc094fa9e8e605ca8c3a43ac1af7f05a9 | 交易明细文件 hash 漂移但严格指标一致时标记 WARN；若指标也漂移则整体 FAIL。
- PASS | OUT-010 | config/account.yml key output hash | expected=6482e45ec46ba0609ecf5fa9ca7069fe3a586a017843bf0947239e79728322fd | actual=6482e45ec46ba0609ecf5fa9ca7069fe3a586a017843bf0947239e79728322fd | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-011 | config/metric_map.yml key output hash | expected=5d01eaf16b945566c3686dd66fd2c52f6184ee7afa2712890571982fd35901ce | actual=5d01eaf16b945566c3686dd66fd2c52f6184ee7afa2712890571982fd35901ce | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-012 | config/observation.yml key output hash | expected=d8c632ef4363e733065213a98a8b9b328b87281745ec7cd67d98582448b6e31b | actual=d8c632ef4363e733065213a98a8b9b328b87281745ec7cd67d98582448b6e31b | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-013 | config/observation_readiness.yml key output hash | expected=d3cd1f8ab42f5cc939b809ea9091af5c8ade3e2e8827c5a5235b779a3866d8ce | actual=d3cd1f8ab42f5cc939b809ea9091af5c8ade3e2e8827c5a5235b779a3866d8ce | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-014 | reports/audit/config_consistency.json key output hash | expected=5a1ed484d116e26d2a84e388edcbd28cace6922b8fe81db04b0bfabac4a5be12 | actual=88dafdb7e4d8de930bdf2cdcec4437fa4f0ab3c63369d28c8651601c89fde403 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-015 | reports/audit/data_freshness.json key output hash | expected=610c450fccb5ce4310df4eafadcf0991ce7c56b4336163b2a2cad26c256424dc | actual=ac0ddc080361b6efa10dbad1ad900a4be3954fbd9ef03d4bede5acd9d027efd7 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-016 | reports/audit/universe_integrity.json key output hash | expected=67f50de841e0f7bab0b0ebfbbd80ca2adb061f3caed9aa6ff463092e5d9ccb59 | actual=112a43c946641cf3818e4fc0d557c3093c32f13657dbc26e69d74facf2a9077e | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-017 | reports/audit/universe_shortfall.json key output hash | expected=82f99a5f9dcf122053f30ab8a3af6b2cf1430d53b6acfdf256abd773dfc1b21a | actual=46226e278cb3a4d0f5bd482c8b865a907b1b6b05fd3e87f89d24b25a6da88c4c | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-018 | reports/backtest/account_constraints_report.json key output hash | expected=eaaf5f14bc589215094e12939e3780aa88167d076a5aa7f0ba0efbfe04be87be | actual=8e6920c39d6ddf63467890a26c24ae00fa5932db728f6972b27447599ceda3e8 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-019 | reports/backtest/account_profiles/account_profile_comparison.json key output hash | expected=e81c5fac9fcf4f64b2659aeb6f5a3f78d23d8bf3a63c0cee5cbf9173b25d55ad | actual=e81c5fac9fcf4f64b2659aeb6f5a3f78d23d8bf3a63c0cee5cbf9173b25d55ad | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-020 | reports/backtest/account_suitability_report.json key output hash | expected=094f21201dc461600a9377477d15e435ddfce818d9eaa9af0cc0732daf061e2f | actual=4c85a0f6da6f334456aa1c2ec89c52ff8d9e9e50674719146bd6f03154a60e1f | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-021 | reports/backtest/audit/integrity_audit.csv key output hash | expected=f38ab2c649db9d43726528a52f172e5bc380b539982b01c62163c244000072d3 | actual=f38ab2c649db9d43726528a52f172e5bc380b539982b01c62163c244000072d3 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-022 | reports/backtest/audit/lookahead_audit.csv key output hash | expected=e445f1c0ee4db5f9964d83928900424f3a9719b20874ccc9a61fbdc67c240c1c | actual=e445f1c0ee4db5f9964d83928900424f3a9719b20874ccc9a61fbdc67c240c1c | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-023 | reports/backtest/combined_v2_candidate_scores.csv key output hash | expected=e73c8e531d8777ee511d657241d689196a61e7dd62c8b6db3e8ad45b6d9b97bc | actual=e73c8e531d8777ee511d657241d689196a61e7dd62c8b6db3e8ad45b6d9b97bc | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-024 | reports/backtest/combined_v2_retail_50k_metrics.csv key output hash | expected=b4ccd522090029b00aabf60a3b0c18913ad9ea64e3f987099740d66d313ca330 | actual=b4ccd522090029b00aabf60a3b0c18913ad9ea64e3f987099740d66d313ca330 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-025 | reports/backtest/combined_v2_signal_funnel.csv key output hash | expected=d4ea5b59f5af7d927fefc3dcc03f2b2568a4aa253eac72baa4458adc46b73eae | actual=d4ea5b59f5af7d927fefc3dcc03f2b2568a4aa253eac72baa4458adc46b73eae | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-026 | reports/backtest/controls/baseline_comparison.json key output hash | expected=4083d52627be6e68fe5516c3c2a973d2e7fc9e0fc19ace95c915a6981b4952d9 | actual=4083d52627be6e68fe5516c3c2a973d2e7fc9e0fc19ace95c915a6981b4952d9 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-027 | reports/backtest/controls/module_contribution_report.json key output hash | expected=f42aa3ae7c437ccdb49de19184b09d8d7282918a3ce2f8fbefe03d40434207c6 | actual=203fe63a2cb4e834b60c52b751a6f78bf7c0d9063616a3e30f81c7f1729ddbfb | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-028 | reports/backtest/robustness/sensitivity_report.json key output hash | expected=5b76e2629c83b8a39cca895104e6d702bc51d00d9f31694bb02cb873e46ea150 | actual=5b76e2629c83b8a39cca895104e6d702bc51d00d9f31694bb02cb873e46ea150 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-029 | reports/backtest/robustness/sensitivity_trigger_coverage.json key output hash | expected=a0d6b753e5e5f87cec1fe206b4d7a5839500704e797a5710bed304eba993a1f2 | actual=b109d54e5eefd179e1eb0d6d1fcd69f0c77294249963e4e76dada1d2b56dbb28 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-030 | reports/observation/2026-05-04/evidence_chain.json key output hash | expected=1bbc70caa79a96c62386c2beab123b87313f8eaffc5df1d73640e431e59ac1f9 | actual=149777b662b806dbb44ace8f92823bcfa99356eaaa6c3df2fbb57be3d249b07a | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-031 | reports/observation/readiness_report.json key output hash | expected=5cbb75b9a16cac78760d62e5c4a43bec1b74dfd315d0e5a8bdb73b1d9c287a4a | actual=5cbb75b9a16cac78760d62e5c4a43bec1b74dfd315d0e5a8bdb73b1d9c287a4a | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | CODE-001 | strategy code hash drift | expected=no drift | actual=src/strategy/signals.py;src/strategy/backtest_engine.py;src/strategy/universe.py;src/strategy/backtest_reports.py;scripts/audit_backtest_integrity.py | 代码有漂移时不直接判定策略失效，但必须重跑完整审计。
