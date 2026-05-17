# diagnosis recommendations

- primary_blockers: ['neighborhood_robustness', 'sharpe', 'annual_return']
- risk_on_cash_drag_top_reasons: {'NO_RAW_SIGNAL': 95, 'PORTFOLIO_FULL': 87, 'CYCLICAL_DISABLED_OR_BLOCKED': 7, 'UNKNOWN': 2}

## Repair experiment candidates

- A. monthly rebalance review: only when risk_on and cash_ratio is above target; keep lot, position, industry and single-name constraints.
- B. replacement repair: test score_gap 6/8/10, min_holding_days 20/40, max_replacements_per_month 1/2; keep thesis-still-valid and RS-positive protection.
- C. partial de-risk: reduce one round lot or sell all single-lot holdings only when loss plus trend/RS weakness is confirmed.
- D. cyclical sleeve: keep cyclical as watch-only unless risk_on, close >= ma60 and ma20 slope non-negative.
- E. module repair: do not delete high dividend or trend stop; test partial de-risk replacing hard trend stop.

These are research-only repair ideas, not release changes.
