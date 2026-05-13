# 50k compact neighborhood robustness

- status: FRAGILE
- research_only: true
- default_release_profile_unchanged: true
- auto_trading_approved: false
- broker_integration_enabled: false
- llm_decision_allowed: false

## best_candidate

- variant: mp6_tr1_tu8_cr15_add0
- annual_return: 7.31%
- cumulative_return: 22.55%
- max_drawdown: -10.62%
- max_exposure: 79.62%
- total_trades: 20
- executable_buy_count: 12
- strategy_eligible_count: 240
- account_actionable_buy_count: 12
- watch_only_count: 228
- executable_account_actionable_ratio: 100.00%

## robustness_judgement

- judgement: FRAGILE
- supporting_neighborhood_count_excluding_best: 1
- neighborhood_candidate_count: 8
- rule: at least 3 neighboring variants excluding the best must satisfy return, drawdown, exposure, execution and trade-count thresholds.

## neighborhood and controls

| group | variant | annual | annual_delta | cumulative_delta | max_dd | max_dd_delta | max_exposure | exposure_delta | trades | trades_delta | watch | watch_delta | exec/actionable | pass |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---:|---|
| negative_max_adds_1 | mp6_tr1_tu10_cr15_add1 | 7.31% | 0.00% | 0.00% | -10.62% | 0.00% | 79.62% | 0.00% | 20 | 0 | 228 | 0 | 100.00% | true |
| negative_max_adds_1 | mp6_tr1_tu8_cr15_add1 | 7.31% | 0.00% | 0.00% | -10.62% | 0.00% | 79.62% | 0.00% | 20 | 0 | 228 | 0 | 100.00% | true |
| negative_max_adds_1 | mp5_tr1_tu10_cr20_add1 | 4.34% | -2.97% | -9.53% | -11.10% | -0.49% | 76.24% | -3.38% | 23 | 3 | 216 | -12 | 100.00% | false |
| negative_max_adds_1 | mp5_tr1_tu8_cr20_add1 | 4.34% | -2.97% | -9.53% | -11.10% | -0.49% | 76.24% | -3.38% | 23 | 3 | 216 | -12 | 100.00% | false |
| negative_max_adds_1 | mp5_tr1_tu10_cr15_add1 | 4.32% | -2.99% | -9.58% | -12.19% | -1.58% | 84.47% | 4.84% | 23 | 3 | 90 | -138 | 100.00% | false |
| negative_max_adds_1 | mp5_tr1_tu8_cr15_add1 | 4.32% | -2.99% | -9.58% | -12.19% | -1.58% | 84.47% | 4.84% | 23 | 3 | 90 | -138 | 100.00% | false |
| negative_max_adds_1 | mp6_tr1_tu10_cr20_add1 | 2.99% | -4.32% | -13.69% | -10.96% | -0.34% | 80.66% | 1.04% | 29 | 9 | 269 | 41 | 28.57% | false |
| negative_max_adds_1 | mp6_tr1_tu8_cr20_add1 | 2.99% | -4.32% | -13.69% | -10.96% | -0.34% | 80.66% | 1.04% | 29 | 9 | 269 | 41 | 28.57% | false |
| negative_max_positions_8 | mp8_tr1_tu10_cr15_add0 | 8.60% | 1.29% | 4.30% | -11.07% | -0.46% | 84.86% | 5.24% | 30 | 10 | 222 | -6 | 100.00% | true |
| negative_max_positions_8 | mp8_tr1_tu8_cr15_add0 | 8.60% | 1.29% | 4.30% | -11.07% | -0.46% | 84.86% | 5.24% | 30 | 10 | 222 | -6 | 100.00% | true |
| negative_max_positions_8 | mp8_tr1_tu10_cr20_add0 | 4.48% | -2.83% | -9.08% | -10.63% | -0.01% | 73.59% | -6.03% | 28 | 8 | 326 | 98 | 100.00% | false |
| negative_max_positions_8 | mp8_tr1_tu8_cr20_add0 | 4.48% | -2.83% | -9.08% | -10.63% | -0.01% | 73.59% | -6.03% | 28 | 8 | 326 | 98 | 100.00% | false |
| negative_max_tranches_2 | mp5_tr2_tu10_cr20_add0 | 1.41% | -5.90% | -18.42% | -7.35% | 3.26% | 43.34% | -36.29% | 28 | 8 | 624 | 396 | 100.00% | false |
| negative_max_tranches_2 | mp5_tr2_tu8_cr20_add0 | 1.41% | -5.90% | -18.42% | -7.35% | 3.26% | 43.34% | -36.29% | 28 | 8 | 624 | 396 | 100.00% | false |
| negative_max_tranches_2 | mp6_tr2_tu10_cr20_add0 | 1.41% | -5.90% | -18.43% | -6.64% | 3.98% | 45.82% | -33.80% | 31 | 11 | 656 | 428 | 100.00% | false |
| negative_max_tranches_2 | mp6_tr2_tu8_cr20_add0 | 1.41% | -5.90% | -18.43% | -6.64% | 3.98% | 45.82% | -33.80% | 31 | 11 | 656 | 428 | 100.00% | false |
| negative_max_tranches_2 | mp5_tr2_tu10_cr15_add0 | 1.40% | -5.92% | -18.47% | -7.66% | 2.95% | 45.18% | -34.44% | 28 | 8 | 617 | 389 | 100.00% | false |
| negative_max_tranches_2 | mp5_tr2_tu8_cr15_add0 | 1.40% | -5.92% | -18.47% | -7.66% | 2.95% | 45.18% | -34.44% | 28 | 8 | 617 | 389 | 100.00% | false |
| negative_max_tranches_2 | mp6_tr2_tu10_cr15_add0 | 1.39% | -5.92% | -18.50% | -6.75% | 3.87% | 46.61% | -33.02% | 31 | 11 | 644 | 416 | 100.00% | false |
| negative_max_tranches_2 | mp6_tr2_tu8_cr15_add0 | 1.39% | -5.92% | -18.50% | -6.75% | 3.87% | 46.61% | -33.02% | 31 | 11 | 644 | 416 | 100.00% | false |
| neighborhood | mp6_tr1_tu10_cr15_add0 | 7.31% | 0.00% | 0.00% | -10.62% | 0.00% | 79.62% | 0.00% | 20 | 0 | 228 | 0 | 100.00% | true |
| neighborhood | mp6_tr1_tu8_cr15_add0 | 7.31% | 0.00% | 0.00% | -10.62% | 0.00% | 79.62% | 0.00% | 20 | 0 | 228 | 0 | 100.00% | true |
| neighborhood | mp5_tr1_tu10_cr20_add0 | 4.34% | -2.97% | -9.53% | -11.10% | -0.49% | 76.24% | -3.38% | 23 | 3 | 216 | -12 | 100.00% | false |
| neighborhood | mp5_tr1_tu8_cr20_add0 | 4.34% | -2.97% | -9.53% | -11.10% | -0.49% | 76.24% | -3.38% | 23 | 3 | 216 | -12 | 100.00% | false |
| neighborhood | mp5_tr1_tu10_cr15_add0 | 4.32% | -2.99% | -9.58% | -12.19% | -1.58% | 84.47% | 4.84% | 23 | 3 | 90 | -138 | 100.00% | false |
| neighborhood | mp5_tr1_tu8_cr15_add0 | 4.32% | -2.99% | -9.58% | -12.19% | -1.58% | 84.47% | 4.84% | 23 | 3 | 90 | -138 | 100.00% | false |
| neighborhood | mp6_tr1_tu10_cr20_add0 | 2.99% | -4.32% | -13.69% | -10.96% | -0.34% | 80.66% | 1.04% | 29 | 9 | 269 | 41 | 28.57% | false |
| neighborhood | mp6_tr1_tu8_cr20_add0 | 2.99% | -4.32% | -13.69% | -10.96% | -0.34% | 80.66% | 1.04% | 29 | 9 | 269 | 41 | 28.57% | false |

## note

- This report reads existing compact_experiment_metrics.csv only.
- It does not run a new search, expand the parameter space, change release guard, or change the default release profile.
