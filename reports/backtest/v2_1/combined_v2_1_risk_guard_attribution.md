# combined_v2_1_risk_guard 归因摘要

- universe、score、基础过滤沿用 combined_v2；本候选只改变 market regime 风险侧买入限制。
- 年化 5.60%，累计 17.01%，最大回撤 -8.88%，成交 64。
- risk_off daily PnL -18383.28，neutral daily PnL -3857.74。

## entry / exit signal

- entry_signal BUY_1: total_pnl 34248.64，realized 28907.28，unrealized 5341.36，count 35。
- entry_signal BUY_2: total_pnl -157.87，realized -157.87，unrealized 0.00，count 3。
- exit_signal REDUCE / soft_trim: total_pnl 641.20，realized 641.20，unrealized 0.00，count 1。
- exit_signal SELL_ALL / cycle_peak_trap_trend_break: total_pnl -585.52，realized -585.52，unrealized 0.00，count 1。
- exit_signal SELL_ALL / trend_stop: total_pnl -10684.43，realized -10684.43，unrealized 0.00，count 13。
- exit_signal SELL_ALL / valuation_reversion_exit: total_pnl 39378.16，realized 39378.16，unrealized 0.00，count 15。

## position

- 600000.sh 浦发银行: total_pnl 7048.44，holding_days 507，open=False。
- 600176.sh 中国巨石: total_pnl 6526.68，holding_days 333，open=False。
- 601688.sh 华泰证券: total_pnl 4690.89，holding_days 180，open=False。
- 603799.sh 华友钴业: total_pnl 4140.19，holding_days 154，open=False。
- 601211.sh 国泰海通: total_pnl 3575.29，holding_days 335，open=False。
- 601601.sh 中国太保: total_pnl 3406.74，holding_days 174，open=False。
- 600803.sh 新奥股份: total_pnl 2437.17，holding_days 404，open=False。
- 601018.sh 宁波港: total_pnl 2420.94，holding_days 485，open=False。
- 600926.sh 杭州银行: total_pnl 1801.10，holding_days 79，open=False。
- 600999.sh 招商证券: total_pnl 1706.19，holding_days 693，open=True。
