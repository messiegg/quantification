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
- WARN | OUT-013 | reports/audit/config_consistency.json key output hash | expected=798ed997cd2877b7159e25e046a0a6a8ae54078e6664537a43ffe1d5b1137096 | actual=edfe54885acbe08279fd0b5058375ec53d98cf90c20530b9a6d4e86efd5b4cf6 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-014 | reports/audit/data_freshness.json key output hash | expected=34afe5f6fb8dfeabdca088d2806bf9ba59e4990338731c50018ab68df23fdaf1 | actual=968fa3d5c92bbabce3a08ae027f1b969cc65af23feb19dfcc92749d3241d9436 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-015 | reports/audit/universe_integrity.json key output hash | expected=5b1f898095956020d225f6b6092bd1801a087496ad194add2c9fa4c67958dd72 | actual=1f1fb85baf8ab7cb3dcf1ae4b30fe110869c04628c9df950ac04c0777850ec98 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-016 | reports/backtest/account_constraints_report.json key output hash | expected=30b684869da5dd28babe19ba696a597f147f0e7b41229fc77b91c92e7344dd57 | actual=4db3f780eca212d3c4cca9edf708745fc1551de6f26e14216f1deaba2829c656 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-017 | reports/backtest/audit/integrity_audit.csv key output hash | expected=f38ab2c649db9d43726528a52f172e5bc380b539982b01c62163c244000072d3 | actual=f38ab2c649db9d43726528a52f172e5bc380b539982b01c62163c244000072d3 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-018 | reports/backtest/audit/lookahead_audit.csv key output hash | expected=e445f1c0ee4db5f9964d83928900424f3a9719b20874ccc9a61fbdc67c240c1c | actual=e445f1c0ee4db5f9964d83928900424f3a9719b20874ccc9a61fbdc67c240c1c | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-019 | reports/backtest/combined_v2_candidate_scores.csv key output hash | expected=e73c8e531d8777ee511d657241d689196a61e7dd62c8b6db3e8ad45b6d9b97bc | actual=e73c8e531d8777ee511d657241d689196a61e7dd62c8b6db3e8ad45b6d9b97bc | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-020 | reports/backtest/combined_v2_signal_funnel.csv key output hash | expected=68a417c1438d6925dfc4bfb33832526eb4b28c06811991c7d2df8329b49214f8 | actual=68a417c1438d6925dfc4bfb33832526eb4b28c06811991c7d2df8329b49214f8 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-021 | reports/backtest/controls/baseline_comparison.json key output hash | expected=b8cc433715313112afe9158e1783d2a9ae3b5d1810bf61dba0ce866e6c49548b | actual=b8cc433715313112afe9158e1783d2a9ae3b5d1810bf61dba0ce866e6c49548b | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-022 | reports/backtest/robustness/sensitivity_report.json key output hash | expected=6f858f5d011cc179c5258601a06c021a3a51d3a816d04f59ab40a019fbb58f62 | actual=6f858f5d011cc179c5258601a06c021a3a51d3a816d04f59ab40a019fbb58f62 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-023 | reports/observation/2026-05-04/evidence_chain.json key output hash | expected=699a3bbf6890196e7524d8f86ad98961572445b9ae03c2c1694ad1711050c05d | actual=ec409a5c27e9b6a593db903bffd07a3fc378bf61bc67c8deb8d80eb2ab2b6b46 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | CODE-001 | strategy code hash drift | expected=no drift | actual=src/strategy/backtest_reports.py;scripts/audit_backtest_integrity.py | 代码有漂移时不直接判定策略失效，但必须重跑完整审计。
