# stale report check

- overall_status: FAIL
- scanned_files: 20
- fail_count: 5
- warn_count: 0

## checks

- PASS | GLOBAL | old_rating_residue_absent | 未发现未隔离的旧 WARN 或旧评级句子。
- PASS | GLOBAL | old_attribution_residue_absent | 未发现旧 signal/regime attribution 行。
- PASS | GLOBAL | release_sync_stale_residue_absent | 未发现 release sync 提交前状态残留。
- FAIL | reports/observation/2026-05-04/observation_blocked.md | observation_gate_allowed_no_current_blocked，matched=observation_blocked.md current | freshness 允许观察时，不得保留未标记 legacy 的 STALE_DATA_BLOCKED 主报告。
- FAIL | reports/observation/2026-05-04/observation_blocked.md | observation_gate_allowed_no_stale_blocked_content，matched=action_allowed: false | freshness 允许观察时，当前主路径不得残留旧 blocked 内容；历史文件必须第一行标记 LEGACY_SUPERSEDED。
- FAIL | reports/observation/2026-05-04/observation_summary.md | observation_gate_allowed_summary_exists，matched=summary missing | freshness 允许观察时必须生成 observation_summary.md。
- FAIL | reports/observation/2026-05-04/observation_run_manifest.json | observation_gate_allowed_manifest，matched=False | manifest 必须以本次允许观察结果为准。
- PASS | reports/backtest/attribution/combined_v2_attribution_report.md | required_section:entry signal attribution，matched=entry signal attribution | combined_v2_attribution_report.md 必须保留新版归因章节。
- PASS | reports/backtest/attribution/combined_v2_attribution_report.md | required_section:exit signal attribution，matched=exit signal attribution | combined_v2_attribution_report.md 必须保留新版归因章节。
- PASS | reports/backtest/attribution/combined_v2_attribution_report.md | required_section:entry-exit pair attribution，matched=entry-exit pair attribution | combined_v2_attribution_report.md 必须保留新版归因章节。
- PASS | reports/backtest/attribution/combined_v2_attribution_report.md | required_section:trade realization regime attribution，matched=trade realization regime attribution | combined_v2_attribution_report.md 必须保留新版归因章节。
- PASS | reports/backtest/attribution/combined_v2_attribution_report.md | required_section:daily MTM regime attribution，matched=daily MTM regime attribution | combined_v2_attribution_report.md 必须保留新版归因章节。
- FAIL | reports/backtest/audit/combined_v2_rc_summary.md | rc_summary_rating_guard，matched=最终评级: PASS_CANDIDATE | 存在 freshness FAIL 时，RC 总结不得仍显示 PASS_CANDIDATE。
