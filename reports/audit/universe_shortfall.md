# universe shortfall report

- status: WARN
- active_date: 2026-04-30
- target_size: 36
- floor_size: 24
- selected_count: 30

## runtime profile

- account_profile: retail_50k_lot_aware
- initial_capital: 50000.0
- min_trade_value: 1500.0
- round_lot: 100
- universe_target_size: 36
- universe_floor: 24
- universe_selected_count: 30
- portfolio_max_positions: 8
- portfolio_equal_weight_target_positions: 8

## shortfall

- shortfall_to_target: 6
- candidate_pool_raw_count: 5151
- candidate_pool_count: 72
- largest_loss_layer: allowed_industry
- industry_cap_blocked_count: 30

## funnel

- raw_feature_rows: 5151
- allowed_industry_rows: 1340
- candidate_pool_rows: 72
- filtered_out_rows: 5079
- filter_loss_counts: {'industry_not_in_metric_map': 3811, 'market_cap_billion': 2090, 'roe': 595, 'st': 42, 'latest_net_profit': 225, 'dv_ttm': 361, 'debt_to_assets': 11, 'valuation': 162, 'industry_leader': 517, 'pb_q_blended': 593, 'avg_amount_60d_million': 56, 'cycle_trap': 29, 'roe_equity_non_positive': 6, 'listed_days': 126, 'pb_missing': 1, 'pb': 1}
- stage_loss_counts: {'allowed_industry': 3811, 'bucket_filter': 1267, 'candidate_pool': 72, 'data_coverage': 1}

## industry counts

- 交通运输: 3
- 公用事业: 3
- 基础化工: 3
- 家用电器: 3
- 建筑材料: 3
- 有色金属: 1
- 煤炭: 1
- 石油石化: 1
- 通信: 3
- 钢铁: 3
- 银行: 3
- 非银金融: 3

## top excluded candidates

- 601816.sh 京沪高铁 | 交通运输 | score=76.44687280158283 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap']
- 000333.sz 美的集团 | 家用电器 | score=76.29400461517217 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap']
- 600803.sh 新奥股份 | 公用事业 | score=74.68734578608549 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap']
- 002032.sz 苏 泊 尔 | 家用电器 | score=74.39196535584526 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 601919.sh 中远海控 | 交通运输 | score=74.08784451807426 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 601018.sh 宁波港 | 交通运输 | score=74.06540075436115 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 600642.sh 申能股份 | 公用事业 | score=73.77711040098946 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 600027.sh 华电国际 | 公用事业 | score=73.0738524475472 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 002736.sz 国信证券 | 非银金融 | score=72.64678694954658 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap']
- 001965.sz 招商公路 | 交通运输 | score=72.24007413209621 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 600233.sh 圆通速递 | 交通运输 | score=72.12598653983045 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 601006.sh 大秦铁路 | 交通运输 | score=71.60260647493321 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 601211.sh 国泰海通 | 非银金融 | score=71.43143287498043 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 601319.sh 中国人保 | 非银金融 | score=71.36848561061795 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 600886.sh 国投电力 | 公用事业 | score=71.31230956096793 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 601881.sh 中国银河 | 非银金融 | score=71.25865374242125 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 600023.sh 浙能电力 | 公用事业 | score=71.18219690246637 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 601601.sh 中国太保 | 非银金融 | score=71.17643151704372 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 600863.sh 华能蒙电 | 公用事业 | score=70.6174702393997 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 601598.sh 中国外运 | 交通运输 | score=70.18685097924751 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 600000.sh 浦发银行 | 银行 | score=70.04571605601451 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap']
- 600015.sh 华夏银行 | 银行 | score=69.50999695851938 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 600377.sh 宁沪高速 | 交通运输 | score=69.3190172434747 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 601880.sh 辽港股份 | 交通运输 | score=69.25405778813176 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 601818.sh 光大银行 | 银行 | score=68.57437940852908 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 002142.sz 宁波银行 | 银行 | score=68.37404578243081 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 601688.sh 华泰证券 | 非银金融 | score=68.33633477254959 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 600060.sh 海信视像 | 家用电器 | score=67.76665430660714 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 600900.sh 长江电力 | 公用事业 | score=67.51198035959787 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']
- 601866.sh 中远海发 | 交通运输 | score=67.3024953362209 | failed=[] | missing=[] | would_enter_if=['if_not_blocked_by_industry_cap', 'if_retained_or_new_ranking_allowed']

## warnings

- UNIVERSE_BELOW_TARGET: {'code': 'UNIVERSE_BELOW_TARGET', 'selected_count': 30, 'target_size': 36}
- DATA_COVERAGE_WARN: {'code': 'DATA_COVERAGE_WARN', 'filtered_out_count': 1}
