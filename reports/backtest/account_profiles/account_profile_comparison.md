# 账户 profile 回测对比

- status: WARN
- default_release_profile: actual_50k_lot_aware
- release_account_profile: retail_50k_lot_aware
- lot_aware_adopted_as_default: true
- adoption_reason: actual_50k_lot_aware 满足本轮全部切默认条件。
- manual_review_required: true
- auto_trading_approved: false
- broker_integration_enabled: false
- llm_decision_allowed: false
- not production ready

## 对比表

| profile | initial | min_trade | max_pos | eq_target | lot_aware | raw | unique | repeat_blocked | feasible | executable | exec/raw | exec/feasible | visible_buy | visible_blocked | pending | MIN_TRADE ratio | LOT_SIZE count/ratio | PRICE_TOO_HIGH count | annual | cumulative | max_dd | Sharpe | turnover | cost_pct | max_pos_seen | status | adopted |
|---|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|---:|---:|---:|---:|---:|---:|---:|---:|---|---|
| reference_200k_current | 200000.0 | 5000.0 | 20 | 36 | False | 370 | 370 | 0 | 116 | 43 | 0.11621621621621622 | 0.3706896551724138 | 43 | 327 | 0 | 0.5945945945945946 | 4/0.010810810810810811 | 0 | 0.07135202476872582 | 0.21964440453100043 | -0.09364547429916759 | 0.7782204340639889 | 2.7762431675 | 0.0028855954689998554 | 20 | WARN | False |
| actual_50k_unmodified | 50000.0 | 5000.0 | 20 | 36 | False | 1300 | 1300 | 0 | 0 | 0 | 0.0 | None | 0 | 1300 | 0 | 0.3976923076923077 | 783/0.6023076923076923 | 0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0 | WARN | False |
| actual_50k_retail | 50000.0 | 1500.0 | 12 | 12 | False | 1145 | 1145 | 0 | 12 | 12 | 0.010480349344978166 | 1.0 | 12 | 1133 | 0 | 0.3056768558951965 | 783/0.6838427947598253 | 0 | 0.01957303760622886 | 0.05743295907599988 | -0.04275365621662608 | 0.4851807879652739 | 0.8027113799999999 | 0.0008270409239999513 | 6 | WARN | False |
| actual_50k_lot_aware | 50000.0 | 1500.0 | 8 | 8 | True | 629 | 159 | 470 | 426 | 23 | 0.03656597774244833 | 0.0539906103286385 | 23 | 136 | 47 | 0.0 | 0/0.0 | 30 | 0.024846220411411934 | 0.07326562069200016 | -0.08876605706976393 | 0.35634328938471815 | 2.04219921 | 0.0020743793079998824 | 8 | WARN | True |

## adoption failures

- none

## 人话说明

- 50000 元账户继续使用 5000 元最小交易额时，单笔门槛约等于本金 10%，大量 raw buy 会在资金颗粒度上被阻断。
- retail_50k 把最小交易额降到 1500 元后，MIN_TRADE_AMOUNT 阻断占比较 5000 元原参数下降 0.09201545179711118；这是用同一 raw buy 口径比较，不是重定义 raw buy。
- lot-aware sizing 会把 NEW_BUY 提升到至少一手，同时仍受现金、单票上限和每日开仓数约束；ADD 不足一手时进入 pending，不进入可执行买入。
- 8 或 12 只最大持仓是组合执行层约束，目标是让 50000 元资金的单票交易额更符合整手颗粒度；universe target 仍是 36，只代表候选股票池目标。
- actual_50k_retail executable/raw=0.010480349344978166，是否解除账户约束 WARN 仍按 25% 门槛判断。
- 当前输出只用于人工观察和研究复核，不是实盘批准，也不包含自动下单或券商接口。
