# 当前可调参数表

生成日期：2026-05-08

范围：当前分支的 `combined_v2` 默认配置、50k 默认账户、候选池、观察准入和 research-only profile。`config/universe.yml`、`config/positions.yml` 这类生成/状态文件不作为可调策略参数。

边界：

- 当前默认 release/account 口径是 `retail_50k_lot_aware`，不是 200k。
- `reference_200k`、`combined_v2_50k_compact` 都是 research-only，不能直接替换默认 release 口径。
- `config/strategy_v2.yml` 是当前 combined_v2 买入、加仓、减仓、退出阈值的主要事实源。
- 修改这些参数后，旧 RC hash 会失效，必须重新跑对应验证/重建报告，不能只改表面数值。
- 本项目仍禁止接入券商、自动下单、真实订单执行或让 LLM 决定买卖。

| 模块 | 参数 | 当前值 | 解释 |
|---|---|---:|---|
| 账户 | `account_profile` | `retail_50k_lot_aware` | 当前默认 release/account 口径 |
| 账户 | `initial_capital` | 50000 | 默认账户初始资金 |
| 账户 | `current_cash` | 50000 | 当前现金假设 |
| 账户 | `reserved_cash` | 0 | 预留现金 |
| 账户 | `latest_total_equity` | 50000 | 当前总权益 |
| 成本 | `commission_rate` | 0.0003 | 买卖佣金 |
| 成本 | `stamp_duty_rate_sell` | 0.0005 | 卖出印花税 |
| 成本 | `slippage_bps` | 5 | 滑点，5bp |
| 成本 | `round_lot` | 100 | A 股整手约束 |
| 仓位 | `max_tranches_per_stock` | 3 | 单票最多分 3 档 |
| 仓位 | `tranche_weights` | 3% / 6% / 9% | 账户层分档目标仓位 |
| 仓位 | `max_single_stock_weight` | 12% | 单票账户层上限 |
| 仓位 | `min_trade_value` | 1500 | 最小成交金额 |
| 执行 | `trade_at` | `next_day_open` | 信号后下一交易日开盘成交 |
| 执行 | `default_tranches` | 3 | 策略默认分 3 档 |
| 执行 | `equal_weight_target_universe_size` | 8 | 当前 50k lot-aware 目标持仓数 |
| 执行 | `max_positions` | 8 | 最大持仓数量 |
| 执行 | `max_new_positions_per_day` | 1 | 每日最多新开仓数 |
| 执行 | `max_adds_per_day` | 2 | 每日最多加仓次数 |
| 执行 | `lot_aware_sizing` | true | 是否按整手约束前置规划 |
| 执行 | `pending_add_state` | true | 是否记录待加仓状态 |
| 执行 | `duplicate_blocked_signal_suppression` | true | 是否抑制重复 blocked 信号 |
| 市场状态 | `benchmark_index` | 000300 | 市场状态基准指数 |
| 市场状态 | `ma60` / `ma200` | 60 / 200 | 判断市场状态的均线窗口 |
| 市场状态 | `max_total_position.risk_on` | 95% | risk_on 最大总仓位 |
| 市场状态 | `max_total_position.neutral` | 70% | neutral 最大总仓位 |
| 市场状态 | `max_total_position.risk_off` | 40% | risk_off 最大总仓位 |
| 市场状态 | `target_exposure_floor.risk_on` | 50% | risk_on 目标最低暴露 |
| 市场状态 | `target_exposure_floor.neutral` | 25% | neutral 目标最低暴露 |
| 市场状态 | `target_exposure_floor.risk_off` | 0% | risk_off 目标最低暴露 |
| 市场状态 | `block_new_in_risk_off` | false | risk_off 是否禁止新开仓 |
| 估值 | `q_5y` / `q_10y` | 5 / 10 | 估值分位历史窗口 |
| 估值 | `blended_weights` | 0.6 / 0.4 | 5 年/10 年分位混合权重 |
| 估值 | `trading_days_per_year` | 252 | 年化交易日假设 |
| 网格 | `grid_execution.enabled` | true | 是否启用网格加减仓判断 |
| 网格 | `atr_multiplier` | 1.2 | ATR 网格步长倍数 |
| 网格 | `min_step` | 3.5% | 最小网格间距 |
| 网格 | `max_step` | 8% | 最大网格间距 |
| 网格 | `reduce_extra_min_stock_q_blended` | 55 | 网格减仓估值分位门槛 |
| 加仓硬禁 | `close_to_ma250_min` | 1.0 | 收盘价/MA250 低于该值时参与硬禁 |
| 加仓硬禁 | `ma120_slope_20d_min` | 0 | MA120 斜率低于该值时参与硬禁 |
| 趋势止损 | `close_lt_ma` | `ma250` | 趋势止损使用的均线 |
| 趋势止损 | `ma120_slope_20d_lt` | 0 | 趋势转弱斜率条件 |
| 趋势止损 | `unrealized_pnl_pct_lte` | -12% | 趋势止损亏损阈值 |
| 财报时点 | `use_announcement_date` | true | 财务数据按公告日生效 |
| 财报时点 | `fallback_days` | 30 | 缺公告日时按报告日后 30 天生效 |
| 基本面破坏 | `latest_net_profit_max` | 0 | 净利润不大于 0 触发破坏条件 |
| 基本面破坏 | `roe_min` | 非金融 3 / 金融 3 | ROE 下限 |
| 基本面破坏 | `cfo_ttm_non_positive_periods` | 2 | 非金融经营现金流连续非正阈值 |
| 候选池 | `target_size` | 36 | combined_v2 目标候选池规模 |
| 候选池 | `floor_size` | 24 | 候选池最低 floor |
| 候选池 | `ceiling_size` | 48 | 候选池最高 ceiling |
| 候选池 | `max_names_per_industry` | 3 | 单行业最多入池数量 |
| 候选池 | `retained_min_score` | 50 | 老成员保留最低分 |
| 候选池 | `new_min_score` | 55 | 新成员入池最低分 |
| 候选池 | `retained_industry_rank` | 6 | 老成员行业内保留排名 |
| 候选池 | `new_industry_rank` | 4 | 新成员行业内入选排名 |
| 候选池 | `floor_fill_min_score` | 52 | floor 补位最低分 |
| 候选池 | `freeze_removed_holdings` | true | 出池但仍持仓时冻结而非强制卖出 |
| 候选池 | `data_stale_blocks_new_entries` | true | 数据 stale 时阻断新入池 |
| 候选池 | `prolonged_data_failure_days` | 10 | 长期数据失败天数阈值 |
| 候选池 | `long_suspension_days` | 20 | 长停牌天数阈值 |
| 候选池基础过滤 | `listed_days_min` | 1000 | 最少上市天数 |
| 候选池基础过滤 | `avg_amount_60d_million_min` | 50 | 60 日成交额下限，百万元 |
| 候选池基础过滤 | `market_cap_billion_min` | 300 | 市值下限，十亿元 |
| 防御股池 | `bucket_targets.min/max` | 18 / 28 | 防御股目标数量范围 |
| 周期股池 | `bucket_targets.min/max` | 10 / 20 | 周期股目标数量范围 |
| 防御股过滤 | `roe_min` | 6 | ROE 下限 |
| 防御股过滤 | `debt_to_assets_max` | 85 | 资产负债率上限 |
| 防御股过滤 | `dv_ttm_min` | 2.5% | 股息率下限 |
| 防御股过滤 | `pe_ttm_max_when_primary_metric` | 25 | PE 主指标时上限 |
| 防御股过滤 | `pb_q_blended_max_when_primary_metric` | 75 | PB 分位上限 |
| 周期股过滤 | `roe_min` | 3 | ROE 下限 |
| 周期股过滤 | `pb_q_blended_max` | 60 | PB 分位上限 |
| 周期股过滤 | `market_cap_industry_rank_top_n` | 10 | 行业内市值排名要求 |
| 周期股过滤 | `market_cap_industry_rank_top_pct` | 40% | 行业内市值百分位要求 |
| 打分 | 防御 final 权重 | 估值35/质量30/股息20/龙头15 | 防御股最终评分权重 |
| 打分 | 周期 final 权重 | 估值40/质量25/龙头20/周期安全15 | 周期股最终评分权重 |
| 防御买入 | `BUY_1.final_score_min` | 55 | BUY_1 最低分 |
| 防御买入 | `BUY_1.stock_q_max` | 40 | BUY_1 个股估值分位上限 |
| 防御买入 | `BUY_1.industry_q_max` | 55 | BUY_1 行业估值分位上限 |
| 防御买入 | `BUY_1.close_to_ma120_max` | 1.00 | BUY_1 价格相对 MA120 上限 |
| 防御买入 | `BUY_1.dv_ttm_min` | 2.5% | BUY_1 股息率下限 |
| 防御买入 | `BUY_2.final_score_min` | 60 | BUY_2 最低分 |
| 防御买入 | `BUY_2.stock_q_max` | 30 | BUY_2 个股估值分位上限 |
| 防御买入 | `BUY_2.industry_q_max` | 45 | BUY_2 行业估值分位上限 |
| 防御买入 | `BUY_2.close_to_ma120_max` | 0.96 | BUY_2 价格相对 MA120 上限 |
| 防御买入 | `BUY_2.elapsed_fallback.days` | 20 | 网格不满足时，至少间隔天数 |
| 防御买入 | `BUY_3.final_score_min` | 65 | BUY_3 最低分 |
| 防御买入 | `BUY_3.stock_q_max` | 20 | BUY_3 个股估值分位上限 |
| 防御买入 | `BUY_3.industry_q_max` | 35 | BUY_3 行业估值分位上限 |
| 防御买入 | `BUY_3.close_to_ma120_max` | 0.92 | BUY_3 价格相对 MA120 上限 |
| 高股息补充 | `enabled` | true | 是否启用高股息补充 BUY_1 |
| 高股息补充 | `dv_ttm_min` | 4.5% | 高股息补充股息率下限 |
| 高股息补充 | `final_score_min` | 65 | 高股息补充分数下限 |
| 高股息补充 | `stock_q_max` | 45 | 高股息补充估值分位上限 |
| 高股息补充 | `close_to_ma120_max` | 1.03 | 高股息补充价格上限 |
| 防御退出 | 估值回归清仓 | stock_q>=90 且 close/MA120>=1.10；或 industry_q>=90 且 stock_q>=80 | 防御股估值回归退出 |
| 防御减仓 | soft trim | stock_q>=65 且 close/MA120>=1.05；或 grid_trim_ok | 防御股软减仓 |
| 周期买入 | `BUY_1.final_score_min` | 55 | BUY_1 最低分 |
| 周期买入 | `BUY_1.stock_q_max` | 35 | BUY_1 个股估值分位上限，当前走 PB |
| 周期买入 | `BUY_1.industry_q_max` | 45 | BUY_1 行业估值分位上限 |
| 周期买入 | `BUY_1.close_to_ma120_max` | 1.08 | BUY_1 价格相对 MA120 上限 |
| 周期买入 | `BUY_1.momentum` | close>=MA20 或 MA20斜率>=0 | BUY_1 动量确认 |
| 周期买入 | `BUY_2.final_score_min` | 60 | BUY_2 最低分 |
| 周期买入 | `BUY_2.stock_q_max` | 25 | BUY_2 个股估值分位上限 |
| 周期买入 | `BUY_2.industry_q_max` | 35 | BUY_2 行业估值分位上限 |
| 周期买入 | `BUY_2.momentum` | close>=MA60，或 close>=MA20 且 MA20斜率>0 | BUY_2 动量确认 |
| 周期买入 | `BUY_2.elapsed_fallback.days` | 20 | 网格不满足时，至少间隔天数 |
| 周期买入 | `BUY_3.final_score_min` | 65 | BUY_3 最低分 |
| 周期买入 | `BUY_3.stock_q_max` | 15 | BUY_3 个股估值分位上限 |
| 周期买入 | `BUY_3.industry_q_max` | 25 | BUY_3 行业估值分位上限 |
| 周期买入 | `BUY_3.momentum` | close>=MA60 且 MA20斜率>=0 | BUY_3 动量确认 |
| 周期陷阱 | `pe_q_blended_max_primary` | 20 | 周期陷阱 PE 分位条件 |
| 周期陷阱 | `roe_pct_in_last_12_quarters_min_primary` | 80 | 周期陷阱 ROE 历史百分位条件 |
| 周期陷阱 | `lookback_quarters` | 12 | 周期陷阱观察季度数 |
| 周期退出 | 估值回归清仓 | stock_q>=85 或 industry_q>=90 | 周期股估值回归退出 |
| 周期减仓 | soft trim | stock_q>=60 且 close>=MA20；或 grid_trim_ok | 周期股软减仓 |
| 行业映射 | `industry_bucket_map` | 银行/非银/通信/公用/家电等->防御；煤炭/有色/钢铁等->周期 | 行业默认归属 bucket |
| 估值指标 | `industry_metric_map` | 金融/周期多用 PB，通信/公用/家电等用 PE | 不同行业使用的估值分位主指标 |
| 默认估值指标 | `bucket_default_metric` | 防御 PE，周期 PB | bucket 缺省估值指标 |
| 观察 | `primary_profile` | combined_v2 | 观察主 profile |
| 观察 | `conservative_profile` | combined_v2_1_risk_guard | 保守对照 profile |
| 观察 | `execution_mode` | next_bar | 观察成交假设 |
| 观察 | `mode` | paper_observation_only | 仅纸面观察 |
| 观察 | `allow_broker_connection` | false | 禁止券商连接 |
| 观察 | `allow_auto_order` | false | 禁止自动下单 |
| 观察 | `allow_llm_decision` | false | 禁止 LLM 决策 |
| 观察 | `max_stale_calendar_days_for_daily_report` | 3 | 日报允许的日历 stale 天数 |
| 观察 | `max_stale_trading_days_for_daily_report` | 0 | 日报允许的交易日 stale 天数 |
| 观察 | `generate_real_orders` | false | 不生成真实订单 |
| 观察 | `initial_paper_capital` | 200000 | 纸面账户初始资金，仅观察账本 |
| 观察准入 | `minimum_observation_trading_days` | 60 | 进入更高状态前最少观察交易日 |
| 观察准入 | `maximum_hard_fail_count` | 0 | 硬失败允许次数 |
| 观察准入 | `minimum_executable_raw_buy_ratio` | 25% | 观察准入执行率门槛 |
| 观察准入 | `require_manual_review_log` | true | 要求人工复核日志 |
| 观察准入 | `require_evidence_chain_every_day` | true | 要求每日证据链 |
| research-only | `reference_200k.initial_capital` | 200000 | 200k 研究对照资金 |
| research-only | `reference_200k.max_positions` | 20 | 200k 研究对照最大持仓 |
| research-only | `reference_200k.min_trade_value` | 5000 | 200k 研究对照最小成交额 |
| research-only | `reference_200k.max_new/adds` | 3 / 5 | 200k 研究对照日内节流 |
| research-only | `50k_compact.max_positions` | 4/5/6/8 | 50k compact 实验持仓数网格 |
| research-only | `50k_compact.cash_reserve_ratio` | 10%/15%/20% | 50k compact 现金预留网格 |
| research-only | `50k_compact.max_tranches` | 1/2 | 50k compact 分档网格 |
| research-only | `50k_compact.target_universe_size` | 8/10/12 | 50k compact 目标池网格 |
| research-only | `50k_compact.executable_actionable_min` | 80% | compact 硬筛执行率门槛 |
| research-only | `50k_compact.max_exposure_max` | 85% | compact 硬筛最大暴露上限 |
