# stale report check

- overall_status: PASS
- scanned_files: 13
- fail_count: 0
- warn_count: 0

## checks

- PASS | GLOBAL | old_rating_residue_absent | 未发现未隔离的旧 WARN 或旧评级句子。
- PASS | GLOBAL | old_attribution_residue_absent | 未发现旧 signal/regime attribution 行。
- PASS | reports/backtest/attribution/combined_v2_attribution_report.md | required_section:entry signal attribution，matched=entry signal attribution | combined_v2_attribution_report.md 必须保留新版归因章节。
- PASS | reports/backtest/attribution/combined_v2_attribution_report.md | required_section:exit signal attribution，matched=exit signal attribution | combined_v2_attribution_report.md 必须保留新版归因章节。
- PASS | reports/backtest/attribution/combined_v2_attribution_report.md | required_section:entry-exit pair attribution，matched=entry-exit pair attribution | combined_v2_attribution_report.md 必须保留新版归因章节。
- PASS | reports/backtest/attribution/combined_v2_attribution_report.md | required_section:trade realization regime attribution，matched=trade realization regime attribution | combined_v2_attribution_report.md 必须保留新版归因章节。
- PASS | reports/backtest/attribution/combined_v2_attribution_report.md | required_section:daily MTM regime attribution，matched=daily MTM regime attribution | combined_v2_attribution_report.md 必须保留新版归因章节。
