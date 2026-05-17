# risk-on cash trace summary

- risk_on_days: 412
- high_cash_days_above_target: 191
- reason_counts: {'CASH_RATIO_WITHIN_TARGET': 221, 'NO_RAW_SIGNAL': 95, 'CYCLICAL_DISABLED_OR_BLOCKED': 93, 'PORTFOLIO_FULL': 2, 'UNKNOWN': 1}
- avg_cash_gap_to_target: 7.66%

## answers

- NO_RAW_SIGNAL is now computed from signal_execution_trace rows. It means no raw buy intent was generated in the effective trace scope for that date.
- PORTFOLIO_FULL with high cash means positions_count reached max_positions while position weights remained below the desired risk-on exposure; this is an allocation granularity issue, not a broker execution failure.
- Replacement did not release enough cash because triggered candidate rows remained sparse and most portfolio-full rows did not become executable switch pairs.
- Cash sleeve remains a research direction, but stock execution trace should be improved first only if it can create valid replacement/exit candidates without using future returns.
