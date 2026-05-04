# data update CLI audit

- overall_status: WARN
- fail_count: 0
- warn_count: 1

## checks

- PASS | scripts/update_market_data.py | as_of=True | start/end=True/True | CLI 可用于 preflight 计划。
- WARN | scripts/build_features.py | as_of=True | start/end=False/False | build_features.py 只支持单日 --as-of-date；safe update 将采用单日构建。
- PASS | scripts/check_data_freshness.py | as_of=True | start/end=False/False | CLI 可用于 preflight 计划。
- PASS | scripts/check_data_quality_for_observation.py | as_of=True | start/end=False/False | CLI 可用于 preflight 计划。
- PASS | scripts/update_market_data_safe.py | as_of=True | start/end=False/False | CLI 可用于 preflight 计划。
