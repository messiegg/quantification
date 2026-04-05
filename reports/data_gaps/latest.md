# Data Gaps (2026-04-04)

- Target trading date: 2026-04-03
- HS A-share symbols in master list: 5194

## Table Status

- stock_list: ready | latest=2026-04-04 | rows=5497 | ready_unique=5194 | master symbol table
- price_daily: missing | latest=2026-04-03 | rows=96754 | ready_unique=202 | requires >=250 rows and latest trade date
- st_flags: missing | latest=2026-04-04 | rows=423 | ready_unique=400 |
- market_caps: missing | latest=2026-04-04 | rows=223 | ready_unique=200 |
- valuation_pb: missing | latest=2026-04-03 | rows=1239 | ready_unique=0 | requires latest date and >=5y history
- valuation_pe_ttm: missing | latest=2026-04-03 | rows=1239 | ready_unique=0 | requires latest date and >=5y history
- financials: missing | latest=2025-12-31 | rows=3766 | ready_unique=61 | latest report with roe/net_profit/cfo/debt_to_assets
- benchmark_daily: missing | latest=2026-04-03 | rows=82 | ready_unique=1 | invalid_rows=2
- industry_daily: missing | latest=2026-01-30 | rows=14490 | ready_unique=337 | required for industry quantiles
- industry_members: missing | latest=2026-04-04 | rows=15684 | ready_unique=205 | required for latest industry mapping

## Missing Symbol Files

- price: /Users/meseg/shu/stocks/quantile/data/curated/missing_data/price_missing.txt (4992)
- st_flags: /Users/meseg/shu/stocks/quantile/data/curated/missing_data/st_flags_missing.txt (4794)
- market_caps: /Users/meseg/shu/stocks/quantile/data/curated/missing_data/market_caps_missing.txt (4994)
- valuation_pb: /Users/meseg/shu/stocks/quantile/data/curated/missing_data/valuation_pb_missing.txt (5194)
- valuation_pe_ttm: /Users/meseg/shu/stocks/quantile/data/curated/missing_data/valuation_pe_ttm_missing.txt (5194)
- financials: /Users/meseg/shu/stocks/quantile/data/curated/missing_data/financials_missing.txt (5133)
- industry_members: /Users/meseg/shu/stocks/quantile/data/curated/missing_data/industry_members_missing.txt (4989)
- core_symbol_data: /Users/meseg/shu/stocks/quantile/data/curated/missing_data/core_symbol_data_missing.txt (5194)

## Blocking Tables

- benchmark_daily: latest_valid=2026-04-03, invalid_rows=2
- industry_daily: latest=2026-01-30 < target_trading_date=2026-04-03
- industry_members: latest=2026-04-04, current_ready_symbols=205/5194
