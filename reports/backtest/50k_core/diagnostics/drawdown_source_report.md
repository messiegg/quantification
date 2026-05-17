# drawdown source report

|   drawdown_id | start_date   | trough_date   | recovery_date   |   max_drawdown | regime_at_start   | regime_at_trough   |   exposure_at_start |   exposure_at_trough |   cash_ratio_at_start |   cash_ratio_at_trough | top_loss_symbols   | top_loss_industries   | bucket_loss_breakdown   | exit_signals_triggered   |   replacement_signals_triggered | missed_exit_candidates      |
|--------------:|:-------------|:--------------|:----------------|---------------:|:------------------|:-------------------|--------------------:|---------------------:|----------------------:|-----------------------:|:-------------------|:----------------------|:------------------------|:-------------------------|--------------------------------:|:----------------------------|
|             1 | 2025-03-17   | 2025-03-25    | 2025-03-31      |      -0.160391 | risk_on           | risk_on            |            0.511709 |             0.418431 |              0.488291 |               0.581569 | {}                 |                       |                         | missing_trade_detail     |                               0 | requires_daily_position_pnl |

## Attribution available

- top_loss_symbols_global: {}
- industry_pnl_global: {'公用事业': 4051.4364099999975, '家用电器': 3139.699140800001, '银行': 6352.712636800002, '非银金融': 1930.1035}
- bucket_pnl_global: {'defensive_dividend': 15473.951687599998}

缺失字段警告：stage1 没有逐日持仓 PnL 和逐笔 exit signal 明细，因此 drawdown 期间股票/bucket 贡献只能用全局 attribution 辅助判断，不能伪造成逐日归因。
