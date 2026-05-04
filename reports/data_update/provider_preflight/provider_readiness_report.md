# provider readiness report

- overall_status: WARN
- as_of_date: 2026-05-04
- target_trading_date: 2026-04-30
- local_tdx_available: false
- network_providers_available: true
- provider_health_date: 2026-04-03
- provider_health_stale: true
- data_quality_date: 2026-04-03
- data_quality_stale: true

## checks

- NOT_APPLICABLE | TDX-001 | tdx | tdx local dirs configured | actual=none | 未配置本地 TDX 路径。
- PASS | IMPORT-akshare | akshare | akshare import | actual=True | 缺少 provider 依赖时相关数据源不可用。
- PASS | IMPORT-pytdx | pytdx | pytdx import | actual=True | 缺少 provider 依赖时相关数据源不可用。
- PASS | IMPORT-py_mini_racer | py_mini_racer | py_mini_racer import | actual=True | 缺少 provider 依赖时相关数据源不可用。
- PASS | IMPORT-efinance | efinance | efinance import | actual=True | 缺少 provider 依赖时相关数据源不可用。
- PASS | IMPORT-baostock | baostock | baostock import | actual=True | 缺少 provider 依赖时相关数据源不可用。
- PASS | IMPORT-adata | adata | adata import | actual=True | 缺少 provider 依赖时相关数据源不可用。
- WARN | TOKEN-tushare | tushare | TUSHARE_TOKEN present | actual=False | 报告只记录 token_present，不输出 token 原文。
- WARN | TOKEN-jqdata_username | jqdata_username | JQDATA_USERNAME present | actual=False | 报告只记录 token_present，不输出 token 原文。
- WARN | TOKEN-jqdata_password | jqdata_password | JQDATA_PASSWORD present | actual=False | 报告只记录 token_present，不输出 token 原文。
- PASS | HEALTH-001 | provider_health | provider_health exists | actual=True | 缺少 provider health 时不能确认上一轮 provider 状态。
- WARN | HEALTH-002 | provider_health | provider_health date | actual=2026-04-03 | provider health 过期时需要先做 provider 验证。
- PASS | HEALTH-003 | provider_health | provider failures | actual=0 | 存在失败 provider 时需审阅失败原因。
- PASS | QUALITY-001 | data_quality | data_quality exists | actual=True | 缺少 data quality 时需要重新生成。
- WARN | QUALITY-002 | data_quality | data_quality date | actual=2026-04-03 | data quality 过期时不能直接信任当前覆盖。
- PASS | WRITE-001 | filesystem | output directory writable | actual=True | 输出目录不可写时禁止非 dry-run 更新。
- PASS | WRITE-002 | filesystem | output directory writable | actual=True | 输出目录不可写时禁止非 dry-run 更新。
- PASS | WRITE-003 | filesystem | output directory writable | actual=True | 输出目录不可写时禁止非 dry-run 更新。
- PASS | WRITE-004 | filesystem | output directory writable | actual=True | 输出目录不可写时禁止非 dry-run 更新。
- PASS | WRITE-005 | filesystem | output directory writable | actual=True | 输出目录不可写时禁止非 dry-run 更新。
- PASS | WRITE-006 | filesystem | output directory writable | actual=True | 输出目录不可写时禁止非 dry-run 更新。
- PASS | WRITE-007 | filesystem | output directory writable | actual=True | 输出目录不可写时禁止非 dry-run 更新。
- PASS | SOURCE-001 | source | at least one usable source | actual=True | 没有可用数据源时禁止非 dry-run 更新。
