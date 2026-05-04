# combined_v2 收益归因报告

## 主口径摘要

- 主口径: combined_v2 PIT next_bar。
- next_bar 年化 7.14%，累计 21.96%，最大回撤 -9.36%，成交 76 笔。
- same_close 对照年化 6.68%，累计 20.50%，成交 76 笔。
- 月度收益已经改为连续 NAV 链；最后一行复合累计与 final NAV 累计差异 0.000000000000。
- 持仓期已经按实际持仓区间交易日去重；未平仓持仓统计到回测结束日。
- signal attribution 已拆分为 entry_signal、exit_signal、entry_exit_pair；当前无 lot 级成本账本，已用 FIFO lot 近似分摊 realized/unrealized PnL。
- regime attribution 同时保留 trade_realization_regime 与 daily_mtm_regime；后者按每日 NAV 变化盯市。
- 组合 total_pnl 44015.70，已实现 38533.83，未实现 5481.87。
- 最大单只股票贡献占总收益比例: 16.01%
- 最大单个行业贡献占总收益比例: 25.95%

## bucket attribution

- defensive_dividend: total_pnl 27465.66，已实现 21983.79，未实现 5481.87，成交 47，平均仓位 36.25%
- cyclical_rotation: total_pnl 16550.04，已实现 16550.04，未实现 0.00，成交 29，平均仓位 13.84%

## industry attribution

- 非银金融: total_pnl 11421.72，已实现 9715.53，未实现 1706.19，成交 11，贡献 25.95%
- 银行: total_pnl 9564.76，已实现 7444.09，未实现 2120.68，成交 13，贡献 21.73%
- 基础化工: total_pnl 6698.99，已实现 6698.99，未实现 0.00，成交 4，贡献 15.22%
- 有色金属: total_pnl 5749.09，已实现 5749.09，未实现 0.00，成交 6，贡献 13.06%
- 建筑材料: total_pnl 5202.48，已实现 5202.48，未实现 0.00，成交 6，贡献 11.82%
- 通信: total_pnl 4129.18，已实现 3655.24，未实现 473.95，成交 3，贡献 9.38%
- 公用事业: total_pnl 1851.93，已实现 2060.98，未实现 -209.04，成交 7，贡献 4.21%
- 钢铁: total_pnl 1380.43，已实现 1380.43，未实现 0.00，成交 4，贡献 3.14%
- 交通运输: total_pnl -321.30，已实现 -321.30，未实现 0.00，成交 13，贡献 -0.73%
- 石油石化: total_pnl -612.49，已实现 -612.49，未实现 0.00，成交 2，贡献 -1.39%
- 家用电器: total_pnl -1049.10，已实现 -2439.20，未实现 1390.10，成交 7，贡献 -2.38%

## position attribution

- 600000.sh 浦发银行: total_pnl 7048.44，已实现 7048.44，未实现 0.00，持仓日 507，open=False。
- 600176.sh 中国巨石: total_pnl 6526.68，已实现 6526.68，未实现 0.00，持仓日 333，open=False。
- 600426.sh 华鲁恒升: total_pnl 5415.12，已实现 5415.12，未实现 0.00，持仓日 201，open=False。
- 601688.sh 华泰证券: total_pnl 4380.74，已实现 4380.74，未实现 0.00，持仓日 177，open=False。
- 603799.sh 华友钴业: total_pnl 4140.19，已实现 4140.19，未实现 0.00，持仓日 154，open=False。
- 300628.sz 亿联网络: total_pnl 4129.18，已实现 3655.24，未实现 473.95，持仓日 405，open=True。
- 601211.sh 国泰海通: total_pnl 3575.29，已实现 3575.29，未实现 0.00，持仓日 335，open=False。
- 601601.sh 中国太保: total_pnl 2710.06，已实现 2710.06，未实现 0.00，持仓日 187，open=False。
- 601018.sh 宁波港: total_pnl 2583.02，已实现 2583.02，未实现 0.00，持仓日 545，open=False。
- 000708.sz 中信特钢: total_pnl 2082.33，已实现 2082.33，未实现 0.00，持仓日 143，open=False。
- 600803.sh 新奥股份: total_pnl 2060.98，已实现 2060.98，未实现 0.00，持仓日 396，open=False。
- 600926.sh 杭州银行: total_pnl 1801.10，已实现 1801.10，未实现 0.00，持仓日 79，open=False。

## entry signal attribution

- BUY_1: total_pnl 43868.69，已实现 38860.76，未实现 5007.92，win_rate 57.50%，profit_factor 4.30，avg_holding_days 223.60。
- BUY_2: total_pnl 147.01，已实现 -326.93，未实现 473.95，win_rate 50.00%，profit_factor 1.09，avg_holding_days 271.00。
- BUY_3: 无独立 BUY_3 entry attribution。
- GRID_ADD: 当前引擎没有独立 GRID_ADD 动作枚举，加仓记录在 BUY_2/BUY_3。

## exit signal attribution

- valuation_reversion_exit: realized_pnl 46116.80，total_pnl 46116.80，win_rate 93.75%，profit_factor 76.29，avg_holding_days 276.12。
- soft_trim: realized_pnl 4562.67，total_pnl 4562.67，win_rate 100.00%，profit_factor inf，avg_holding_days 198.50。
- cycle_peak_trap_trend_break: realized_pnl 698.35，total_pnl 698.35，win_rate 50.00%，profit_factor 2.19，avg_holding_days 229.00。
- trend_stop: realized_pnl -12844.00，total_pnl -12844.00，win_rate 0.00%，profit_factor 0.00，avg_holding_days 108.38。

## entry-exit pair attribution

- BUY_1 -> valuation_reversion_exit: total_pnl 44760.37，已实现 44760.37，未实现 0.00，样本 15。
- BUY_1 -> open_position: total_pnl 5007.92，已实现 0.00，未实现 5007.92，样本 7。
- BUY_1 -> soft_trim: total_pnl 4562.67，已实现 4562.67，未实现 0.00，样本 2。
- BUY_2 -> valuation_reversion_exit: total_pnl 1356.43，已实现 1356.43，未实现 0.00，样本 1。
- BUY_1 -> cycle_peak_trap_trend_break: total_pnl 698.35，已实现 698.35，未实现 0.00，样本 2。
- BUY_2 -> open_position: total_pnl 473.95，已实现 0.00，未实现 473.95，样本 1。
- BUY_2 -> trend_stop: total_pnl -1683.36，已实现 -1683.36，未实现 0.00，样本 2。
- BUY_1 -> trend_stop: total_pnl -11160.64，已实现 -11160.64，未实现 0.00，样本 14。

## trade realization regime attribution

- trade_realization_regime risk_on: realized_pnl 50076.42，卖出 20，avg_holding_days 242.75。
- trade_realization_regime neutral: realized_pnl -2663.14，卖出 4，avg_holding_days 105.75。
- trade_realization_regime risk_off: realized_pnl -8879.44，卖出 9，avg_holding_days 109.89。

## daily MTM regime attribution

- daily_mtm_regime neutral: 日盯市 PnL -3916.63，已实现 -2663.14，未实现/盯市 -1253.49，交易 20。
- daily_mtm_regime risk_off: 日盯市 PnL -18617.68，已实现 -8879.44，未实现/盯市 -9738.23，交易 14。
- daily_mtm_regime risk_on: 日盯市 PnL 66463.19，已实现 50076.42，未实现/盯市 16386.77，交易 42。

## holding period attribution

- 0-20: realized_pnl -696.67，卖出 1，avg_holding_days 12.00。
- 120+: realized_pnl 37341.29，卖出 20，avg_holding_days 271.25。
- 21-60: realized_pnl 379.72，卖出 5，avg_holding_days 44.40。
- 61-120: realized_pnl 1509.50，卖出 7，avg_holding_days 86.86。

## major winners

- 600000.sh 浦发银行: total_pnl 7048.44，行业 银行，bucket defensive_dividend。
- 600176.sh 中国巨石: total_pnl 6526.68，行业 建筑材料，bucket cyclical_rotation。
- 600426.sh 华鲁恒升: total_pnl 5415.12，行业 基础化工，bucket cyclical_rotation。
- 601688.sh 华泰证券: total_pnl 4380.74，行业 非银金融，bucket defensive_dividend。
- 603799.sh 华友钴业: total_pnl 4140.19，行业 有色金属，bucket cyclical_rotation。
- 300628.sz 亿联网络: total_pnl 4129.18，行业 通信，bucket defensive_dividend。
- 601211.sh 国泰海通: total_pnl 3575.29，行业 非银金融，bucket defensive_dividend。
- 601601.sh 中国太保: total_pnl 2710.06，行业 非银金融，bucket defensive_dividend。
- 601018.sh 宁波港: total_pnl 2583.02，行业 交通运输，bucket defensive_dividend。
- 000708.sz 中信特钢: total_pnl 2082.33，行业 钢铁，bucket cyclical_rotation。

## major losers

- 601166.sh 兴业银行: total_pnl -1969.68，行业 银行，bucket defensive_dividend。
- 601021.sh 春秋航空: total_pnl -1397.04，行业 交通运输，bucket cyclical_rotation。
- 601866.sh 中远海发: total_pnl -1035.86，行业 交通运输，bucket defensive_dividend。
- 601318.sh 中国平安: total_pnl -950.57，行业 非银金融，bucket defensive_dividend。
- 600027.sh 华电国际: total_pnl -939.34，行业 公用事业，bucket defensive_dividend。
- 600690.sh 海尔智家: total_pnl -931.13，行业 家用电器，bucket defensive_dividend。
- 000921.sz 海信家电: total_pnl -858.83，行业 家用电器，bucket defensive_dividend。
- 600233.sh 圆通速递: total_pnl -760.99，行业 交通运输，bucket cyclical_rotation。
- 000786.sz 北新建材: total_pnl -709.46，行业 建筑材料，bucket cyclical_rotation。
- 000932.sz 华菱钢铁: total_pnl -701.90，行业 钢铁，bucket cyclical_rotation。

## key answers

- combined_v2 的收益是否主要在 risk_on 日赚到: risk_on daily MTM PnL 为 66463.19，risk_on 卖出/成交日 realized PnL 为 50076.42；以 daily MTM 为主判断赚钱发生在哪些市场状态。
- risk_off 负收益来源: risk_off daily MTM PnL 为 -18617.68，risk_off realized PnL 为 -8879.44；若 realized 明显为负，说明 risk_off 中止损兑现占比高，否则更多来自持仓盯市波动。
- 当前是否需要直接替换 v2 为 v2_1_risk_guard: 不需要；v2_1_risk_guard 是更保守观察候选，不替换主口径。
- defensive_dividend total_pnl: 27465.66。
- cyclical_rotation total_pnl: 16550.04。
- 正贡献、负贡献和成交多但贡献低的行业见 `combined_v2_industry_attribution.csv`。
