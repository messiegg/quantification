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
- WARN | OUT-013 | reports/audit/config_consistency.json key output hash | expected=77090fe76a34da2a53ef2783e8ea366729765b8e0a76960933372b8d01128acf | actual=8f1815371d273f5d911bda46cb443b20f157d590b281663e1b80eaf859229885 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-014 | reports/audit/data_freshness.json key output hash | expected=21bbee05d7d280c9a5cd4dfb2c6963b06511468d49e242eff220dbfade0f5c90 | actual=139f5465eae07c3534cd632e07c79703024673d919850cc10975f2a8cbc22a2f | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-015 | reports/audit/universe_integrity.json key output hash | expected=80c9499b66974bcda8145070cad18bca38369fe954282fd71cabae798053000d | actual=ed1897ca0ea7d4bc0ed3cfee94308531c997f803768bc3df7a6e66781e704b86 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-016 | reports/backtest/account_constraints_report.json key output hash | expected=a8634ee5d049c78dad166e4c2feb18add2de52a0bb64e057e5fed9cc6c9d395c | actual=ea1b24f2574686bfb70c9db6625f96d88036575a443aa6f168a06322cb3d4832 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-017 | reports/backtest/audit/integrity_audit.csv key output hash | expected=f38ab2c649db9d43726528a52f172e5bc380b539982b01c62163c244000072d3 | actual=f38ab2c649db9d43726528a52f172e5bc380b539982b01c62163c244000072d3 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-018 | reports/backtest/audit/lookahead_audit.csv key output hash | expected=e445f1c0ee4db5f9964d83928900424f3a9719b20874ccc9a61fbdc67c240c1c | actual=e445f1c0ee4db5f9964d83928900424f3a9719b20874ccc9a61fbdc67c240c1c | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-019 | reports/backtest/combined_v2_candidate_scores.csv key output hash | expected=e73c8e531d8777ee511d657241d689196a61e7dd62c8b6db3e8ad45b6d9b97bc | actual=e73c8e531d8777ee511d657241d689196a61e7dd62c8b6db3e8ad45b6d9b97bc | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-020 | reports/backtest/combined_v2_signal_funnel.csv key output hash | expected=68a417c1438d6925dfc4bfb33832526eb4b28c06811991c7d2df8329b49214f8 | actual=68a417c1438d6925dfc4bfb33832526eb4b28c06811991c7d2df8329b49214f8 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-021 | reports/backtest/controls/baseline_comparison.json key output hash | expected=018fea1522dc26e60fedd58881c1d95c884b811e66593b82009ceccf0d39d181 | actual=018fea1522dc26e60fedd58881c1d95c884b811e66593b82009ceccf0d39d181 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-022 | reports/backtest/robustness/sensitivity_report.json key output hash | expected=3acff0e05d3bb988497bff973fc78c1fc7c820a4f71e27154bc5842b612cb672 | actual=3acff0e05d3bb988497bff973fc78c1fc7c820a4f71e27154bc5842b612cb672 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | OUT-023 | reports/observation/2026-05-04/evidence_chain.json key output hash | expected=47538e9ee5719512793366c3c786dc914a2495d51d2436a7427cd23f9098efcc | actual=0d7e4757b39d1a98076794b1655c449d145bd4a751ee05c4dcc2cb7d974925ec | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- WARN | CODE-001 | strategy code hash drift | expected=no drift | actual=src/strategy/universe.py;src/strategy/backtest_reports.py;scripts/audit_backtest_integrity.py | 代码有漂移时不直接判定策略失效，但必须重跑完整审计。
