# combined_v2_50k_core research report

## 1. 摘要

- status: NO_50K_CORE_CANDIDATE
- candidate_is_research_only: true
- auto_trading_allowed: false
- release_replacement: false
- experiment_count: 17
- hard_condition_pass_count: 0

## 2. 为什么原 50k 表现差

- raw buy 到 executable buy 漏斗显示，信号不是完全缺失，主要损耗发生在组合满仓、现金不足和一手金额过高。
- 小账户下 100 股整手导致目标仓位金额与真实可买单位错配，高现金拖累会持续存在。
- 原多档加仓结构会把现金切碎，增加 `LOT_SIZE_ACCUMULATION_REQUIRED` 类 watch-only 或 pending 信号。
- 持仓数量过多时，单票贡献和行业贡献更容易集中，替换机制需要只在 research backtest 中模拟。

## 3. 50k core 的设计逻辑

- 少持仓、单档、不加仓，降低整手执行碎片化。
- 单票上限提高到 14%-18% 网格，但一手金额超过单票上限时仍结构性阻断。
- defensive dividend 作为核心，周期股作为 risk-on opportunity sleeve，且不能挤占 defensive core。
- replacement / switch plan 只在回测中 research-only 模拟，live/manual 仍 advisory only。
- lot-fit 进入排序和审计输出，而不是事后解释。

## 4. top 20 变体表

| variant | annual_return | cumulative_return | max_drawdown | sharpe | total_trades | executable_account_actionable_ratio | average_exposure | avg_cash_ratio_in_risk_on | largest_single_stock_pnl_contribution | largest_industry_pnl_contribution | defensive_dividend_pnl | cyclical_rotation_pnl | replacement_count | pass_hard_conditions | fail_reasons |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_disable_both | 9.80% | 30.92% | -16.04% | 61.99% | 10 | 100.00% | 59.33% | 36.46% | 22.91% | 41.05% | 15473.951687599998 | 0.0 | 1 | False | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_disable_trend_stop | 6.89% | 21.17% | -11.21% | 58.52% | 9 | 100.00% | 70.83% | 26.87% | 31.80% | 57.06% | 10130.929068800004 | 469.3128287999987 | 0 | False | sharpe,total_trades,largest_industry_pnl_contribution |
| mp6_tr1_tu8_cr10_sw18_ind2_def3_cy2_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_current | 3.11% | 9.24% | -8.61% | 34.31% | 24 | 100.00% | 47.45% | 42.61% | 26.05% | 29.54% | 6448.570696800004 | -1808.8503851999974 | 1 | False | annual_return,sharpe,avg_cash_ratio_in_risk_on,cyclical_rotation_pnl |
| mp6_tr1_tu8_cr15_sw18_ind2_def4_cy2_lot100_gap10_rpm1_ro85_ne60_rf25_rep1_cyc1_current | 3.11% | 9.24% | -8.61% | 34.31% | 24 | 100.00% | 47.45% | 42.61% | 26.05% | 29.54% | 6448.570696800004 | -1808.8503851999974 | 1 | False | annual_return,sharpe,avg_cash_ratio_in_risk_on,cyclical_rotation_pnl |
| mp5_tr1_tu8_cr10_sw14_ind1_def3_cy0_lot80_gap8_rpm1_ro75_ne45_rf25_rep1_cyc1_current | 2.73% | 8.06% | -10.76% | 34.46% | 15 | 100.00% | 29.34% | 63.46% | 48.69% | 53.82% | 4409.354240800003 | -367.49537399999946 | 0 | False | annual_return,sharpe,total_trades,avg_cash_ratio_in_risk_on,largest_single_stock_pnl_contribution |
| mp5_tr1_tu8_cr15_sw16_ind2_def4_cy0_lot90_gap10_rpm1_ro85_ne60_rf25_rep1_cyc1_current | 4.80% | 14.45% | -18.60% | 35.48% | 16 | 100.00% | 52.98% | 41.48% | 24.90% | 36.07% | 7242.785331600003 | 0.0 | 2 | False | annual_return,sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy2_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_current | 2.22% | 6.52% | -10.55% | 25.07% | 17 | 100.00% | 64.14% | 30.17% | 38.64% | 38.12% | 3880.2758968000066 | -594.8765340000018 | 0 | False | annual_return,sharpe,total_trades,cyclical_rotation_pnl |
| mp6_tr1_tu8_cr10_sw16_ind2_def3_cy0_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_current | 1.50% | 4.38% | -9.07% | 20.50% | 20 | 100.00% | 41.94% | 52.44% | 38.80% | 52.97% | 2575.2026608000065 | -367.49537399999946 | 0 | False | annual_return,sharpe,avg_cash_ratio_in_risk_on |
| mp6_tr1_tu8_cr15_sw18_ind2_def4_cy0_lot100_gap10_rpm1_ro85_ne60_rf25_rep1_cyc1_current | 1.50% | 4.38% | -9.07% | 20.50% | 20 | 100.00% | 41.94% | 52.44% | 38.80% | 52.97% | 2575.2026608000065 | -367.49537399999946 | 0 | False | annual_return,sharpe,avg_cash_ratio_in_risk_on |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy1_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_current | 4.38% | 13.15% | -20.77% | 31.86% | 17 | 100.00% | 66.56% | 25.88% | 26.90% | 32.50% | 6130.212820800006 | 469.3128287999987 | 1 | False | annual_return,sharpe,max_drawdown,total_trades |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap8_rpm1_ro85_ne60_rf25_rep0_cyc1_replacement_disabled | 4.32% | 12.94% | -20.60% | 31.85% | 15 | 100.00% | 57.77% | 39.18% | 37.91% | 38.24% | 6021.393636800006 | 469.3128287999987 | 0 | False | annual_return,sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on |
| mp6_tr1_tu8_cr10_sw18_ind2_def3_cy1_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_current | 0.70% | 2.03% | -9.40% | 12.11% | 22 | 100.00% | 45.48% | 46.18% | 31.50% | 44.28% | 2111.448329600006 | -1076.9549491999987 | 1 | False | annual_return,sharpe,avg_cash_ratio_in_risk_on,cyclical_rotation_pnl |
| mp6_tr1_tu8_cr15_sw18_ind2_def4_cy1_lot100_gap10_rpm1_ro85_ne60_rf25_rep1_cyc1_current | 0.70% | 2.03% | -9.40% | 12.11% | 22 | 100.00% | 45.48% | 46.18% | 31.50% | 44.28% | 2111.448329600006 | -1076.9549491999987 | 1 | False | annual_return,sharpe,avg_cash_ratio_in_risk_on,cyclical_rotation_pnl |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_current | 3.41% | 10.13% | -20.61% | 27.23% | 15 | 100.00% | 59.87% | 35.45% | 31.98% | 40.54% | 4613.852150800005 | 469.3128287999987 | 1 | False | annual_return,sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc0_cyclical_disabled | 3.41% | 10.13% | -20.61% | 27.23% | 15 | 100.00% | 59.87% | 35.45% | 31.98% | 40.54% | 4613.852150800005 | 469.3128287999987 | 1 | False | annual_return,sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_disable_high_dividend_supplement | 3.05% | 9.04% | -21.46% | 25.33% | 12 | 100.00% | 47.66% | 44.83% | 39.57% | 44.16% | 4531.7714700000015 | 0.0 | 0 | False | annual_return,sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on |
| mp5_tr1_tu8_cr10_sw16_ind1_def3_cy0_lot90_gap8_rpm1_ro75_ne45_rf25_rep1_cyc1_current | 1.27% | 3.69% | -17.29% | 15.85% | 13 | 100.00% | 40.13% | 51.68% | 45.91% | 55.21% | 1696.3463888000006 | 162.89012160000007 | 0 | False | annual_return,sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on,largest_single_stock_pnl_contribution,largest_industry_pnl_contribution |

## 5. best candidate

- 没有候选通过硬条件。失败分布如下：
  - sharpe: 17
  - max_drawdown: 8
  - total_trades: 11
  - avg_cash_ratio_in_risk_on: 14
  - largest_industry_pnl_contribution: 2
  - annual_return: 15
  - cyclical_rotation_pnl: 5
  - largest_single_stock_pnl_contribution: 2

## 6. neighborhood robustness

- judgement: FRAGILE
- neighbor_count: 0
- supporting_neighbors_excluding_best: 0
- rule: excluding best, >=3 hard-condition neighbors is ACCEPTABLE; >=5 is ROBUST; otherwise FRAGILE.

## 7. attribution

- largest_single_stock_pnl_contribution: 0.00%
- largest_industry_pnl_contribution: 0.00%
- defensive_dividend_pnl: 0.00
- cyclical_rotation_pnl: 0.00
- realized_pnl: 0.00
- unrealized_pnl: 0.00

## 8. execution audit

- executable_account_actionable_ratio: 0.00%
- raw_buy_signal_count: 0
- watch_only_count: 0
- top_watch_only_reasons: {}
- replacement_count: 0
- average_cash_ratio: 0.00%

## 9. module contribution

- See `core_module_contribution_report.md`. Controls are research-only and do not delete modules automatically.

## 10. 结论

- This profile is paper trading / observation only.
- It does not allow automatic live trading.
- It does not replace the default release profile.
- Daily monitoring should track generated signals, executable buys, watch-only reasons, current exposure, cash ratio, industry concentration, paper fill slippage, and manual overrides.

## cash_sleeve note

- 50k low return still has cash drag. `cash_sleeve` is a future research interface, disabled by default, with no ETF result fabricated in this run.
