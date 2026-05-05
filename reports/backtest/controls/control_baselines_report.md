# control baselines 报告

- 口径: 2023-04-03 到 2026-04-03，next_bar，统一账户、费用、印花税、滑点、整手和最小成交额。
- 本脚本只使用配置副本，不写回 `config/strategy_v2.yml` 或 `config/universe_rules_v2.yml`。

## 关键结论

- combined_v2 是否显著优于原 baseline next_bar: 是；v2 年化 7.14%，baseline 年化 0.10%。
- combined_v2 是否优于 v2_universe_equal_weight_monthly: 是；equal weight 年化 -1.33%。
- combined_v2 是否优于 v2_top_score_monthly: 是；top score 年化 3.33%。
- 收益主要来自股票池本身还是交易信号: 交易信号贡献更明显。
- defensive_only vs cyclical_only: defensive 年化 5.82%、回撤 -7.95%；cyclical 年化 2.81%、回撤 -2.96%。
- 高股息补充触发是否贡献主要收益: 禁用后年化 8.11%，相对 v2 变化 0.98%。
- 网格是否有实际贡献: 禁用后年化 5.80%，成交 75；若与 v2 接近，说明当前 GRID_ADD/GRID_TRIM 贡献有限。
- trend_stop 是保护还是拖累: 禁用后年化 8.23%、回撤 -8.82%；该项只作风险解释，不能作为主策略。
- risk_off 新买入是否值得保留: risk_off 禁新买后年化 6.68%、回撤 -9.23%。
- no_market_state_filter 仅研究用途: 年化 8.30%、回撤 -12.42%，不能作为实盘口径。
- no_industry_cap 仅研究用途: 年化 6.61%、回撤 -9.09%，不能作为实盘口径。
- relaxed_account_constraints 仅研究用途: 年化 6.99%、回撤 -9.71%，不能作为实盘口径。
- combined_v2 在 random placebo 年化分布中的 percentile: 96.0%。

## 指标明细

- baseline_combined_next_bar: 年化 0.10%，累计 0.30%，回撤 -1.66%，夏普 0.10，成交 7，平均仓位 2.66%
- combined_v2_next_bar: 年化 7.14%，累计 21.96%，回撤 -9.36%，夏普 0.78，成交 76，平均仓位 46.98%
- v2_universe_equal_weight_monthly: 年化 -1.33%，累计 -3.79%，回撤 -23.90%，夏普 -0.08，成交 257，平均仓位 54.07%
- v2_top_score_monthly: 年化 3.33%，累计 9.90%，回撤 -19.43%，夏普 0.30，成交 359，平均仓位 61.88%
- v2_defensive_only: 年化 5.82%，累计 17.72%，回撤 -7.95%，夏普 0.75，成交 43，平均仓位 38.34%
- v2_cyclical_only: 年化 2.81%，累计 8.31%，回撤 -2.96%，夏普 0.82，成交 30，平均仓位 15.17%
- v2_no_high_dividend_supplement: 年化 8.11%，累计 25.19%，回撤 -7.35%，夏普 0.98，成交 60，平均仓位 46.46%
- v2_no_grid: 年化 5.80%，累计 17.62%，回撤 -9.36%，夏普 0.63，成交 75，平均仓位 48.62%
- v2_no_trend_stop: 年化 8.23%，累计 25.59%，回撤 -8.82%，夏普 0.78，成交 54，平均仓位 55.20%
- v2_risk_off_no_new_buy: 年化 6.68%，累计 20.47%，回撤 -9.23%，夏普 0.75，成交 72，平均仓位 45.83%
- v2_no_market_state_filter: 年化 8.30%，累计 25.82%，回撤 -12.42%，夏普 0.79，成交 81，平均仓位 50.88%
- v2_relaxed_account_constraints_research_only: 年化 6.99%，累计 21.50%，回撤 -9.71%，夏普 0.69，成交 79，平均仓位 56.14%
- v2_no_industry_cap: 年化 6.61%，累计 20.26%，回撤 -9.09%，夏普 0.69，成交 84，平均仓位 54.19%

## random placebo 分布

- mean: 年化 3.50%，最大回撤 -17.72%，夏普 0.31
- median: 年化 3.45%，最大回撤 -17.27%，夏普 0.31
- p5: 年化 0.34%，最大回撤 -22.64%，夏普 0.09
- p25: 年化 2.26%，最大回撤 -19.78%，夏普 0.22
- p75: 年化 4.86%，最大回撤 -15.57%，夏普 0.41
- p95: 年化 6.54%，最大回撤 -13.51%，夏普 0.53
