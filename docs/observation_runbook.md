# combined_v2 observation / paper trading runbook

本 runbook 只用于规则输出的人工观察和纸面交易记录。它不批准实盘，不接券商，不自动下单，也不允许 LLM 改写 `action_enum`、目标仓位或目标金额。

## 每日盘前检查

盘前只确认系统状态是否允许进入人工观察，不做策略调参。

1. 确认数据更新任务成功完成，并记录失败、降级或缺失的数据源。
2. 检查最新 observation / evidence 输出中的 `data_stale` 是否为 `false`。
3. 检查 `core_fields_complete` 是否为 `true`；若核心字段不完整，暂停当日买卖观察。
4. 检查 universe 数量：
   - 低于 `floor_size` 时暂停 observation。
   - 低于 `target_size` 但高于 floor 时保留 WARN，并记录缺口原因。
5. 检查 `reports/backtest/release/release_guard_report.csv`：
   - `fail_count` 必须为 0。
   - 当前允许 `WARN`，不得为了好看改成 PASS。
6. 检查 `reports/backtest/release/combined_v2_rc_verify.csv`：
   - 不得有 FAIL。
   - `CODE` / `CFG` / config key output drift 不得存在。
7. 运行 `scripts/check_observation_readiness.py`：
   - `READY_FOR_OBSERVATION` 只表示可以进入人工 observation / paper trading。
   - `NOT_READY` 时暂停，并记录脚本输出的原因。

## 每日盘后检查

盘后只复核规则输出是否合理、完整、可解释，不把解释变成交易裁决。

1. 确认当日 signals / orders / evidence 是否按预期生成；若 gate 阻断，只保留阻断报告。
2. 统计 `BLOCKED` 原因，并与前几日对比。
3. 重点检查以下原因是否激增：
   - `MAX_POSITIONS_LIMIT`
   - `CASH_INSUFFICIENT_FOR_ONE_LOT`
   - `PRICE_TOO_HIGH_FOR_ACCOUNT_LOT`
4. 检查买入建议是否异常集中在单一行业；若集中，需要记录行业暴露风险，但不得手工改写规则输出。
5. 检查是否出现：
   - `fundamental_break`
   - `trend_stop`
   - `hard_add_ban`
6. 对每个 NEW_BUY、ADD、REDUCE、EXIT 记录人工复核结果、纸面成交状态、未成交原因和价格来源。

## 人工复核标准

1. 任何 `NEW_BUY`、`ADD`、`REDUCE`、`EXIT` 都必须人工确认。
2. 纸面成交价格必须记录来源，例如收盘价、次日开盘价、可验证行情截图或本地行情缓存路径。
3. 未成交必须记录原因，例如一手金额过高、现金不足、价格偏离、停牌、涨跌停、人工否决。
4. 不允许因为 LLM 的解释而改变 `action_enum`。
5. LLM 只能解释规则输出、整理检查清单、辅助发现异常；不能决定买卖方向、仓位、金额或是否执行。
6. 如人工复核与规则输出不一致，记录为人工 override / observation note，不回写策略逻辑。

## 观察期暂停和退出条件

任一条件触发时，暂停 observation / paper trading，直到重新生成并验证相关报告。

1. 连续 observation days 不足，不得进入实盘或 PASS_CANDIDATE。
2. 数据更新失败、`data_stale=true`、核心字段不完整或 universe 低于 floor。
3. 出现 code/config hash drift。
4. `release_guard` 出现 FAIL。
5. `combined_v2_rc_verify` 出现 FAIL。
6. executable/raw 长期低于 25%，不得升级为 PASS。
7. 实际滑点、纸面不可成交比例或价格可得性与回测假设明显偏离。
8. 发现真实账户成交、券商 API、自动下单或 LLM 买卖裁决痕迹。

## 记录模板

每日记录使用 `reports/observation/templates/daily_observation_template.md`。真实人工复核日志和纸面成交记录不得提交真实账户敏感信息；需要提交时只能提交脱敏样例或模板。
