# 手工观察协议

## 运行模式

观察期由 `config/observation.yml` 定义：

- primary_profile: `combined_v2`
- conservative_profile: `combined_v2_1_risk_guard`
- mode: `paper_observation_only`
- allow_broker_connection: `false`
- allow_auto_order: `false`
- allow_llm_decision: `false`
- generate_real_orders: `false`

这个配置只定义观察运行方式，不改变策略交易规则。

## 每日入口

```bash
./.venv/bin/python scripts/run_observation_pipeline.py \
  --as-of-date 2026-05-04 \
  --profile combined_v2 \
  --mode paper \
  --compare-conservative true
```

运行顺序：

1. 验证 combined_v2 RC。
2. 检查旧报告残留。
3. 检查数据新鲜度。
4. 只有全部通过时，才生成观察摘要、动作候选、阻断原因和手工动作清单。
5. 数据过期时只输出 blocked / historical review 报告，不输出手工订单清单。

## 纸面账户

首次运行会创建：

- `data/observation/paper_account.yml`
- `data/observation/paper_trades.csv`
- `data/observation/paper_positions.yml`

这三个文件是真实本地纸面账本，属于持续变化的本地产物，已被 `.gitignore` 忽略，不提交。仓库只提交 `fixtures/observation/` 下的 example 模板；首次运行时脚本会从 example 初始化本地文件。

更新纸面账本：

```bash
./.venv/bin/python scripts/update_paper_observation.py --as-of-date 2026-05-04
```

纸面账本只允许三种来源：

- `paper_next_bar_simulated`
- `manual_user_entered`
- `correction`

人工复核状态只允许：

- `pending`
- `approved`
- `rejected`
- `executed_paper`
- `corrected`

## 人工边界

观察报告和手工清单只是人工参考。任何真实交易都必须由人判断、人执行；仓库不连接券商，不自动下单，不生成真实委托。

`combined_v2_1_risk_guard` 会并行输出作保守观察对照，但不得自动替换 `combined_v2`。
