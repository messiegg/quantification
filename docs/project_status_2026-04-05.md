# 项目现状说明（2026-04-05）

> 历史快照：本文记录的是 2026-04-05 strict 数据链路恢复阶段的状态，已经不是当前仓库状态。当前状态请看 `docs/project_status_2026-05-05.md`、`README.md` 的 CI / 发布保护章节，以及 `reports/observation/2026-05-04/` 下的 observation 报告。

## 1. 仓库目标

本项目是一个本地可追溯的 A 股研究/选股流水线，不接入自动交易或券商执行。

主链路如下：

1. 原始数据更新  
   `scripts/update_market_data.py`
2. 事件/行业历史回填  
   `scripts/backfill_share_change.py`  
   `scripts/backfill_industry_history.py`
3. 本地派生面板重建  
   `scripts/derive_daily_panels.py`
4. 因子与特征构建  
   `scripts/build_features.py`
5. effective universe 生成  
   `scripts/refresh_universe.py --apply`
6. snapshot / report / orders  
   `scripts/prepare_snapshot.py`  
   `scripts/render_report.py`

## 2. 本次 GitHub 上传范围

本次上传的是：

- 当前代码改动
- 新增的 strict 数据脚本与 helper
- 新增/更新的小体量诊断与状态文件
- 本文档

本次**不会**上传的大文件：

- `data/raw/**/*.parquet`
- `data/curated/**/*.parquet`
- `data/features/**/*.parquet`
- `data/snapshots/**/*.json`
- 本地虚拟环境、cache、日志

这些大文件已由 `.gitignore` 排除，GitHub 上不会包含本地大数据本体。

## 2.1 本次快速验证

本次提交前已执行：

```bash
./.venv/bin/pytest tests/test_data_adapters.py tests/test_storage.py tests/test_data_gaps.py -q
```

结果：

- `20 passed`
- `1` 条第三方依赖 `py_mini_racer` 的 `DeprecationWarning`

说明：

- 本次做了针对改动面的快速验证
- 没有执行全量测试矩阵

## 3. 当前代码层面的主要变化

### 3.1 strict 数据链路相关

已存在并可运行的 strict 相关文件包括：

- `scripts/backfill_share_change.py`
- `scripts/backfill_industry_history.py`
- `scripts/derive_daily_panels.py`
- `src/pipeline/strict_data.py`

### 3.2 数据源与派生逻辑

当前代码已经具备以下能力：

- 使用本地 strict helper 统一处理 strict run 日期与派生面板
- 新增 `share_change` 原始表回填
- 新增 SW 行业历史回填与 `industry_members_effective` 生成
- 从本地 `price_daily + share_change + financials` 重建：
  - `shares_daily`
  - `market_cap_daily`
  - `stock_valuation_daily`
  - `industry_daily`
- `build_features / refresh_universe / prepare_snapshot / render_report` 已接到新的 strict 数据面板

### 3.3 本次实际补过的 strict 细节

为完成 `2026-04-03` strict run，本次对 strict 数据更新路径补了几处关键修正：

- `update_market_data.py`
  - strict 模式下不再把 symbol 范围缩回旧的 partial 数据子集
  - strict `stock_list` 在 `pytdx` 失败时，fallback 到正式 adapter 的 `get_stock_list(as_of_date)`，不再直接复用旧 parquet
  - strict `stock_list` 会直接写回 `2026-04-03` 的当日版本
  - strict `price_daily` 支持判断 AkShare TX 结果是否真正覆盖到 `as_of_date`
  - AkShare TX 若只返回到更早日期，会回退到 BaoStock
  - BaoStock fallback 在 strict 里做了串行化，避免并发解码/解压异常
  - strict `financials` 支持检测现有 raw 覆盖并直接复用
- `src/pipeline/strict_data.py`
  - 新增 AkShare TX 价格抓取 helper
  - 保留 strict 数据派生 helper
  - 子进程执行器统一改为 `spawn`

## 4. 2026-04-03 strict run 执行结果

### 4.1 已完成的步骤

以下步骤已完成并核实产物落盘：

1. `python scripts/update_market_data.py --as-of-date 2026-04-03`
2. `python scripts/backfill_share_change.py --as-of-date 2026-04-03`
3. `python scripts/backfill_industry_history.py --as-of-date 2026-04-03`
4. `python scripts/derive_daily_panels.py --as-of-date 2026-04-03`
5. `python scripts/build_features.py --as-of-date 2026-04-03`
6. `python scripts/refresh_universe.py --as-of-date 2026-04-03 --apply`

### 4.2 失败步骤

第 7 步失败：

```bash
python scripts/prepare_snapshot.py --as-of-date 2026-04-03
```

失败信息：

```text
Strict snapshot failed because safe_mode would be triggered on 2026-04-03.
```

因此第 8 步 `render_report.py` 没有继续执行。

## 5. 当前数据覆盖状态

以下统计均对应本地当前文件状态。

### 5.1 原始层

- `data/raw/stock_list.parquet`
  - `5194` symbols
  - `as_of_date = 2026-04-03`
- `data/raw/price_daily.parquet`
  - `5194` symbols
  - `2026-04-03` 当日覆盖 `5194` symbols
- `data/raw/financials.parquet`
  - `5194` symbols
  - `report_date` 覆盖到 `2025-12-31`
- `data/raw/st_flags.parquet`
  - `2026-04-03` 当日覆盖 `5194` symbols
- `data/raw/share_change.parquet`
  - `5194` symbols
- `data/raw/industry_hist_sw.parquet`
  - `5194` symbols

### 5.2 派生层

- `data/curated/shares_daily.parquet`
  - `2026-04-03` 覆盖 `5194` symbols
- `data/curated/market_cap_daily.parquet`
  - `2026-04-03` 覆盖 `5194` symbols
- `data/curated/stock_valuation_daily.parquet`
  - `2026-04-03` 覆盖 `5194` symbols
- `data/curated/industry_members_effective.parquet`
  - `2026-04-03` 覆盖 `5194` symbols
- `data/curated/industry_daily.parquet`
  - `2026-04-03` 覆盖 `31` 个行业

### 5.3 features / universe

- `data/features/daily_features/2026.parquet`
  - `2026-04-03` 覆盖 `5194` symbols
- `data/features/latest_feature_snapshot.parquet`
  - 最新快照行为 `5194`
- `reports/universe/latest.json`
  - `candidate_pool_size = 0`
  - `effective_universe_size = 0`
- `config/universe.yml`
  - 当前写回结果为空 universe

## 6. 当前严格 blocker

### 6.1 直接 blocker

strict run 当前不是卡在数据缺表，而是卡在 **candidate pool 为 0**。

具体表现：

- `refresh_universe.py --apply` 成功执行，但结果为：
  - `candidate_pool_size = 0`
  - `effective_universe_size = 0`
- `prepare_snapshot.py` 因会触发 `safe_mode` 而直接失败

### 6.2 根因

当前最关键的 blocker 是：

- `listed_days_insufficient`

原因不是上市日期缺失，而是 `listed_days` 计算使用的交易历史窗口不够长。

当前 strict 价格/benchmark 历史窗口从 `2021-01-04` 开始，到 `2026-04-03` 结束，最多只有 `1271` 个交易日左右；而当前 universe 规则中的基础过滤要求：

```yaml
listed_days_min: 1500
```

这意味着：

- 即使股票真实上市很久
- 只要 `listed_days` 由当前可用交易日窗口计算
- 它的值就不可能超过约 `1271`

所以当前允许行业里的股票会被批量卡在这条规则上。

### 6.3 已统计的 blocker 数量

在当前允许行业范围内，主要 blocker 统计如下：

- `listed_days`: `1347`
- `avg_amount_60d_million`: `1282`
- `roe`: `846`
- `main_metric_history`: `713`
- `dv_ttm`: `646`
- `market_cap_billion`: `594`
- `industry_leader`: `492`
- `core_fields_missing`: `319`
- `latest_net_profit`: `227`
- `debt_to_assets`: `132`
- `cfo_ttm`: `111`
- `pb_q_blended`: `72`
- `st`: `29`
- `cycle_trap`: `24`
- `pb`: `11`

此外：

- 总 feature symbols: `5194`
- 落在当前 `metric_map` 允许行业中的 symbols: `1347`
- 不在当前候选行业范围中的 symbols: `3847`

这 `3847` 只不属于本次 strict 数据层 blocker，而是现有策略/行业范围本身不纳入候选池。

## 7. 为什么不是“数据层全坏”

当前状态需要区分两件事：

### 7.1 已经修到位的部分

- strict 原始行情已经补满到 `2026-04-03`
- strict 财报覆盖已经补满到当前股票范围
- share change / industry history 已补满
- 本地估值与行业估值派生面板已重建
- features 已成功构建到 `2026-04-03`

### 7.2 还没过的部分

- 不是“没有数据”
- 而是“现有历史窗口长度不够支撑现有 universe 规则”
- 因此 `candidate_pool = 0`
- 因此 strict snapshot 被系统判定会进入 `safe_mode`

## 8. 当前仓库中值得注意的文件

### 8.1 关键代码

- `scripts/update_market_data.py`
- `scripts/backfill_share_change.py`
- `scripts/backfill_industry_history.py`
- `scripts/derive_daily_panels.py`
- `scripts/build_features.py`
- `scripts/refresh_universe.py`
- `scripts/prepare_snapshot.py`
- `src/pipeline/strict_data.py`
- `src/pipeline/features.py`
- `src/adapters/akshare_adapter.py`
- `src/adapters/adata_adapter.py`
- `src/adapters/factory.py`

### 8.2 当前状态产物

- `provider_health/latest.json`
- `data_quality/latest.json`
- `reports/universe/latest.json`
- `reports/universe/latest.md`
- `data/curated/missing_data/*.txt`
- `reports/data_gaps/latest.json`
- `reports/data_gaps/latest.md`

## 9. 下一步建议

如果继续沿 strict 路线推进，优先级应是：

1. 解决 `listed_days` 被历史窗口截断的问题  
   这不是改阈值，而是补长 strict 价格/benchmark 历史窗口。
2. 重新构建 features
3. 重跑 `refresh_universe.py --apply`
4. 再跑 `prepare_snapshot.py`
5. 只有 snapshot strict 成功后，才继续 `render_report.py`

## 10. 当前结论

当前项目状态可以概括为：

- 数据层 strict 修复已经基本完成
- `2026-04-03` 的 raw / curated / features 已能本地生成
- strict run 最终失败在 snapshot 前一层
- 当前失败主因是 universe 入口条件未满足，而不是 share_change / industry / valuation 数据缺失
- 在不改策略规则的前提下，下一步应补长历史窗口，而不是继续加 safe mode、partial coverage 或近似替代
