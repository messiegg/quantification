# CI 与本地验证说明

本仓库的验证分三层。GitHub Actions 默认只跑轻量检查和报告 guard；完整数据和完整回测只在本地数据环境运行。

## Layer 1：CI 轻量检查

GitHub Actions 每次 push 和 PR 都运行：

```bash
python -m pip install -r requirements.txt
python -m pytest -q -m "not data_required and not full_backtest"
```

这一层必须覆盖：

- 单元测试；
- path sanitization；
- observation gate consistency；
- stale report 检查；
- release sync consistency；
- provider readiness 不输出 token；
- safe update 不带 `--execute` 不写数据；
- paper ledger ignored。

带 `data_required` 或 `full_backtest` marker 的测试不会在这一层运行。

## Layer 2：CI report guard

GitHub Actions 运行：

```bash
python scripts/run_release_guard.py --ci --as-of-date 2026-05-04
```

这一层只使用仓库内已提交的小型报告、manifest、hash 和 Git 跟踪状态。它不会重新跑完整回测，不依赖本地完整特征数据，不生成真实订单，不写行情数据。

内部检查包括：

- `scripts/check_report_freshness.py`
- `scripts/check_release_sync_consistency.py`
- `scripts/check_report_path_sanitization.py`
- `scripts/check_observation_gate_consistency.py --as-of-date 2026-05-04`
- `scripts/verify_combined_v2_rc.py --mode hash-only`
- `scripts/check_forbidden_tracked_files.py`

## Layer 3：本地 full-data 验证

完整数据环境才运行：

```bash
./.venv/bin/python scripts/verify_combined_v2_rc.py --mode full
./.venv/bin/python scripts/check_data_freshness.py --as-of-date 2026-05-04 --write-report
./.venv/bin/python scripts/check_data_quality_for_observation.py --as-of-date 2026-05-04 --write-report
./.venv/bin/python scripts/run_observation_pipeline.py --as-of-date 2026-05-04 --profile combined_v2 --mode paper --compare-conservative true
./.venv/bin/python -m pytest -q
```

这一层允许读取本地完整数据并重新验证 `combined_v2 next_bar`，但仍禁止接券商、自动下单、生成真实订单。

## 本地 pre-commit 风格检查

不强制安装 Git hook。提交前建议手动运行：

```bash
./.venv/bin/python scripts/run_release_guard.py --ci --as-of-date 2026-05-04 --write-report
./.venv/bin/python scripts/check_forbidden_tracked_files.py --write-report
./.venv/bin/python scripts/verify_combined_v2_rc.py --mode hash-only
./.venv/bin/python -m pytest -q -m "not data_required and not full_backtest"
```

如果修改涉及本地完整数据或回测，再运行 Layer 3。

## observation SOP

交易日：

- 若 data、feature、benchmark 覆盖到目标交易日，允许生成 observation report。
- data quality 为 PASS 或 WARN 时可进入观察；WARN 必须写入报告并要求人工复核。
- manual order list 只是本地人工复核产物，不能提交，不能自动执行。

非交易日：

- `as_of_date` 映射到最近目标交易日。
- 如果目标交易日数据已覆盖，calendar staleness 只作为 WARN。
- observation summary 必须标记市场关闭，并说明仅用于下一交易日人工复核。

数据 stale：

- `allowed_actions` 必须为 historical review 或等价阻断状态。
- 不得保留当前 observation summary。
- 不得生成 manual order list。

provider WARN：

- 报告必须说明 provider readiness 或数据质量 WARN。
- 可以继续观察，但不能把 WARN 写成实盘执行许可。
- token 只允许写是否存在，不允许输出原文。
