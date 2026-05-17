# combined_v2_50k_core phase4 deployment repair report

- research_only: true
- auto_trading_approved: false
- broker_integration_enabled: false
- llm_decision_allowed: false
- writes_real_trades: false
- release_profile_replacement: false

## 本轮定位

本轮不是继续调参，也不是扩展参数网格；它只基于 phase3 trace 结论测试小规模机制修复。

## phase3 trace 结论摘要

- risk-on cash 主要来自 NO_RAW_SIGNAL 与 CYCLICAL_DISABLED_OR_BLOCKED；phase2 的 PORTFOLIO_FULL 判断已被修正，真正满仓高现金只有 2 天。
- 2025-03 最大回撤集中在 defensive_dividend，行业集中于银行、非银金融和公用事业。
- 回撤期间平均 exposure 43.70%，不是仓位过高导致。
- exit/replacement 没有明确滞后或应触发未触发证据。
- 2023-05-12 到 2024-10-29 长期无买入主要来自 MARKET_REGIME_BLOCK，其次 DAILY_ADD_LIMIT。

## 本轮机制

- quality_defensive_fill: 只在 risk_on、高现金且无股票可执行买入时，从 effective universe 补充非周期高质量防御候选。
- winner_add: 只加已有盈利持仓，禁止补亏损，限制单票权重和每月次数。
- financial_group_cap: 银行+非银金融合并限额，公用事业单独限额，只阻断新增，不强制卖出。
- market_regime_block_review: 不取消 regime block，只允许 neutral/risk_on 下严格复核的 quality defensive fill。
- cash_sleeve_research: 只在仓库有真实 ETF/现金替代行情时研究；无数据时仅输出 feasibility。

## top variants

| variant                                           | mechanisms_enabled                                                    |   annual_return |   max_drawdown |   sharpe |   total_trades |   avg_cash_ratio_in_risk_on |   quality_defensive_fill_executed |   winner_add_executed |   financial_group_cap_blocks |   market_regime_review_fills |   cash_sleeve_trades | pass_hard_conditions   | fail_reasons                                                                                                                        |
|:--------------------------------------------------|:----------------------------------------------------------------------|----------------:|---------------:|---------:|---------------:|----------------------------:|----------------------------------:|----------------------:|-----------------------------:|-----------------------------:|---------------------:|:-----------------------|:------------------------------------------------------------------------------------------------------------------------------------|
| quality_strict_winner_sw18                        | quality_defensive_fill,winner_add                                     |       0.0810117 |      -0.137608 | 0.677869 |              9 |                    0.326983 |                                 1 |                     3 |                            0 |                            0 |                    0 | False                  | sharpe,max_drawdown,total_trades,executable_account_actionable_ratio                                                                |
| quality_balanced_winner_sw18                      | quality_defensive_fill,winner_add                                     |       0.0810117 |      -0.137608 | 0.677869 |              9 |                    0.326983 |                                 1 |                     3 |                            0 |                            0 |                    0 | False                  | sharpe,max_drawdown,total_trades,executable_account_actionable_ratio                                                                |
| winner_add_sw16                                   | winner_add                                                            |       0.102773  |      -0.160391 | 0.638149 |             11 |                    0.318347 |                                 0 |                     1 |                            0 |                            0 |                    0 | False                  | sharpe,max_drawdown,total_trades,executable_account_actionable_ratio                                                                |
| regime_review_strict_fin2                         | quality_defensive_fill,financial_group_cap,market_regime_block_review |       0.0835038 |      -0.149502 | 0.635531 |              5 |                    0.292847 |                                 0 |                     0 |                            0 |                            3 |                    0 | False                  | sharpe,max_drawdown,total_trades,realized_pnl                                                                                       |
| regime_review_balanced_fin2                       | quality_defensive_fill,financial_group_cap,market_regime_block_review |       0.0835038 |      -0.149502 | 0.635531 |              5 |                    0.292847 |                                 0 |                     0 |                            0 |                            3 |                    0 | False                  | sharpe,max_drawdown,total_trades,realized_pnl                                                                                       |
| winner_add_sw18                                   | winner_add                                                            |       0.0989525 |      -0.168218 | 0.606574 |             11 |                    0.332234 |                                 0 |                     2 |                            0 |                            0 |                    0 | False                  | sharpe,max_drawdown,total_trades,executable_account_actionable_ratio                                                                |
| repair_best_baseline                              | baseline                                                              |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                                 0 |                     0 |                            0 |                            0 |                    0 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                                                                          |
| quality_strict_winner_sw16                        | quality_defensive_fill,winner_add                                     |       0.0980135 |      -0.170142 | 0.606545 |             10 |                    0.275609 |                                 1 |                     2 |                            0 |                            0 |                    0 | False                  | sharpe,max_drawdown,total_trades,executable_account_actionable_ratio                                                                |
| quality_balanced_winner_sw16                      | quality_defensive_fill,winner_add                                     |       0.0980135 |      -0.170142 | 0.606545 |             10 |                    0.275609 |                                 1 |                     2 |                            0 |                            0 |                    0 | False                  | sharpe,max_drawdown,total_trades,executable_account_actionable_ratio                                                                |
| regime_review_strict_fin1                         | quality_defensive_fill,financial_group_cap,market_regime_block_review |       0.0774925 |      -0.138978 | 0.520617 |              7 |                    0.265004 |                                 0 |                     0 |                            1 |                            4 |                    0 | False                  | sharpe,max_drawdown,total_trades                                                                                                    |
| regime_review_balanced_fin1                       | quality_defensive_fill,financial_group_cap,market_regime_block_review |       0.0774925 |      -0.138978 | 0.520617 |              7 |                    0.265004 |                                 0 |                     0 |                            1 |                            4 |                    0 | False                  | sharpe,max_drawdown,total_trades                                                                                                    |
| quality_fill_strict_total1                        | quality_defensive_fill                                                |       0.0922051 |      -0.1686   | 0.585167 |              8 |                    0.32775  |                                 1 |                     0 |                            0 |                            0 |                    0 | False                  | sharpe,max_drawdown,total_trades                                                                                                    |
| quality_fill_strict_total2                        | quality_defensive_fill                                                |       0.0922051 |      -0.1686   | 0.585167 |              8 |                    0.32775  |                                 1 |                     0 |                            0 |                            0 |                    0 | False                  | sharpe,max_drawdown,total_trades                                                                                                    |
| quality_fill_balanced_total1                      | quality_defensive_fill                                                |       0.0922051 |      -0.1686   | 0.585167 |              8 |                    0.32775  |                                 1 |                     0 |                            0 |                            0 |                    0 | False                  | sharpe,max_drawdown,total_trades                                                                                                    |
| quality_fill_balanced_total2                      | quality_defensive_fill                                                |       0.0893264 |      -0.1686   | 0.569309 |              9 |                    0.319277 |                                 2 |                     0 |                            0 |                            0 |                    0 | False                  | sharpe,max_drawdown,total_trades                                                                                                    |
| group_cap_fin2_fw30                               | quality_defensive_fill,financial_group_cap                            |       0.0867563 |      -0.172254 | 0.562697 |              9 |                    0.369012 |                                 2 |                     0 |                            3 |                            0 |                    0 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                                                                          |
| group_cap_fin2_fw35                               | quality_defensive_fill,financial_group_cap                            |       0.0867563 |      -0.172254 | 0.562697 |              9 |                    0.369012 |                                 2 |                     0 |                            3 |                            0 |                    0 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                                                                          |
| group_cap_fin1_fw30                               | quality_defensive_fill,financial_group_cap                            |       0.0402411 |      -0.126844 | 0.415855 |              5 |                    0.313901 |                                 2 |                     0 |                           10 |                            0 |                    0 | False                  | annual_return,sharpe,max_drawdown,total_trades,largest_single_stock_pnl_contribution,largest_industry_pnl_contribution,realized_pnl |
| group_cap_fin1_fw35                               | quality_defensive_fill,financial_group_cap                            |       0.0402411 |      -0.126844 | 0.415855 |              5 |                    0.313901 |                                 2 |                     0 |                           10 |                            0 |                    0 | False                  | annual_return,sharpe,max_drawdown,total_trades,largest_single_stock_pnl_contribution,largest_industry_pnl_contribution,realized_pnl |
| cash_sleeve_w15_                                  | cash_sleeve_research                                                  |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                                 0 |                     0 |                            0 |                            0 |                    0 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                                                                          |
| cash_sleeve_w25_                                  | cash_sleeve_research                                                  |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                                 0 |                     0 |                            0 |                            0 |                    0 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                                                                          |
| cash_sleeve_w25_quality_defensive_fill_winner_add | quality_defensive_fill,winner_add,cash_sleeve_research                |       0.0980135 |      -0.170142 | 0.606545 |             10 |                    0.275609 |                                 1 |                     2 |                            0 |                            0 |                    0 | False                  | sharpe,max_drawdown,total_trades,executable_account_actionable_ratio                                                                |
| cash_sleeve_w15_quality_defensive_fill            | quality_defensive_fill,cash_sleeve_research                           |       0.0922051 |      -0.1686   | 0.585167 |              8 |                    0.32775  |                                 1 |                     0 |                            0 |                            0 |                    0 | False                  | sharpe,max_drawdown,total_trades                                                                                                    |

## hard condition result

- variant_count: 23
- hard_condition_pass_count: 0
- stock_only_pass_count: 0
- cash_sleeve_overlay_pass_count: 0
- closest_to_pass_variant: quality_strict_winner_sw18

## stock-only vs cash sleeve

- cash sleeve PnL is reported separately and is not counted as stock alpha.
- If cash sleeve is the only pass, stock-only 50k core is still treated as not passed.

## trace questions

1. quality_defensive_fill: 减少了部分 NO_RAW_SIGNAL 高现金日。
2. winner_add: 产生加仓并降低部分 risk-on cash。
3. financial_group_cap: 阻断 10 个金融/公用事业集中新增，属于诊断性降集中。
4. market_regime_review: 产生 4 笔严格复核 fill，对 2023-05 到 2024-10 无买入区间有局部改善。
5. cash sleeve: 没有真实 ETF 数据，只能输出 feasibility，不能掩盖股票策略不足。
6. 过度交易或集中度恶化: GROUP_CAP_RETURN_TRADEOFF,QUALITY_FILL_OVERTRADING_OR_LOW_EDGE

## conclusion

- stock_only_candidate_passed: false
- cash_sleeve_overlay_candidate_passed: false
- cyclical bucket remains watch-only.
- This does not allow automatic live trading.
- This does not replace the default release profile.
