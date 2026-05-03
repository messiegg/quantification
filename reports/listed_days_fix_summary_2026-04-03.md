# Listed Days Fix Summary (2026-04-03)

## 修复前

- trade calendar date range:
  - formal table: `absent`
  - effective calendar used by `listed_days`: `data/raw/benchmark_daily.parquet`
  - date range: `2021-01-04` -> `2026-04-03`
- max possible listed_days as of 2026-04-03: `1271`
- candidate_pool_size: `0`
- effective_universe_size: `0`
- candidate industries impacted by old cap:
  - total symbols in candidate industries: `1347`
  - `listed_days < 1500`: `1347`
  - `listed_days >= 1500`: `0`

## 修复后

- new trade calendar source: `data/raw/price_daily.parquet` unique trading dates
- new trade calendar output: `data/curated/trade_calendar.parquet`
- new trade calendar date range: `2018-01-02` -> `2026-04-03`
- new trade calendar size: `2001` trading dates
- cleaned anomalous weekend dates: `0`
- listed_days calculation:
  - primary path: `stock_list.listed_date + trade_calendar`
  - fallback path: `symbol earliest price date + trade_calendar`
  - strict 2026-04-03 actual source usage in candidate industries:
    - `listed_date_trade_calendar`: `1347`
    - `first_price_trade_calendar`: `0`
- new max possible listed_days as of 2026-04-03: `2001`
- candidate industries after fix:
  - total symbols in candidate industries: `1347`
  - `listed_days < 1500`: `309`
  - `listed_days >= 1500`: `1038`
- candidate_pool_size: `0`
- effective_universe_size: `0`

## 运行结果

- step 1 `update_market_data`: `success`
  - verified outputs:
    - `data/raw/price_daily.parquet`
    - `data/raw/benchmark_daily.parquet`
    - `data/raw/stock_list.parquet`
    - `data/curated/trade_calendar.parquet`
- step 2 `build_features`: `success`
  - verified outputs:
    - `data/features/daily_features/2026.parquet`
    - `data/features/latest_feature_snapshot.parquet`
    - `data/curated/financials_effective.parquet`
    - `data/curated/stock_quantiles.parquet`
    - `data/curated/industry_quantiles.parquet`
- step 3 `refresh_universe --apply`: `success`
  - verified outputs:
    - `reports/universe/latest.json`
    - `reports/universe/latest.md`
    - `config/universe.yml`
  - result:
    - `candidate_pool_size = 0`
    - `effective_universe_size = 0`
- step 4 `prepare_snapshot`: `failed`
  - error: `Strict snapshot failed because safe_mode would be triggered on 2026-04-03`
- step 5 `render_report`: `not executed because strict chain stopped at snapshot failure`

## 剩余 Blockers

Remaining blocker counts below are unique symbol counts inside current candidate industries, using the repaired `listed_days` logic.

- `avg_amount_60d_million`: `1282`
- `roe`: `846`
- `main_metric_history`: `713`
- `dv_ttm`: `646`
- `market_cap_billion`: `594`
- `industry_leader`: `492`
- `pe_ttm`: `343`
- `core_fields_missing`: `319`
- `listed_days`: `309`
- `latest_net_profit`: `227`
- `debt_to_assets`: `132`
- `cfo_ttm`: `111`
- `pb_q_blended`: `72`
- `st`: `29`
- `cycle_trap`: `24`
- `pb`: `11`

## 结论

- 是否确认“历史窗口不足”就是主因: `yes`
  - before fix, old benchmark-capped calendar guaranteed all `1347` candidate-industry symbols failed `listed_days`
- 是否已经解除这一主因: `yes`
  - after fix, `listed_days` max rose from `1271` to `2001`
  - `1038` candidate-industry symbols now satisfy `listed_days >= 1500`
- strict run 是否成功: `no`
  - old `listed_days` cap is no longer the blocking reason for the whole run
  - the current strict failure is now the downstream empty universe / snapshot `safe_mode` failure caused by remaining liquidity, quality, history, and bucket-level blockers
