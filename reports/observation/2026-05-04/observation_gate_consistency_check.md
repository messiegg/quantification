# observation gate consistency check

- overall_status: FAIL
- as_of_date: 2026-05-04
- fail_count: 4
- warn_count: 0

## checks

- FAIL | GATE-001A | blocked report absent or legacy when allowed | actual=current | freshness 已允许观察时，旧 blocked 报告不能作为当前主报告存在。
- FAIL | GATE-001B | no stale blocked content when allowed | actual=action_allowed: false | 允许观察时，当前主路径下不得保留旧 STALE_DATA_BLOCKED 内容。
- PASS | GATE-001C | tracked old blocked report absent unless legacy | actual=tracked=False, legacy=False | Git 跟踪的旧 blocked report 必须删除，除非第一行标记 LEGACY_SUPERSEDED。
- FAIL | GATE-002 | summary exists when freshness allowed | actual=False | 允许观察时必须生成 observation_summary.md。
- FAIL | GATE-003 | manifest action_allowed true | actual=False | manifest 必须反映本次观察已允许。
- PASS | CAL-001 | holiday calendar staleness is warn only | actual=NONE | 非交易日且目标交易日数据已覆盖时，calendar staleness 不得阻断。
- PASS | CAL-002 | holiday calendar staleness warning present | actual=True | calendar-day 超阈值应作为非交易日自然间隔提示。
