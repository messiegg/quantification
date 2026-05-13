# combined_v2 收益归因报告

## 主口径摘要

- 主口径: combined_v2 PIT next_bar。
- next_bar 年化 2.48%，累计 7.33%，最大回撤 -8.88%，成交 41 笔。
- same_close 对照年化 2.19%，累计 6.46%，成交 45 笔。
- 月度收益已经改为连续 NAV 链；最后一行复合累计与 final NAV 累计差异 0.000000000000。
- 持仓期已经按实际持仓区间交易日去重；未平仓持仓统计到回测结束日。
- signal attribution 已拆分为 entry_signal、exit_signal、entry_exit_pair；当前无 lot 级成本账本，已用 FIFO lot 近似分摊 realized/unrealized PnL。
- regime attribution 同时保留 trade_realization_regime 与 daily_mtm_regime；后者按每日 NAV 变化盯市。
- 组合 total_pnl 3680.69，已实现 40.71，未实现 3639.98。
- 最大单只股票贡献占总收益比例: 81.06%
- 最大单个行业贡献占总收益比例: 75.42%

## bucket attribution

- defensive_dividend: total_pnl 3954.22，已实现 314.24，未实现 3639.98，成交 24，平均仓位 37.58%
- cyclical_rotation: total_pnl -273.53，已实现 -273.53，未实现 0.00，成交 17，平均仓位 9.74%

## industry attribution

- 家用电器: total_pnl 2775.92，已实现 -596.65，未实现 3372.57，成交 6，贡献 75.42%
- 有色金属: total_pnl 822.91，已实现 822.91，未实现 0.00，成交 2，贡献 22.36%
- 银行: total_pnl 621.47，已实现 621.47，未实现 0.00，成交 7，贡献 16.88%
- 交通运输: total_pnl 483.97，已实现 483.97，未实现 0.00，成交 12，贡献 13.15%
- 基础化工: total_pnl 259.94，已实现 259.94，未实现 0.00，成交 2，贡献 7.06%
- 通信: total_pnl 192.45，已实现 0.00，未实现 192.45，成交 1，贡献 5.23%
- 公用事业: total_pnl 74.96，已实现 0.00，未实现 74.96，成交 1，贡献 2.04%
- 石油石化: total_pnl -245.00，已实现 -245.00，未实现 0.00，成交 2，贡献 -6.66%
- 钢铁: total_pnl -255.24，已实现 -255.24，未实现 0.00，成交 2，贡献 -6.93%
- 非银金融: total_pnl -495.24，已实现 -495.24，未实现 0.00，成交 2，贡献 -13.45%
- 建筑材料: total_pnl -555.45，已实现 -555.45，未实现 0.00，成交 4，贡献 -15.09%

## position attribution

- 000333.sz 美的集团: total_pnl 2983.68，已实现 0.00，未实现 2983.68，持仓日 546，open=True。
- 600000.sh 浦发银行: total_pnl 1626.56，已实现 1626.56，未实现 0.00，持仓日 507，open=False。
- 002532.sz 天山铝业: total_pnl 822.91，已实现 822.91，未实现 0.00，持仓日 78，open=False。
- 601018.sh 宁波港: total_pnl 742.97，已实现 742.97，未实现 0.00，持仓日 545，open=False。
- 002032.sz 苏 泊 尔: total_pnl 388.90，已实现 0.00，未实现 388.90，持仓日 707，open=True。
- 600018.sh 上港集团: total_pnl 372.62，已实现 372.62，未实现 0.00，持仓日 667，open=False。
- 600989.sh 宝丰能源: total_pnl 259.94，已实现 259.94，未实现 0.00，持仓日 337，open=False。
- 300628.sz 亿联网络: total_pnl 192.45，已实现 0.00，未实现 192.45，持仓日 405，open=True。
- 600023.sh 浙能电力: total_pnl 74.96，已实现 0.00，未实现 74.96，持仓日 101，open=True。
- 000877.sz 天山股份: total_pnl -204.91，已实现 -204.91，未实现 0.00，持仓日 29，open=False。
- 600346.sh 恒力石化: total_pnl -245.00，已实现 -245.00，未实现 0.00，持仓日 90，open=False。
- 601866.sh 中远海发: total_pnl -251.12，已实现 -251.12，未实现 0.00，持仓日 117，open=False。

## entry signal attribution

- BUY_1: total_pnl 3471.65，已实现 -168.33，未实现 3639.98，win_rate 45.00%，profit_factor 2.00，avg_holding_days 217.05。
- BUY_2: total_pnl 209.04，已实现 209.04，未实现 0.00，win_rate 75.00%，profit_factor 1.64，avg_holding_days 301.00。
- BUY_3: 无独立 BUY_3 entry attribution。
- GRID_ADD: 当前引擎没有独立 GRID_ADD 动作枚举，加仓记录在 BUY_2/BUY_3。

## exit signal attribution

- valuation_reversion_exit: realized_pnl 2683.23，total_pnl 2683.23，win_rate 80.00%，profit_factor 11.95，avg_holding_days 338.20。
- soft_trim: realized_pnl 636.83，total_pnl 636.83，win_rate 100.00%，profit_factor inf，avg_holding_days 163.33。
- cycle_peak_trap_trend_break: realized_pnl 259.94，total_pnl 259.94，win_rate 100.00%，profit_factor inf，avg_holding_days 337.00。
- trend_stop: realized_pnl -3539.28，total_pnl -3539.28，win_rate 0.00%，profit_factor 0.00，avg_holding_days 115.27。

## entry-exit pair attribution

- BUY_1 -> open_position: total_pnl 3639.98，已实现 0.00，未实现 3639.98，样本 4。
- BUY_1 -> valuation_reversion_exit: total_pnl 2204.47，已实现 2204.47，未实现 0.00，样本 3。
- BUY_1 -> soft_trim: total_pnl 578.27，已实现 578.27，未实现 0.00，样本 2。
- BUY_2 -> valuation_reversion_exit: total_pnl 478.76，已实现 478.76，未实现 0.00，样本 2。
- BUY_1 -> cycle_peak_trap_trend_break: total_pnl 259.94，已实现 259.94，未实现 0.00，样本 1。
- BUY_2 -> soft_trim: total_pnl 58.56，已实现 58.56，未实现 0.00，样本 1。
- BUY_2 -> trend_stop: total_pnl -328.28，已实现 -328.28，未实现 0.00，样本 1。
- BUY_1 -> trend_stop: total_pnl -3211.01，已实现 -3211.01，未实现 0.00，样本 10。

## trade realization regime attribution

- trade_realization_regime risk_on: realized_pnl 2877.80，卖出 10，avg_holding_days 277.80。
- trade_realization_regime neutral: realized_pnl -840.64，卖出 3，avg_holding_days 100.67。
- trade_realization_regime risk_off: realized_pnl -1996.44，卖出 5，avg_holding_days 139.20。

## daily MTM regime attribution

- daily_mtm_regime neutral: 日盯市 PnL -681.35，已实现 -840.64，未实现/盯市 159.29，交易 15。
- daily_mtm_regime risk_off: 日盯市 PnL -677.10，已实现 -1996.44，未实现/盯市 1319.34，交易 9。
- daily_mtm_regime risk_on: 日盯市 PnL 5021.74，已实现 2877.80，未实现/盯市 2143.94，交易 17。

## holding period attribution

- 120+: realized_pnl 1121.27，卖出 10，avg_holding_days 313.90。
- 21-60: realized_pnl -801.57，卖出 3，avg_holding_days 43.00。
- 61-120: realized_pnl -278.99，卖出 5，avg_holding_days 101.60。

## major winners

- 000333.sz 美的集团: total_pnl 2983.68，行业 家用电器，bucket defensive_dividend。
- 600000.sh 浦发银行: total_pnl 1626.56，行业 银行，bucket defensive_dividend。
- 002532.sz 天山铝业: total_pnl 822.91，行业 有色金属，bucket cyclical_rotation。
- 601018.sh 宁波港: total_pnl 742.97，行业 交通运输，bucket defensive_dividend。
- 002032.sz 苏 泊 尔: total_pnl 388.90，行业 家用电器，bucket defensive_dividend。
- 600018.sh 上港集团: total_pnl 372.62，行业 交通运输，bucket cyclical_rotation。
- 600989.sh 宝丰能源: total_pnl 259.94，行业 基础化工，bucket cyclical_rotation。
- 300628.sz 亿联网络: total_pnl 192.45，行业 通信，bucket defensive_dividend。
- 600023.sh 浙能电力: total_pnl 74.96，行业 公用事业，bucket defensive_dividend。
- 000877.sz 天山股份: total_pnl -204.91，行业 建筑材料，bucket cyclical_rotation。

## major losers

- 601166.sh 兴业银行: total_pnl -656.56，行业 银行，bucket defensive_dividend。
- 601318.sh 中国平安: total_pnl -495.24，行业 非银金融，bucket defensive_dividend。
- 600233.sh 圆通速递: total_pnl -380.50，行业 交通运输，bucket cyclical_rotation。
- 000786.sz 北新建材: total_pnl -350.54，行业 建筑材料，bucket cyclical_rotation。
- 600036.sh 招商银行: total_pnl -348.53，行业 银行，bucket defensive_dividend。
- 600690.sh 海尔智家: total_pnl -310.38，行业 家用电器，bucket defensive_dividend。
- 000921.sz 海信家电: total_pnl -286.28，行业 家用电器，bucket defensive_dividend。
- 000932.sz 华菱钢铁: total_pnl -255.24，行业 钢铁，bucket cyclical_rotation。
- 601866.sh 中远海发: total_pnl -251.12，行业 交通运输，bucket defensive_dividend。
- 600346.sh 恒力石化: total_pnl -245.00，行业 石油石化，bucket cyclical_rotation。

## key answers

- combined_v2 的收益是否主要在 risk_on 日赚到: risk_on daily MTM PnL 为 5021.74，risk_on 卖出/成交日 realized PnL 为 2877.80；以 daily MTM 为主判断赚钱发生在哪些市场状态。
- risk_off 负收益来源: risk_off daily MTM PnL 为 -677.10，risk_off realized PnL 为 -1996.44；若 realized 明显为负，说明 risk_off 中止损兑现占比高，否则更多来自持仓盯市波动。
- 当前是否需要直接替换 v2 为 v2_1_risk_guard: 不需要；v2_1_risk_guard 是更保守观察候选，不替换主口径。
- defensive_dividend total_pnl: 3954.22。
- cyclical_rotation total_pnl: -273.53。
- 正贡献、负贡献和成交多但贡献低的行业见 `combined_v2_industry_attribution.csv`。
