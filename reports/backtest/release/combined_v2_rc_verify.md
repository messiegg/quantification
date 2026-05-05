# combined_v2 RC verify

- overall_status: WARN
- mode: hash-only
- profile: combined_v2
- execution_mode: next_bar
- period: 2023-04-03 to 2026-04-03
- annual_return: 0.0713520247687258
- cumulative_return: 0.2196444045310004
- max_drawdown: -0.0936454742991675
- total_trades: 76
- final_nav: 243928.8809062001

## checks

- PASS | MODE-001 | verification mode | expected=hash-only | actual=hash-only | hash-only 使用已提交的小型报告与 manifest，不重跑完整回测；full 仅用于本地完整数据环境。
- PASS | CFG-002 | config/strategy_v2.yml sha256 matches RC manifest | expected=7957dae7b8671c0c19cad3712f02d642e684a8be3c445f73c8b32455543c7ccb | actual=7957dae7b8671c0c19cad3712f02d642e684a8be3c445f73c8b32455543c7ccb | 配置未漂移。
- PASS | CFG-003 | config/universe_rules_v2.yml sha256 matches RC manifest | expected=edf1b3ed04cd63dca1ca546f1a07641e84e1f3808aac166abef34e895264c2a8 | actual=edf1b3ed04cd63dca1ca546f1a07641e84e1f3808aac166abef34e895264c2a8 | 配置未漂移。
- PASS | MET-annual_return | annual_return strict RC metric | expected=0.0713520247687258 | actual=0.0713520247687258 | annual_return 必须在容差 1e-10 内复现。
- PASS | MET-cumulative_return | cumulative_return strict RC metric | expected=0.2196444045310004 | actual=0.2196444045310004 | cumulative_return 必须在容差 1e-10 内复现。
- PASS | MET-max_drawdown | max_drawdown strict RC metric | expected=-0.0936454742991675 | actual=-0.0936454742991675 | max_drawdown 必须在容差 1e-10 内复现。
- PASS | MET-final_nav | final_nav strict RC metric | expected=243928.8809062001 | actual=243928.8809062001 | final_nav 必须在容差 1e-06 内复现。
- PASS | MET-total_trades | total_trades strict RC metric | expected=76 | actual=76 | total_trades 必须等于 76。
- PASS | OUT-001 | combined_v2 trades detailed hash | expected=6a1e6a6859c8dfa0e399bf0f900aadad6a3920e36ce3e2cb95a090d6c8643cec | actual=6a1e6a6859c8dfa0e399bf0f900aadad6a3920e36ce3e2cb95a090d6c8643cec | 交易明细文件 hash 漂移但严格指标一致时标记 WARN；若指标也漂移则整体 FAIL。
- PASS | OUT-010 | config/account.yml key output hash | expected=997c8fa175dc5562aaed18a944df6447ff67e92be222cecd35b60655025feb7f | actual=997c8fa175dc5562aaed18a944df6447ff67e92be222cecd35b60655025feb7f | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-011 | config/metric_map.yml key output hash | expected=5d01eaf16b945566c3686dd66fd2c52f6184ee7afa2712890571982fd35901ce | actual=5d01eaf16b945566c3686dd66fd2c52f6184ee7afa2712890571982fd35901ce | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-012 | config/observation.yml key output hash | expected=d8c632ef4363e733065213a98a8b9b328b87281745ec7cd67d98582448b6e31b | actual=d8c632ef4363e733065213a98a8b9b328b87281745ec7cd67d98582448b6e31b | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-013 | config/observation_readiness.yml key output hash | expected=d3cd1f8ab42f5cc939b809ea9091af5c8ade3e2e8827c5a5235b779a3866d8ce | actual=d3cd1f8ab42f5cc939b809ea9091af5c8ade3e2e8827c5a5235b779a3866d8ce | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-014 | reports/audit/config_consistency.json key output hash | expected=8a670a7fba5827ab20abab19e57009d525408011570e01b36f0ecf896a07ebf5 | actual=a2097562b1936594311acf56cfbe7b477e85efbad4c37cd6ac1a344861d9b118 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-015 | reports/audit/data_freshness.json key output hash | expected=27e3c97fc3596cedac5421139beafaa0346eb93696c4b72477eaad16748de156 | actual=56918713265c7e83d5bf97049b8533ea10e5e66786dce99448abd600eea204d8 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-016 | reports/audit/universe_integrity.json key output hash | expected=bf4c2b2c810d978ddafe8d4c14ff0ded6a78406b529fcbde1d0d9cc83481db70 | actual=24ec2ff3ed00f625e63a14635cdc8077935cdc50df4e10c660f5ff2db6be8470 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-017 | reports/audit/universe_shortfall.json key output hash | expected=8d7153845661279be98f935e5d4ea336dc2407e32b2ef5117a6459ec1a6f1a8b | actual=7b5c711388c9fe86033cd4864ee2b1b465e3cfd676471223ee41e54fc50203d5 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-018 | reports/backtest/account_constraints_report.json key output hash | expected=d8fc7e732775952d1600cd1b0a45cc01738b04acffed4f3d275476fd37147622 | actual=9dfc70561620ec349e7c2ba38afe416095eba314cb6f555391eb5c7af242cc43 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-019 | reports/backtest/account_suitability_report.json key output hash | expected=efcbf11bc8d45c9975ebee7e556174127fa914ae8c6ac0e0af42c0dff257a1cf | actual=467053002c31e44afd1aaeed027992b03fe9dfc7e223ba6ca5541b666a925c69 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-020 | reports/backtest/audit/integrity_audit.csv key output hash | expected=f38ab2c649db9d43726528a52f172e5bc380b539982b01c62163c244000072d3 | actual=f38ab2c649db9d43726528a52f172e5bc380b539982b01c62163c244000072d3 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-021 | reports/backtest/audit/lookahead_audit.csv key output hash | expected=e445f1c0ee4db5f9964d83928900424f3a9719b20874ccc9a61fbdc67c240c1c | actual=e445f1c0ee4db5f9964d83928900424f3a9719b20874ccc9a61fbdc67c240c1c | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-022 | reports/backtest/combined_v2_candidate_scores.csv key output hash | expected=e73c8e531d8777ee511d657241d689196a61e7dd62c8b6db3e8ad45b6d9b97bc | actual=e73c8e531d8777ee511d657241d689196a61e7dd62c8b6db3e8ad45b6d9b97bc | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-023 | reports/backtest/combined_v2_signal_funnel.csv key output hash | expected=68a417c1438d6925dfc4bfb33832526eb4b28c06811991c7d2df8329b49214f8 | actual=68a417c1438d6925dfc4bfb33832526eb4b28c06811991c7d2df8329b49214f8 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-024 | reports/backtest/controls/baseline_comparison.json key output hash | expected=0662216c60f7d7ab899488794e9610af4dd53cc35ca143373e4c288aab313793 | actual=0662216c60f7d7ab899488794e9610af4dd53cc35ca143373e4c288aab313793 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-025 | reports/backtest/controls/module_contribution_report.json key output hash | expected=5b649f969b0face29236caac97b126938e87fb9e089167a80f32427f1711b4be | actual=96d093efaf089ea50a2b2014939dd841d2051fdf33eff56bd70e809cb082d072 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-026 | reports/backtest/robustness/sensitivity_report.json key output hash | expected=b6845b1daee4c288107c7b351cb9a0b36c8be5f4621b66b0807ebbae36265fe8 | actual=b6845b1daee4c288107c7b351cb9a0b36c8be5f4621b66b0807ebbae36265fe8 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-027 | reports/backtest/robustness/sensitivity_trigger_coverage.json key output hash | expected=e75584231a930f1cfadec4c109a1f3c12b46cce4dc0a393e91755afb1013e41a | actual=0ceb452337de7e6f80c25c4871b15c98e89370480ded6966fd2d4cd9cbc62181 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-028 | reports/observation/2026-05-04/evidence_chain.json key output hash | expected=4d7b581b91dfccb38f40081929faa733d92cf97f6bbba6c090b716ebcd59a2ef | actual=76d394baaf005f920eeb50d05240d35eac71140e3217ba0bb969f24b8072a5f7 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-029 | reports/observation/readiness_report.json key output hash | expected=60151accdb259782b6a294ab4f9c891e71116a0f2f39a908407f43d5c4dee5e1 | actual=60151accdb259782b6a294ab4f9c891e71116a0f2f39a908407f43d5c4dee5e1 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | CODE-001 | strategy code hash drift | expected=no drift | actual=src/strategy/universe.py;src/strategy/backtest_reports.py;scripts/audit_backtest_integrity.py | 代码有漂移时不直接判定策略失效，但必须重跑完整审计。
