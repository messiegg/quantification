# data update preflight summary

- as_of_date: 2026-05-04
- target_trading_date: 2026-04-30
- can_attempt_non_dry_run: false
- blocking_layers: PROVIDER_READINESS_WARN
- next_safe_command: `./.venv/bin/python scripts/run_data_update_preflight.py --as-of-date 2026-05-04 --write-report`
- next_safe_command_note: 当前只建议继续修复并重跑 preflight；该命令不写行情数据、不生成订单。

## statuses

- stale_report_check: PASS
- verify_combined_v2_rc: PASS
- release_sync_consistency: PASS
- data_freshness_allowed_actions: historical_review_only
- data_update_cli_audit: WARN
- provider_readiness: WARN
- safe_update_preflight: WARN

## safe update preflight

- will_write_data: false
- wrote_data: false
- skipped_reason: PREFLIGHT_ONLY

## commands_planned

- `./.venv/bin/python scripts/update_market_data.py --as-of-date 2026-04-30 --all-stocks`
- `./.venv/bin/python scripts/build_features.py --as-of-date 2026-04-30`

## 用户需要补充或确认

- 如需离线更新，配置可读的本地 TDX vipdoc 路径。
- 如需 Tushare，设置 TUSHARE_TOKEN 环境变量或 .env 条目。
- 如需 JQData，设置 JQDATA_USERNAME / JQDATA_PASSWORD。
