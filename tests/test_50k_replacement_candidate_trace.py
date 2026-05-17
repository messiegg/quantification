from __future__ import annotations

from scripts import generate_50k_core_traces as traces
from tests.test_50k_core_trace_generation import make_trace_bundle


def test_replacement_candidate_trace_is_diagnostic_only_and_score_gap_is_correct() -> None:
    bundle = make_trace_bundle()
    replacement = bundle.replacement_candidate_trace

    assert replacement["diagnostic_only"].all()
    assert not bundle.signal_execution_trace.columns.str.contains("diagnostic_future_return").any()
    row = replacement.iloc[0]
    assert row["score_gap"] == row["candidate_score"] - row["weakest_holding_score"]
    assert row["reason_not_triggered"] in traces.REPLACEMENT_REASON_ENUM | {""}


def test_triggered_replacement_pair_exists_in_trade_ledger() -> None:
    bundle = make_trace_bundle()
    replacement = bundle.replacement_candidate_trace
    trades = bundle.trade_ledger
    triggered = replacement[replacement["replacement_triggered"]]

    for pair_id in triggered["replacement_pair_id"]:
        pair = trades[trades["replacement_pair_id"] == pair_id]
        assert pair["is_replacement_sell"].any()
        assert pair["is_replacement_buy"].any()
