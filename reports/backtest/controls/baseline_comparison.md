# baseline comparison

- status: FAIL
- base_dianjinshu_like: 仓库配置中定义的点金术风格基线，不是对外部作者原文的严格复刻。
- combined_v2: 当前主研究候选。
- no_* 和 relaxed_account_constraints 仅用于解释模块贡献，不自动修改主策略。

## violations

- BASELINE_COMPARISON_MISSING: {'code': 'BASELINE_COMPARISON_MISSING', 'comparison_id': 'no_market_state_filter', 'source_control_id': 'v2_no_market_state_filter'}
- BASELINE_COMPARISON_MISSING: {'code': 'BASELINE_COMPARISON_MISSING', 'comparison_id': 'no_industry_cap', 'source_control_id': 'v2_no_industry_cap'}
- BASELINE_COMPARISON_MISSING: {'code': 'BASELINE_COMPARISON_MISSING', 'comparison_id': 'relaxed_account_constraints_research_only', 'source_control_id': 'v2_relaxed_account_constraints_research_only'}

## metrics

- base_dianjinshu_like: 年化 0.10%，累计 0.30%，回撤 -1.66%，Sharpe 0.10，Calmar 0.06，turnover 0.20，平均仓位 2.66%，成交 7，raw/executable None / None，超额 -2.79%
- combined_v2: 年化 7.14%，累计 21.96%，回撤 -9.36%，Sharpe 0.78，Calmar 0.76，turnover 2.78，平均仓位 46.98%，成交 76，raw/executable None / None，超额 4.25%
- no_high_dividend_supplement: 年化 8.11%，累计 25.19%，回撤 -7.35%，Sharpe 0.98，Calmar 1.10，turnover 2.20，平均仓位 46.46%，成交 60，raw/executable None / None，超额 5.22% | MODULE_MAY_BE_DRAG
- no_trend_stop: 年化 8.23%，累计 25.59%，回撤 -8.82%，Sharpe 0.78，Calmar 0.93，turnover 2.14，平均仓位 55.20%，成交 54，raw/executable None / None，超额 5.34% | MODULE_MAY_BE_DRAG
