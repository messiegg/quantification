# 50k core repair experiment report

- research_only: true
- auto_trading_approved: false
- release_profile_replacement: false
- status: NO_REPAIR_CANDIDATE
- experiment_count: 17
- hard_condition_pass_count: 0

## 修复动机

- 来自 stage1 诊断：Sharpe、回撤、交易密度和 risk-on cash drag 是主要阻断。
- repair 不放宽硬条件，只测试 monthly review、replacement 参数、partial de-risk、cyclical sleeve 和模块 overlay。

## top variants

| variant                                                                                                                                 |   annual_return |   max_drawdown |   sharpe |   total_trades |   avg_cash_ratio_in_risk_on |   replacement_count | pass_hard_conditions   | fail_reasons                                                                     |
|:----------------------------------------------------------------------------------------------------------------------------------------|----------------:|---------------:|---------:|---------------:|----------------------------:|--------------------:|:-----------------------|:---------------------------------------------------------------------------------|
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_disable_both_monthly_review                               |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                   1 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                       |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap6_rpm1_ro85_ne60_rf25_rep1_cyc1_disable_both_rep_gap6_hold20_rpm1                         |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                   1 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                       |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap6_rpm2_ro85_ne60_rf25_rep1_cyc1_disable_both_rep_gap6_hold20_rpm2                         |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                   1 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                       |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap6_rpm1_ro85_ne60_rf25_rep1_cyc1_disable_both_rep_gap6_hold40_rpm1                         |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                   1 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                       |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap6_rpm2_ro85_ne60_rf25_rep1_cyc1_disable_both_rep_gap6_hold40_rpm2                         |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                   1 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                       |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_disable_both_rep_gap8_hold20_rpm1                         |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                   1 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                       |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap8_rpm2_ro85_ne60_rf25_rep1_cyc1_disable_both_rep_gap8_hold20_rpm2                         |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                   1 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                       |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_disable_both_rep_gap8_hold40_rpm1                         |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                   1 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                       |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap8_rpm2_ro85_ne60_rf25_rep1_cyc1_disable_both_rep_gap8_hold40_rpm2                         |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                   1 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                       |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap10_rpm1_ro85_ne60_rf25_rep1_cyc1_disable_both_rep_gap10_hold20_rpm1                       |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                   1 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                       |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap10_rpm2_ro85_ne60_rf25_rep1_cyc1_disable_both_rep_gap10_hold20_rpm2                       |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                   1 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                       |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap10_rpm1_ro85_ne60_rf25_rep1_cyc1_disable_both_rep_gap10_hold40_rpm1                       |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                   1 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                       |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap10_rpm2_ro85_ne60_rf25_rep1_cyc1_disable_both_rep_gap10_hold40_rpm2                       |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                   1 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                       |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc0_disable_both_cyclical_watch_only                          |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                   1 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                       |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_disable_both_disable_both_control                         |       0.0980293 |      -0.160391 | 0.619853 |             10 |                    0.364556 |                   1 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on                       |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy1_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_disable_both_cyclical_one_strict                          |       0.0866806 |      -0.170735 | 0.562424 |             10 |                    0.381368 |                   2 | False                  | sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on,cyclical_rotation_pnl |
| mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_disable_high_dividend_supplement_partial_derisk_hardtrend |       0.0482677 |      -0.152756 | 0.436982 |             20 |                    0.543653 |                   1 | False                  | annual_return,sharpe,max_drawdown,avg_cash_ratio_in_risk_on                      |

## closest gap

- closest_variant: mp5_tr1_tu8_cr10_sw18_ind2_def3_cy0_lot100_gap8_rpm1_ro85_ne60_rf25_rep1_cyc1_disable_both_monthly_review
- annual_return: 9.80%
- max_drawdown: -16.04%
- sharpe: 0.6199
- total_trades: 10
- fail_reasons: sharpe,max_drawdown,total_trades,avg_cash_ratio_in_risk_on

## overtrading and safety

- total_trades must remain between 20 and 60 under original hard conditions.
- no broker integration, no real trades, no LLM decision authority.
