# observation gate consistency check

- overall_status: PASS
- as_of_date: 2026-05-04
- fail_count: 0
- warn_count: 0

## checks

- PASS | GATE-001 | allowed freshness has no current blocked report | actual=absent_or_legacy | freshness 已允许观察时，旧 blocked 报告不能作为当前主报告存在。
- PASS | GATE-002 | summary exists when freshness allowed | actual=True | 允许观察时必须生成 observation_summary.md。
- PASS | GATE-003 | manifest action_allowed true | actual=True | manifest 必须反映本次观察已允许。
- PASS | MARKET-001 | holiday summary marks market closed | actual=present | 非交易日观察报告必须显式标记市场关闭。
- PASS | MARKET-002 | holiday summary has no execution wording | actual=none | 非交易日报告只能作为下一交易日人工复核。
- PASS | MANUAL-001 | manual list marks next trading day review | actual=True | 非交易日手工清单必须限定为下一交易日人工复核。
- PASS | MANUAL-002 | manual list disables auto order | actual=True | 手工清单必须明确禁止自动下单。
- PASS | MANUAL-003 | manual list requires human review | actual=True | 手工清单必须要求人工复核。
- PASS | QUALITY-001 | summary includes data quality WARN | actual=True | 数据质量 WARN 允许观察，但必须在 summary 中展示。
- PASS | CAL-001 | holiday calendar staleness is warn only | actual=NONE | 非交易日且目标交易日数据已覆盖时，calendar staleness 不得阻断。
- PASS | CAL-002 | holiday calendar staleness warning present | actual=True | calendar-day 超阈值应作为非交易日自然间隔提示。
