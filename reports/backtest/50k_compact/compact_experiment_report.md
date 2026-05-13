# combined_v2_50k_compact research report

- status: HAS_50K_COMPACT_CANDIDATE
- profile: combined_v2_50k_compact
- research_only: true
- capital: 50000
- round_lot: 100
- default_release_profile_unchanged: true
- auto_trading_approved: false
- broker_integration_enabled: false
- llm_decision_allowed: false
- experiment_count: 144
- hard_condition_pass_count: 84

## conclusion

- 找到满足硬条件的 50k compact research-only 候选：mp6_tr1_tu8_cr15_add0，annual=7.31%，max_dd=-10.62%，exec/actionable=100.00%。
- 通过实验不等于可以自动实盘；任何真实交易都必须人工独立决策。
- 200k research profile 只用于解释资金规模瓶颈，不是可操作方案。

## top variants

| rank | variant | max_pos | tranches | target_universe | reserve | max_adds | annual | max_dd | max_exposure | trades | strategy_eligible | actionable | executable | exec/actionable | watch | industry_conc | pass | top reasons |
|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| 1 | mp6_tr1_tu8_cr15_add0 | 6 | 1 | 8 | 15.00% | 0 | 7.31% | -10.62% | 79.62% | 20 | 240 | 12 | 12 | 100.00% | 228 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 163, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 39, 'WATCH_ONLY_MAX_TRANCHES': 22, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 3, 'WATCH_ONLY_DAILY_NEW_LIMIT': 1} |
| 2 | mp6_tr1_tu8_cr15_add1 | 6 | 1 | 8 | 15.00% | 1 | 7.31% | -10.62% | 79.62% | 20 | 240 | 12 | 12 | 100.00% | 228 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 163, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 39, 'WATCH_ONLY_MAX_TRANCHES': 22, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 3, 'WATCH_ONLY_DAILY_NEW_LIMIT': 1} |
| 3 | mp6_tr1_tu10_cr15_add0 | 6 | 1 | 10 | 15.00% | 0 | 7.31% | -10.62% | 79.62% | 20 | 240 | 12 | 12 | 100.00% | 228 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 163, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 39, 'WATCH_ONLY_MAX_TRANCHES': 22, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 3, 'WATCH_ONLY_DAILY_NEW_LIMIT': 1} |
| 4 | mp6_tr1_tu10_cr15_add1 | 6 | 1 | 10 | 15.00% | 1 | 7.31% | -10.62% | 79.62% | 20 | 240 | 12 | 12 | 100.00% | 228 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 163, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 39, 'WATCH_ONLY_MAX_TRANCHES': 22, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 3, 'WATCH_ONLY_DAILY_NEW_LIMIT': 1} |
| 5 | mp6_tr1_tu12_cr15_add0 | 6 | 1 | 12 | 15.00% | 0 | 7.31% | -10.62% | 79.62% | 20 | 240 | 12 | 12 | 100.00% | 228 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 163, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 39, 'WATCH_ONLY_MAX_TRANCHES': 22, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 3, 'WATCH_ONLY_DAILY_NEW_LIMIT': 1} |
| 6 | mp6_tr1_tu12_cr15_add1 | 6 | 1 | 12 | 15.00% | 1 | 7.31% | -10.62% | 79.62% | 20 | 240 | 12 | 12 | 100.00% | 228 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 163, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 39, 'WATCH_ONLY_MAX_TRANCHES': 22, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 3, 'WATCH_ONLY_DAILY_NEW_LIMIT': 1} |
| 7 | mp8_tr2_tu8_cr20_add1 | 8 | 2 | 8 | 20.00% | 1 | 6.14% | -5.84% | 43.18% | 41 | 569 | 22 | 22 | 100.00% | 547 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 288, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 173, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 81, 'WATCH_ONLY_DAILY_NEW_LIMIT': 5} |
| 8 | mp8_tr2_tu10_cr20_add1 | 8 | 2 | 10 | 20.00% | 1 | 6.14% | -5.84% | 43.18% | 41 | 569 | 22 | 22 | 100.00% | 547 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 288, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 173, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 81, 'WATCH_ONLY_DAILY_NEW_LIMIT': 5} |
| 9 | mp8_tr2_tu12_cr20_add1 | 8 | 2 | 12 | 20.00% | 1 | 6.14% | -5.84% | 43.18% | 41 | 569 | 22 | 22 | 100.00% | 547 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 288, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 173, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 81, 'WATCH_ONLY_DAILY_NEW_LIMIT': 5} |
| 10 | mp8_tr2_tu8_cr15_add1 | 8 | 2 | 8 | 15.00% | 1 | 5.42% | -7.95% | 51.87% | 40 | 549 | 22 | 22 | 100.00% | 527 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 260, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 166, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 96, 'WATCH_ONLY_DAILY_NEW_LIMIT': 5} |
| 11 | mp8_tr2_tu10_cr15_add1 | 8 | 2 | 10 | 15.00% | 1 | 5.42% | -7.95% | 51.87% | 40 | 549 | 22 | 22 | 100.00% | 527 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 260, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 166, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 96, 'WATCH_ONLY_DAILY_NEW_LIMIT': 5} |
| 12 | mp8_tr2_tu12_cr15_add1 | 8 | 2 | 12 | 15.00% | 1 | 5.42% | -7.95% | 51.87% | 40 | 549 | 22 | 22 | 100.00% | 527 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 260, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 166, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 96, 'WATCH_ONLY_DAILY_NEW_LIMIT': 5} |
| 13 | mp8_tr2_tu8_cr20_add0 | 8 | 2 | 8 | 20.00% | 0 | 5.28% | -4.99% | 38.29% | 38 | 783 | 20 | 20 | 100.00% | 763 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 296, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 269, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 113, 'WATCH_ONLY_DAILY_ADD_LIMIT': 80, 'WATCH_ONLY_DAILY_NEW_LIMIT': 5} |
| 14 | mp8_tr2_tu10_cr20_add0 | 8 | 2 | 10 | 20.00% | 0 | 5.28% | -4.99% | 38.29% | 38 | 783 | 20 | 20 | 100.00% | 763 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 296, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 269, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 113, 'WATCH_ONLY_DAILY_ADD_LIMIT': 80, 'WATCH_ONLY_DAILY_NEW_LIMIT': 5} |
| 15 | mp8_tr2_tu12_cr20_add0 | 8 | 2 | 12 | 20.00% | 0 | 5.28% | -4.99% | 38.29% | 38 | 783 | 20 | 20 | 100.00% | 763 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 296, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 269, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 113, 'WATCH_ONLY_DAILY_ADD_LIMIT': 80, 'WATCH_ONLY_DAILY_NEW_LIMIT': 5} |
| 16 | mp8_tr2_tu8_cr10_add1 | 8 | 2 | 8 | 10.00% | 1 | 5.20% | -9.30% | 47.15% | 42 | 482 | 22 | 22 | 100.00% | 460 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 247, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 130, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 80, 'WATCH_ONLY_DAILY_NEW_LIMIT': 3} |
| 17 | mp8_tr2_tu10_cr10_add1 | 8 | 2 | 10 | 10.00% | 1 | 5.20% | -9.30% | 47.15% | 42 | 482 | 22 | 22 | 100.00% | 460 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 247, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 130, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 80, 'WATCH_ONLY_DAILY_NEW_LIMIT': 3} |
| 18 | mp8_tr2_tu12_cr10_add1 | 8 | 2 | 12 | 10.00% | 1 | 5.20% | -9.30% | 47.15% | 42 | 482 | 22 | 22 | 100.00% | 460 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 247, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 130, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 80, 'WATCH_ONLY_DAILY_NEW_LIMIT': 3} |
| 19 | mp8_tr2_tu8_cr15_add0 | 8 | 2 | 8 | 15.00% | 0 | 4.93% | -7.44% | 45.06% | 35 | 646 | 19 | 19 | 100.00% | 627 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 260, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 190, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 106, 'WATCH_ONLY_DAILY_ADD_LIMIT': 66, 'WATCH_ONLY_DAILY_NEW_LIMIT': 5} |
| 20 | mp8_tr2_tu10_cr15_add0 | 8 | 2 | 10 | 15.00% | 0 | 4.93% | -7.44% | 45.06% | 35 | 646 | 19 | 19 | 100.00% | 627 | 100.00% | true | {'WATCH_ONLY_PORTFOLIO_FULL': 260, 'WATCH_ONLY_LOT_TOO_EXPENSIVE': 190, 'WATCH_ONLY_INDUSTRY_CONCENTRATION': 106, 'WATCH_ONLY_DAILY_ADD_LIMIT': 66, 'WATCH_ONLY_DAILY_NEW_LIMIT': 5} |

## hard conditions

- executable/account_actionable >= 80.00%
- max_exposure <= 85.00%
- max_positions <= 8
- capital = 50000
- round_lot = 100
- default release profile remains 50k lot-aware WARN
