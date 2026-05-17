from __future__ import annotations

from scripts import run_50k_core_deployment_repair as deployment


def test_deployment_repair_trace_selection_is_capped_at_four() -> None:
    rows = [
        {"variant": "repair_best_baseline", "stock_only": True, "pass_hard_conditions": False, "selection_score": 0.1},
        {"variant": "stock_best", "stock_only": True, "pass_hard_conditions": True, "selection_score": 0.9},
        {"variant": "cash_best", "stock_only": False, "cash_sleeve_data_available": True, "selection_score": 0.8},
        {"variant": "closest", "stock_only": True, "pass_hard_conditions": False, "selection_score": 0.7},
        {"variant": "extra", "stock_only": True, "pass_hard_conditions": False, "selection_score": 0.6},
    ]

    selected = deployment.select_trace_variants(rows)

    assert len(selected) <= 4
    assert "repair_best_baseline" in selected
    assert "stock_best" in selected
    assert "cash_best" in selected


def test_trace_diagnostic_text_answers_required_questions() -> None:
    text = deployment.build_deployment_trace_diagnostic_report(
        {
            "quality_defensive_fill_candidates": 5,
            "quality_defensive_fill_executed": 2,
            "winner_add_executed": 1,
            "financial_group_cap_blocks": 3,
            "market_regime_review_fills": 4,
            "cash_sleeve_data_available": False,
            "overtrading_flags": ["QUALITY_FILL_OVERTRADING_OR_LOW_EDGE"],
        }
    )

    for phrase in [
        "quality_defensive_fill",
        "winner_add",
        "financial_group_cap",
        "market_regime_review",
        "cash sleeve",
        "过度交易",
    ]:
        assert phrase in text
