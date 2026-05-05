# forbidden tracked files check

- overall_status: PASS
- tracked_files: 538
- allowlisted_exceptions: 4
- fail_count: 0

## checks

- PASS | ALLOW-001 | forbidden pattern allowed by release allowlist | actual=.env.example | evidence=allowlisted small fixture/report, size=135 | 可提交的空值环境变量模板，不包含真实 token、密码或账户信息。
- PASS | ALLOW-002 | forbidden pattern allowed by release allowlist | actual=data/demo_case/benchmark_daily.parquet | evidence=allowlisted small fixture/report, size=2223 | 小型 demo fixture，用于离线测试固定 demo，不是行情主数据。
- PASS | ALLOW-003 | forbidden pattern allowed by release allowlist | actual=data/demo_case/daily_features.parquet | evidence=allowlisted small fixture/report, size=33280 | 小型 demo fixture，用于离线测试固定 demo，不是 data/features 主特征目录。
- PASS | ALLOW-004 | forbidden pattern allowed by release allowlist | actual=data/demo_case/financials_effective.parquet | evidence=allowlisted small fixture/report, size=3880 | 小型 demo fixture，用于离线测试固定 demo，不是完整财务数据。
- PASS | FORBID-000 | no forbidden tracked files | actual=0 | evidence=git ls-files | 未发现未豁免的大体量数据、真实账本、订单文件或 secret 文件。
- PASS | SECRET-000 | no token-like secrets in tracked text files | actual=0 | evidence=tracked text scan | 未发现 token/password/secret/api key 原文。
