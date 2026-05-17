# 50k core hard condition failure summary

## Primary blockers

- neighborhood_robustness: fail_count=17, median_gap=3.0000, 邻域鲁棒性不足
- sharpe: fail_count=17, median_gap=0.4777, 组合质量不足
- annual_return: fail_count=15, median_gap=0.0195, 收益能力不足

## Full table

| condition_name                        |   fail_count |   fail_ratio |   median_gap_to_pass |   best_gap_to_pass |   worst_gap_to_pass |   variants_close_to_pass_count | interpretation             |
|:--------------------------------------|-------------:|-------------:|---------------------:|-------------------:|--------------------:|-------------------------------:|:---------------------------|
| annual_return                         |           15 |     0.882353 |            0.0195196 |         0.00204744 |           0.0429951 |                              8 | 收益能力不足                     |
| sharpe                                |           17 |     1        |            0.477679  |         0.130147   |           0.628891  |                              0 | 组合质量不足                     |
| max_drawdown                          |            8 |     0.470588 |            0.0860595 |         0.0403906  |           0.0946187 |                              0 | 组合质量不足                     |
| total_trades                          |           11 |     0.647059 |            5         |         3          |          11         |                              8 | 执行与资金利用不足                  |
| executable_account_actionable_ratio   |            0 |     0        |            0         |         0          |           0         |                              0 | passed in sampled variants |
| avg_cash_ratio_in_risk_on             |           14 |     0.823529 |            0.087219  |         0.00447511 |           0.284578  |                              3 | 执行与资金利用不足                  |
| largest_single_stock_pnl_contribution |            2 |     0.117647 |            0.0230311 |         0.00913014 |           0.036932  |                              1 | 组合质量不足                     |
| largest_industry_pnl_contribution     |            2 |     0.117647 |            0.0113361 |         0.00208626 |           0.0205859 |                              1 | 组合质量不足                     |
| realized_pnl                          |            0 |     0        |            0         |         0          |           0         |                              0 | passed in sampled variants |
| cyclical_rotation_pnl                 |            5 |     0.294118 |         1076.95      |       594.877      |        1808.85      |                             11 | 周期 bucket 负贡献              |
| neighborhood_robustness               |           17 |     1        |            3         |         3          |           3         |                             17 | 邻域鲁棒性不足                    |
