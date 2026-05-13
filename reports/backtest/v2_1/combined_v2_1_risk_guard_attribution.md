# combined_v2_1_risk_guard 归因摘要

- universe、score、基础过滤沿用 combined_v2；本候选只改变 market regime 风险侧买入限制。
- 年化 1.99%，累计 5.83%，最大回撤 -4.27%，成交 21。
- risk_off daily PnL -910.18，neutral daily PnL -29.75。

## entry / exit signal

- entry_signal BUY_1: total_pnl 2921.16，realized 2972.21，unrealized -51.05，count 12。
- exit_signal SELL_ALL / cycle_peak_trap_trend_break: total_pnl -232.42，realized -232.42，unrealized 0.00，count 1。
- exit_signal SELL_ALL / trend_stop: total_pnl -734.07，realized -734.07，unrealized 0.00，count 3。
- exit_signal SELL_ALL / valuation_reversion_exit: total_pnl 3938.70，realized 3938.70，unrealized 0.00，count 5。

## position

- 600000.sh 浦发银行: total_pnl 1626.56，holding_days 507，open=False。
- 601688.sh 华泰证券: total_pnl 876.15，holding_days 177，open=False。
- 600803.sh 新奥股份: total_pnl 609.29，holding_days 404，open=False。
- 002532.sz 天山铝业: total_pnl 304.18，holding_days 164，open=False。
- 600011.sh 华能国际: total_pnl 95.01，holding_days 247，open=True。
- 600023.sh 浙能电力: total_pnl 74.96，holding_days 101，open=True。
- 600018.sh 上港集团: total_pnl 72.40，holding_days 672，open=False。
- 600027.sh 华电国际: total_pnl -221.02，holding_days 254，open=True。
- 601866.sh 中远海发: total_pnl -251.12，holding_days 117，open=False。
- 600926.sh 杭州银行: total_pnl -265.24，holding_days 48，open=False。
