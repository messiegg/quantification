from __future__ import annotations

from tests.test_50k_core_trace_generation import make_trace_bundle


def test_trade_ledger_round_lot_cash_and_unique_trade_id() -> None:
    trades = make_trace_bundle().trade_ledger

    assert trades["trade_id"].is_unique
    assert ((trades["shares"] % trades["round_lot"]) == 0).all()
    buys = trades[trades["side"].astype(str).str.contains("BUY")]
    for row in buys.to_dict(orient="records"):
        assert abs(row["cash_before"] - row["trade_value"] - row["total_cost"] - row["cash_after"]) < 1e-9


def test_replacement_pair_has_sell_and_buy_and_trade_links_to_trace() -> None:
    bundle = make_trace_bundle()
    trades = bundle.trade_ledger
    signal_symbols = set(zip(bundle.signal_execution_trace["date"], bundle.signal_execution_trace["symbol"]))
    exit_symbols = set(zip(bundle.exit_rule_trace["date"], bundle.exit_rule_trace["symbol"]))

    pair = trades[trades["replacement_pair_id"] == "R000001"]
    assert pair["is_replacement_buy"].any()
    assert pair["is_replacement_sell"].any()
    assert (trades["execution_status"] == "EXECUTED").all()
    assert (("2025-01-01", "600000.sh") in signal_symbols) or (("2025-01-01", "600000.sh") in exit_symbols)
