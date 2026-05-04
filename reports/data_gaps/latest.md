# Data Gaps (2026-05-04)

- Target trading date: 2026-04-30
- HS A-share symbols in master list: 5201

## Table Status

- stock_list: ready | latest=2026-04-30 | rows=5201 | ready_unique=5201 | master symbol table
- price_daily: missing | latest=2026-04-30 | rows=7417498 | ready_unique=5067 | requires >=250 rows and latest trade date
- st_flags: missing | latest=2026-04-30 | rows=10814 | ready_unique=0 |
- market_caps: missing | latest=2026-04-30 | rows=5424 | ready_unique=0 |
- valuation_pb: missing | latest=2026-04-30 | rows=1239 | ready_unique=0 | requires latest date and >=5y history
- valuation_pe_ttm: missing | latest=2026-04-30 | rows=1239 | ready_unique=0 | requires latest date and >=5y history
- financials: missing | latest=2025-12-31 | rows=147475 | ready_unique=1230 | latest report with roe/net_profit/cfo/debt_to_assets
- benchmark_daily: ready | latest=2026-04-30 | rows=2751 | ready_unique=2 | invalid_rows=0
- industry_daily: missing | latest=2026-01-30 | rows=14490 | ready_unique=337 | required for industry quantiles
- industry_members: missing | latest=2026-04-04 | rows=15684 | ready_unique=0 | required for latest industry mapping

## Missing Symbol Files

- price: /Users/meseg/shu/stocks/quantile/data/curated/missing_data/price_missing.txt (134)
- st_flags: /Users/meseg/shu/stocks/quantile/data/curated/missing_data/st_flags_missing.txt (5201)
- market_caps: /Users/meseg/shu/stocks/quantile/data/curated/missing_data/market_caps_missing.txt (5201)
- valuation_pb: /Users/meseg/shu/stocks/quantile/data/curated/missing_data/valuation_pb_missing.txt (5201)
- valuation_pe_ttm: /Users/meseg/shu/stocks/quantile/data/curated/missing_data/valuation_pe_ttm_missing.txt (5201)
- financials: /Users/meseg/shu/stocks/quantile/data/curated/missing_data/financials_missing.txt (3971)
- industry_members: /Users/meseg/shu/stocks/quantile/data/curated/missing_data/industry_members_missing.txt (5201)
- core_symbol_data: /Users/meseg/shu/stocks/quantile/data/curated/missing_data/core_symbol_data_missing.txt (5201)

## Blocking Tables

- industry_daily: latest=2026-01-30 < target_trading_date=2026-04-30
- industry_members: latest=2026-04-04, current_ready_symbols=0/5201
