# module contribution report

- status: WARN
- delta_definition: combined_v2_enabled_minus_ablation_disabled
- 模块贡献报告只解释风险收益权衡，不自动删除或修改任何模块。

## modules

- high_dividend_supplement: classification=POSSIBLE_DRAG research_only=false annual_delta=-0.98% max_drawdown_delta=-2.02% sharpe_delta=-0.19741544946340916 human_review_required=true
- trend_stop: classification=POSSIBLE_DRAG research_only=false annual_delta=-1.09% max_drawdown_delta=-0.54% sharpe_delta=-0.006097181931827178 human_review_required=true
- market_state_filter: classification=RISK_REDUCER research_only=false annual_delta=-1.16% max_drawdown_delta=3.05% sharpe_delta=-0.009849778439080081 human_review_required=false
- industry_cap: classification=RETURN_ENHANCER research_only=false annual_delta=0.52% max_drawdown_delta=-0.27% sharpe_delta=0.08528501998662985 human_review_required=false
- account_constraints: classification=RETURN_ENHANCER research_only=true annual_delta=0.14% max_drawdown_delta=0.34% sharpe_delta=0.0887378215561535 human_review_required=false

## warnings

- MODULE_REQUIRES_HUMAN_REVIEW: {'code': 'MODULE_REQUIRES_HUMAN_REVIEW', 'module': 'high_dividend_supplement', 'classification': 'POSSIBLE_DRAG'}
- MODULE_REQUIRES_HUMAN_REVIEW: {'code': 'MODULE_REQUIRES_HUMAN_REVIEW', 'module': 'trend_stop', 'classification': 'POSSIBLE_DRAG'}

## violations

- none
