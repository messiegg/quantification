# trace diagnostic report

## 1. Trace coverage summary

- daily_portfolio_ledger rows: 726
- daily_position_pnl rows: 3542
- trade_ledger rows: 10
- signal_execution_trace rows: 18555
- exit_rule_trace rows: 3535
- replacement_candidate_trace rows: 2

## 2. Data quality limitations

- critical_missing: []
- lot_level_cost_basis: unavailable; using FIFO_APPROX_AVG_COST
- fee_allocation: allocated directly by trade symbol, not broker lot ledger
- thesis_still_valid: heuristic from available fundamental fields
- exit_rule_origin: selected action from signal engine plus trace heuristics

## 3. Portfolio daily ledger reconciliation

- nav_return_reconciliation_ok: True
- median_position_vs_portfolio_pnl_abs_diff: 7.958078640513122e-13

## 4. Position-level PnL attribution

| symbol    |   pnl_contribution_during_drawdown |
|:----------|-----------------------------------:|
| 600036.sh |                           -714     |
| 600803.sh |                           -520.645 |
| 601318.sh |                           -166     |
| 002032.sz |                            105     |

## 5. Max drawdown attribution

- max_drawdown_window: 2025-03-17 to 2025-03-25; recovery=2025-03-31; max_drawdown=-16.04%
- market_regime: risk_on_days_ratio=1.00
- average_exposure_during_drawdown: 43.70%
- exit_lag_supported: no clear missed exit in trace
- replacement_missed_supported: no clear missed replacement in trace

Top industries:

| industry   |   pnl_contribution_during_drawdown |
|:-----------|-----------------------------------:|
| 银行         |                           -714     |
| 公用事业       |                           -520.645 |
| 非银金融       |                           -166     |
| 家用电器       |                            105     |

Top buckets:

| bucket             |   pnl_contribution_during_drawdown |
|:-------------------|-----------------------------------:|
| defensive_dividend |                           -1295.64 |

## 6. Exit rule timing analysis

- missed_exit_candidates: 1150
- would_have_triggered_trend_stop: 1150

## 7. Replacement candidate analysis

- replacement_candidate_rows: 2
- replacement_triggered_rows: 1
- diagnostic future returns remain diagnostic_only and are not present in signal_execution_trace.

## 8. Risk-on cash drag analysis

- reason_counts: {'CASH_RATIO_WITHIN_TARGET': 221, 'NO_RAW_SIGNAL': 95, 'CYCLICAL_DISABLED_OR_BLOCKED': 93, 'PORTFOLIO_FULL': 2, 'UNKNOWN': 1}

## 9. No-trade interval analysis

- longest_interval: 2023-05-12 to 2024-10-29 (355 trading days)
- reason_no_trade_summary: MARKET_REGIME_BLOCK

## 10. Updated diagnosis vs phase2

- Phase2 could only infer drawdown from portfolio NAV and global attribution. Trace now supports symbol/industry/bucket attribution with daily_position_pnl, but exact lot-level accounting is still approximate.
- Risk-on cash reasons are now derived from signal_execution_trace rather than only daily funnel counts.
- Replacement opportunity cost remains offline diagnostic-only and cannot be used as a rule input.

## 11. What can now be concluded

- Daily NAV, cash ratio, exposure, trade counts, signal blockers, exit-rule flags, and replacement comparisons are auditable by date.
- Drawdown attribution can be traced to symbols, industries, and buckets within the available average-cost ledger.

## 12. What still cannot be concluded

- Broker-grade lot-level realized PnL cannot be concluded because the trace uses FIFO_APPROX_AVG_COST.
- Live fill behavior cannot be concluded because all trades are research-only simulated next-bar fills.

## 13. Recommended next engineering step

- Before another repair search, add exact lot inventory accounting if broker-grade realized/unrealized decomposition is required; otherwise use this trace base to test a small cash-sleeve research interface separately.

## 14. Safety statement

research_only=true; auto_trading_approved=false; broker_integration_enabled=false; llm_decision_allowed=false; writes_real_trades=false; release_profile_replacement=false.
