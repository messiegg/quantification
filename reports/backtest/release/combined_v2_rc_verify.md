# combined_v2 RC verify

- overall_status: PASS
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
- PASS | CFG-002 | config/strategy_v2.yml sha256 matches RC manifest | expected=2d1d303f0e845a0d44279c4c60438604bad1e10cd3eea6e5c6a0152b5c7b2a04 | actual=2d1d303f0e845a0d44279c4c60438604bad1e10cd3eea6e5c6a0152b5c7b2a04 | 配置未漂移。
- PASS | CFG-003 | config/universe_rules_v2.yml sha256 matches RC manifest | expected=edf1b3ed04cd63dca1ca546f1a07641e84e1f3808aac166abef34e895264c2a8 | actual=edf1b3ed04cd63dca1ca546f1a07641e84e1f3808aac166abef34e895264c2a8 | 配置未漂移。
- PASS | MET-annual_return | annual_return strict RC metric | expected=0.0713520247687258 | actual=0.0713520247687258 | annual_return 必须在容差 1e-10 内复现。
- PASS | MET-cumulative_return | cumulative_return strict RC metric | expected=0.2196444045310004 | actual=0.2196444045310004 | cumulative_return 必须在容差 1e-10 内复现。
- PASS | MET-max_drawdown | max_drawdown strict RC metric | expected=-0.0936454742991675 | actual=-0.0936454742991675 | max_drawdown 必须在容差 1e-10 内复现。
- PASS | MET-final_nav | final_nav strict RC metric | expected=243928.8809062001 | actual=243928.8809062001 | final_nav 必须在容差 1e-06 内复现。
- PASS | MET-total_trades | total_trades strict RC metric | expected=76 | actual=76 | total_trades 必须等于 76。
- PASS | OUT-001 | combined_v2 trades detailed hash | expected=6a1e6a6859c8dfa0e399bf0f900aadad6a3920e36ce3e2cb95a090d6c8643cec | actual=6a1e6a6859c8dfa0e399bf0f900aadad6a3920e36ce3e2cb95a090d6c8643cec | 交易明细文件 hash 漂移但严格指标一致时标记 WARN；若指标也漂移则整体 FAIL。
- PASS | OUT-010 | reports/backtest/attribution/combined_v2_monthly_returns.csv key output hash | expected=263bbbd73a5fd9755ae77c2c4aa7172d981fba302f3bb4d89092f2b1b58f847d | actual=263bbbd73a5fd9755ae77c2c4aa7172d981fba302f3bb4d89092f2b1b58f847d | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-011 | reports/backtest/attribution/combined_v2_position_attribution.csv key output hash | expected=33927cc57ed658b2d379757b57c4607cd5f3f0dce8b643ca57c9fc4bf37bc778 | actual=33927cc57ed658b2d379757b57c4607cd5f3f0dce8b643ca57c9fc4bf37bc778 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-012 | reports/backtest/attribution/combined_v2_regime_attribution.csv key output hash | expected=b6319a00e0e386751d2490b47f1c5024c2071f6c090019c823750e3ee7934ba2 | actual=b6319a00e0e386751d2490b47f1c5024c2071f6c090019c823750e3ee7934ba2 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-013 | reports/backtest/attribution/combined_v2_signal_attribution.csv key output hash | expected=fc94e98ea51b2478dd0f30cd4fd77f2fb252389f298595359c0dd0188dd3daaf | actual=fc94e98ea51b2478dd0f30cd4fd77f2fb252389f298595359c0dd0188dd3daaf | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-014 | reports/backtest/attribution/combined_v2_trade_attribution.csv key output hash | expected=b396b30200aa348ab6d4dc48dc84d1540ad3c2bbc0ed11657f904b34a64f37a2 | actual=b396b30200aa348ab6d4dc48dc84d1540ad3c2bbc0ed11657f904b34a64f37a2 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-015 | reports/backtest/audit/integrity_audit.csv key output hash | expected=f38ab2c649db9d43726528a52f172e5bc380b539982b01c62163c244000072d3 | actual=f38ab2c649db9d43726528a52f172e5bc380b539982b01c62163c244000072d3 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-016 | reports/backtest/audit/lookahead_audit.csv key output hash | expected=e445f1c0ee4db5f9964d83928900424f3a9719b20874ccc9a61fbdc67c240c1c | actual=e445f1c0ee4db5f9964d83928900424f3a9719b20874ccc9a61fbdc67c240c1c | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-017 | reports/backtest/combined_v2_candidate_scores.csv key output hash | expected=e73c8e531d8777ee511d657241d689196a61e7dd62c8b6db3e8ad45b6d9b97bc | actual=e73c8e531d8777ee511d657241d689196a61e7dd62c8b6db3e8ad45b6d9b97bc | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-018 | reports/backtest/combined_v2_signal_funnel.csv key output hash | expected=68a417c1438d6925dfc4bfb33832526eb4b28c06811991c7d2df8329b49214f8 | actual=68a417c1438d6925dfc4bfb33832526eb4b28c06811991c7d2df8329b49214f8 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | OUT-019 | reports/backtest/controls/control_baselines_metrics.csv key output hash | expected=c295d12ceb198d199bb81914db21234e9bf2e685ea696982ce2dd88face185a3 | actual=c295d12ceb198d199bb81914db21234e9bf2e685ea696982ce2dd88face185a3 | 报告或辅助产物 hash 漂移；若严格指标完全一致，作为 WARN 处理并建议刷新审计报告。
- PASS | CODE-001 | strategy code hash drift | expected=no drift | actual=no drift | 代码哈希与 RC code manifest 一致。
