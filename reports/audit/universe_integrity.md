# universe integrity audit

- status: FAIL
- checked_at: 2026-05-05T09:09:34.569168+00:00
- git_commit: f0cd73e15a915b7af4373421dbb57797de0dea83
- config_hash: 0e89b4d194ac999b77ad51b3f22dba53a074999d2671518ffdcea8ec0121539f
- universe_file: config/universe.yml
- rules_file: config/universe_rules_v2.yml
- active_date: 2026-04-30
- selected_count: 8
- target/floor/ceiling: 36 / 24 / 48
- max_per_industry: 3
- market_cap_billion_min: 300

## FAIL

- UNIVERSE_UNDER_FLOOR:  selected universe count is below configured floor actual=8
- MISSING_KEY_FIELDS: 600018.sh selected constituent misses required fields actual=['pb']
- HARD_FILTER_VIOLATION: 600018.sh selected constituent violates hard filters without explicit override basis actual=['missing_pb', 'missing_pb', 'missing_latest_net_profit']
- MISSING_KEY_FIELDS: 600011.sh selected constituent misses required fields actual=['pb']
- HARD_FILTER_VIOLATION: 600011.sh selected constituent violates hard filters without explicit override basis actual=['missing_pe_ttm', 'missing_pb', 'missing_latest_net_profit', 'missing_debt_to_assets']
- MISSING_KEY_FIELDS: 600873.sh selected constituent misses required fields actual=['pb']
- HARD_FILTER_VIOLATION: 600873.sh selected constituent violates hard filters without explicit override basis actual=['market_cap_billion_below_market_cap_billion_min', 'missing_pb', 'missing_pb', 'missing_latest_net_profit']
- MISSING_KEY_FIELDS: 600690.sh selected constituent misses required fields actual=['pb']
- HARD_FILTER_VIOLATION: 600690.sh selected constituent violates hard filters without explicit override basis actual=['missing_pe_ttm', 'missing_pb', 'missing_latest_net_profit', 'missing_debt_to_assets']
- MISSING_KEY_FIELDS: 000786.sz selected constituent misses required fields actual=['pb']
- HARD_FILTER_VIOLATION: 000786.sz selected constituent violates hard filters without explicit override basis actual=['missing_pb', 'missing_pb', 'missing_latest_net_profit']
- MISSING_KEY_FIELDS: 603799.sh selected constituent misses required fields actual=['pb']
- HARD_FILTER_VIOLATION: 603799.sh selected constituent violates hard filters without explicit override basis actual=['missing_pb', 'missing_pb', 'missing_latest_net_profit']
- MISSING_KEY_FIELDS: 300628.sz selected constituent misses required fields actual=['pb']
- HARD_FILTER_VIOLATION: 300628.sz selected constituent violates hard filters without explicit override basis actual=['missing_pe_ttm', 'missing_pb', 'missing_latest_net_profit', 'missing_debt_to_assets']
- MISSING_KEY_FIELDS: 000708.sz selected constituent misses required fields actual=['pb']
- HARD_FILTER_VIOLATION: 000708.sz selected constituent violates hard filters without explicit override basis actual=['missing_pb', 'missing_pb', 'missing_latest_net_profit']

## WARN

- 无

## Constituents

- 600018.sh 上港集团 | 交通运输 | cyclical_rotation | market_cap_billion=1163.998 | selected_reason=retained | failed_filters=missing_pb,missing_pb,missing_latest_net_profit
- 600011.sh 华能国际 | 公用事业 | defensive_dividend | market_cap_billion=1097.2967 | selected_reason=retained | failed_filters=missing_pe_ttm,missing_pb,missing_latest_net_profit,missing_debt_to_assets
- 600873.sh 梅花生物 | 基础化工 | cyclical_rotation | market_cap_billion=278.1808 | selected_reason=retained | failed_filters=market_cap_billion_below_market_cap_billion_min,missing_pb,missing_pb,missing_latest_net_profit
- 600690.sh 海尔智家 | 家用电器 | defensive_dividend | market_cap_billion=2019.0037 | selected_reason=retained | failed_filters=missing_pe_ttm,missing_pb,missing_latest_net_profit,missing_debt_to_assets
- 000786.sz 北新建材 | 建筑材料 | cyclical_rotation | market_cap_billion=441.56 | selected_reason=retained | failed_filters=missing_pb,missing_pb,missing_latest_net_profit
- 603799.sh 华友钴业 | 有色金属 | cyclical_rotation | market_cap_billion=1263.0308 | selected_reason=retained | failed_filters=missing_pb,missing_pb,missing_latest_net_profit
- 300628.sz 亿联网络 | 通信 | defensive_dividend | market_cap_billion=462.7427 | selected_reason=retained | failed_filters=missing_pe_ttm,missing_pb,missing_latest_net_profit,missing_debt_to_assets
- 000708.sz 中信特钢 | 钢铁 | cyclical_rotation | market_cap_billion=769.6916 | selected_reason=retained | failed_filters=missing_pb,missing_pb,missing_latest_net_profit
