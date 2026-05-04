# 观察期数据质量检查

- status: WARN
- requested_as_of_date: 2026-05-04
- target_trading_date: 2026-04-30
- total_a_share_count: 5201
- active_a_share_count: 5201
- feature_rows_on_target_date: 5151
- unique_stocks_on_target_date: 5151
- benchmark_row_exists_on_target_trading_date: True
- effective_universe_file: data/curated/universe_history/2026-04-06.json
- provider_health_date: 2026-04-30

## checks

- PASS | STOCK-001 | total_a_share_count | actual=5201 | 缺少股票列表时不能生成观察报告。
- PASS | STOCK-002 | active_a_share_count | actual=5201 | 缺少活跃 A 股范围时不能生成观察报告。
- PASS | FEATURE-001 | feature_rows_on_target_date | actual=5151 | 目标交易日必须有特征行。
- PASS | FEATURE-002 | unique_stocks_on_target_date | actual=5151 | 目标交易日必须覆盖可交易股票。
- PASS | CORE-close | close completeness | actual=0.0 | 核心字段缺失超过规则时阻断或降级观察。
- PASS | CORE-ma20 | ma20 completeness | actual=0.0 | 核心字段缺失超过规则时阻断或降级观察。
- PASS | CORE-ma60 | ma60 completeness | actual=0.0 | 核心字段缺失超过规则时阻断或降级观察。
- PASS | CORE-ma120 | ma120 completeness | actual=0.0 | 核心字段缺失超过规则时阻断或降级观察。
- PASS | CORE-ma200 | ma200 completeness | actual=0.0 | 核心字段缺失超过规则时阻断或降级观察。
- PASS | CORE-ma250 | ma250 completeness | actual=0.0 | 核心字段缺失超过规则时阻断或降级观察。
- PASS | CORE-atr20 | atr20 completeness | actual=0.0 | 核心字段缺失超过规则时阻断或降级观察。
- PASS | CORE-pb | pb completeness | actual=0.002524 | 核心字段缺失超过规则时阻断或降级观察。
- WARN | CORE-pe_ttm | pe_ttm completeness | actual=0.27451 | 核心字段缺失超过规则时阻断或降级观察。
- PASS | CORE-roe | roe completeness | actual=0.007571 | 核心字段缺失超过规则时阻断或降级观察。
- PASS | CORE-cfo_ttm | cfo_ttm completeness | actual=0.011454 | 核心字段缺失超过规则时阻断或降级观察。
- PASS | CORE-net_profit_ttm | net_profit_ttm completeness | actual=0.001941 | 核心字段缺失超过规则时阻断或降级观察。
- PASS | CORE-dividend_yield_ttm | dividend_yield_ttm completeness | actual=0.0 | 核心字段缺失超过规则时阻断或降级观察。
- PASS | BENCH-001 | benchmark row exists on target_trading_date | actual=True | 目标交易日必须有 benchmark 行。
- PASS | BENCH-002 | benchmark ma60 available | actual=True | benchmark ma60 缺失时 market regime 不可靠。
- PASS | BENCH-003 | benchmark ma200 available | actual=True | benchmark ma200 缺失时 market regime 不可靠。
- PASS | VAL-001 | stock valuation source fields exist | actual=True | 估值 resolver 需要 stock source fields。
- PASS | VAL-002 | industry valuation source fields exist | actual=True | 估值 resolver 需要 industry source fields。
- PASS | UNIVERSE-001 | effective universe available for target_trading_date | actual=data/curated/universe_history/2026-04-06.json | 目标交易日必须能找到有效股票池。
- PASS | PROVIDER-001 | latest provider health date | actual=2026-04-30 | provider health 缺失时降级为 WARN 并显式记录。
- PASS | PROVIDER-002 | provider failures | actual=0 | 存在 provider 失败时继续人工审阅数据质量。
