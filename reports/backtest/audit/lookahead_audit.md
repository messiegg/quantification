# 前视偏差审计

- 审计结论: WARN
- 固定区间: 2023-04-03 到 2026-04-03
- 财务字段 fallback_lag: 30 天
- 确认违规条数: 0
- 估值分位抽样: 20 条，失败 0 条
- resolver 字段解析: 1638 条，WARN 2 条，FAIL 0 条
- combined_v2 月度股票池 PIT 文件数: 38，future-data 文件数: 0

## 检查项

- LH-FIN-roe PASS: roe availability。证据：non_null=3654994, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-net_profit_ttm_effective PASS: net_profit_ttm_effective availability。证据：non_null=3674369, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-latest_net_profit PASS: latest_net_profit availability。证据：non_null=3674369, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-cfo_ttm PASS: cfo_ttm availability。证据：non_null=3632366, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-debt_to_assets PASS: debt_to_assets availability。证据：non_null=3674293, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-dv_ttm PASS: dv_ttm availability。证据：non_null=3674369, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-pe_ttm PASS: pe_ttm availability。证据：non_null=2753406, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-pb PASS: pb availability。证据：non_null=3667711, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-stock_pb_q_5y PASS: stock_pb_q_5y availability。证据：non_null=3667711, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-stock_pb_q_10y PASS: stock_pb_q_10y availability。证据：non_null=3667711, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-stock_pb_q_blended PASS: stock_pb_q_blended availability。证据：non_null=3667711, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-stock_pe_ttm_q_5y PASS: stock_pe_ttm_q_5y availability。证据：non_null=2753406, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-stock_pe_ttm_q_10y PASS: stock_pe_ttm_q_10y availability。证据：non_null=2753406, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-stock_pe_ttm_q_blended PASS: stock_pe_ttm_q_blended availability。证据：non_null=2753406, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-industry_pb_q_5y PASS: industry_pb_q_5y availability。证据：non_null=3668724, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-industry_pb_q_10y PASS: industry_pb_q_10y availability。证据：non_null=3668724, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-industry_pb_q_blended PASS: industry_pb_q_blended availability。证据：non_null=3668724, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-industry_pe_ttm_q_5y PASS: industry_pe_ttm_q_5y availability。证据：non_null=3668724, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-industry_pe_ttm_q_10y PASS: industry_pe_ttm_q_10y availability。证据：non_null=3668724, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-industry_pe_ttm_q_blended PASS: industry_pe_ttm_q_blended availability。证据：non_null=3668724, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-cycle_peak_trap PASS: cycle_peak_trap availability。证据：non_null=3674369, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-FIN-roe_pct_in_last_12_quarters PASS: roe_pct_in_last_12_quarters availability。证据：non_null=3674199, announcement_violations=0, fallback_violations=0, fallback_days=30
- LH-VAL-001 PASS: valuation quantile rolling windows。证据：samples=20, failures=0
- LH-VAL-SOURCE-001 WARN: combined_v2 resolver valuation source fields。证据：candidate_rows=1638, failures=0, warnings=2
- LH-TECH-001 PASS: technical indicators use current-or-prior bars。证据：checked=ma20,ma60,ma120,ma200,ma250,ma20_slope_10d,ma60_slope_20d,ma120_slope_20d,atr20,close; missing=; max_source_date_used=signal_date
- LH-UNI-001 PASS: combined_v2 historical universe point-in-time。证据：monthly_files=38, future_data_files=0

## 估值分位抽样证据

- 2025-12-02 002622.sz stock_pb_q_blended: window_end=2025-12-02, max_source_date_used=2025-12-02, PASS
- 2025-08-05 601866.sh stock_pb_q_blended: window_end=2025-08-05, max_source_date_used=2025-08-05, PASS
- 2023-04-11 002571.sz stock_pb_q_blended: window_end=2023-04-11, max_source_date_used=2023-04-11, PASS
- 2024-07-19 300446.sz stock_pb_q_blended: window_end=2024-07-19, max_source_date_used=2024-07-19, PASS
- 2024-10-25 605009.sh stock_pb_q_blended: window_end=2024-10-25, max_source_date_used=2024-10-25, PASS
- 2025-02-05 688466.sh stock_pe_ttm_q_blended: window_end=2025-02-05, max_source_date_used=2025-02-05, PASS
- 2023-09-05 002062.sz stock_pe_ttm_q_blended: window_end=2023-09-05, max_source_date_used=2023-09-05, PASS
- 2024-09-11 002611.sz stock_pe_ttm_q_blended: window_end=2024-09-11, max_source_date_used=2024-09-11, PASS
- 2025-01-10 600503.sh stock_pe_ttm_q_blended: window_end=2025-01-10, max_source_date_used=2025-01-10, PASS
- 2026-01-13 688508.sh stock_pe_ttm_q_blended: window_end=2026-01-13, max_source_date_used=2026-01-13, PASS
- 2023-04-24 002965.sz industry_pb_q_blended: window_end=2023-04-24, max_source_date_used=2023-04-24, PASS
- 2023-09-26 000635.sz industry_pb_q_blended: window_end=2023-09-26, max_source_date_used=2023-09-26, PASS
- 2024-10-10 601798.sh industry_pb_q_blended: window_end=2024-10-10, max_source_date_used=2024-10-10, PASS
- 2025-06-13 002437.sz industry_pb_q_blended: window_end=2025-06-13, max_source_date_used=2025-06-13, PASS
- 2024-08-07 688185.sh industry_pb_q_blended: window_end=2024-08-07, max_source_date_used=2024-08-07, PASS
- 2023-04-24 002965.sz industry_pe_ttm_q_blended: window_end=2023-04-24, max_source_date_used=2023-04-24, PASS
- 2023-09-26 000635.sz industry_pe_ttm_q_blended: window_end=2023-09-26, max_source_date_used=2023-09-26, PASS
- 2024-10-10 601798.sh industry_pe_ttm_q_blended: window_end=2024-10-10, max_source_date_used=2024-10-10, PASS
- 2025-06-13 002437.sz industry_pe_ttm_q_blended: window_end=2025-06-13, max_source_date_used=2025-06-13, PASS
- 2024-08-07 688185.sh industry_pe_ttm_q_blended: window_end=2024-08-07, max_source_date_used=2024-08-07, PASS

## resolver 字段解析证据

- 2023-04-03 600018.sh defensive_dividend: stock=stock_pe_ttm_q_blended(pe_ttm), industry=industry_pe_ttm_q_blended(pe_ttm), max_source_date_used=2023-04-03, PASS
- 2023-04-03 601866.sh defensive_dividend: stock=stock_pe_ttm_q_blended(pe_ttm), industry=industry_pe_ttm_q_blended(pe_ttm), max_source_date_used=2023-04-03, PASS
- 2023-04-03 601919.sh defensive_dividend: stock=stock_pe_ttm_q_blended(pe_ttm), industry=industry_pe_ttm_q_blended(pe_ttm), max_source_date_used=2023-04-03, PASS
- 2023-04-03 600153.sh defensive_dividend: stock=stock_pe_ttm_q_blended(pe_ttm), industry=industry_pe_ttm_q_blended(pe_ttm), max_source_date_used=2023-04-03, PASS
- 2023-04-03 600377.sh defensive_dividend: stock=stock_pe_ttm_q_blended(pe_ttm), industry=industry_pe_ttm_q_blended(pe_ttm), max_source_date_used=2023-04-03, PASS
- 2023-04-03 601298.sh defensive_dividend: stock=stock_pe_ttm_q_blended(pe_ttm), industry=industry_pe_ttm_q_blended(pe_ttm), max_source_date_used=2023-04-03, PASS
- 2023-04-03 002120.sz cyclical_rotation: stock=stock_pb_q_blended(pb), industry=industry_pb_q_blended(pb), max_source_date_used=2023-04-03, PASS
- 2023-04-03 601018.sh cyclical_rotation: stock=stock_pb_q_blended(pb), industry=industry_pb_q_blended(pb), max_source_date_used=2023-04-03, PASS
- 2023-04-03 002352.sz cyclical_rotation: stock=stock_pb_q_blended(pb), industry=industry_pb_q_blended(pb), max_source_date_used=2023-04-03, PASS
- 2023-04-03 601006.sh defensive_dividend: stock=stock_pe_ttm_q_blended(pe_ttm), industry=industry_pe_ttm_q_blended(pe_ttm), max_source_date_used=2023-04-03, PASS
- 2023-04-03 001965.sz defensive_dividend: stock=stock_pe_ttm_q_blended(pe_ttm), industry=industry_pe_ttm_q_blended(pe_ttm), max_source_date_used=2023-04-03, PASS
- 2023-04-03 600025.sh defensive_dividend: stock=stock_pe_ttm_q_blended(pe_ttm), industry=industry_pe_ttm_q_blended(pe_ttm), max_source_date_used=2023-04-03, PASS
- 2023-04-03 601985.sh defensive_dividend: stock=stock_pe_ttm_q_blended(pe_ttm), industry=industry_pe_ttm_q_blended(pe_ttm), max_source_date_used=2023-04-03, PASS
- 2023-04-03 600900.sh defensive_dividend: stock=stock_pe_ttm_q_blended(pe_ttm), industry=industry_pe_ttm_q_blended(pe_ttm), max_source_date_used=2023-04-03, PASS
- 2023-04-03 600236.sh defensive_dividend: stock=stock_pe_ttm_q_blended(pe_ttm), industry=industry_pe_ttm_q_blended(pe_ttm), max_source_date_used=2023-04-03, PASS
- 2023-04-03 600674.sh defensive_dividend: stock=stock_pe_ttm_q_blended(pe_ttm), industry=industry_pe_ttm_q_blended(pe_ttm), max_source_date_used=2023-04-03, PASS
- 2023-04-03 603260.sh cyclical_rotation: stock=stock_pb_q_blended(pb), industry=industry_pb_q_blended(pb), max_source_date_used=2023-04-03, PASS
- 2023-04-03 002064.sz cyclical_rotation: stock=stock_pb_q_blended(pb), industry=industry_pb_q_blended(pb), max_source_date_used=2023-04-03, PASS
- 2023-04-03 601216.sh cyclical_rotation: stock=stock_pb_q_blended(pb), industry=industry_pb_q_blended(pb), max_source_date_used=2023-04-03, PASS
- 2023-04-03 000651.sz defensive_dividend: stock=stock_pe_ttm_q_blended(pe_ttm), industry=industry_pe_ttm_q_blended(pe_ttm), max_source_date_used=2023-04-03, PASS
