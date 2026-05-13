from __future__ import annotations

import copy
from collections import Counter

from src.execution.models import AccountExecutionPolicy, BUY_INTENTS, ExecutionReason, ExecutionStatus, StrategyIntent
from src.execution.pending import build_pending_add_hint, merge_pending_add_value
from src.execution.sizer import LEGACY_REASON_MAP, size_add, size_new_buy


STRATEGY_BLOCK_REASONS = {
    "NOT_IN_EFFECTIVE_UNIVERSE",
    "DATA_STALE_BLOCK",
    "REGIME_OPEN_BLOCK",
    "HARD_ADD_BAN",
    "CYCLE_TRAP",
    "REGIME_CAP_BLOCK",
    "MARKET_REGIME_BLOCK",
}


def _safe_float(value: object, default: float = 0.0) -> float:
    try:
        if value is None:
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_int(value: object, default: int = 0) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError):
        return default


def _priority_score(decision: dict) -> float:
    for field in ("priority_score", "universe_final_score", "final_score"):
        if field in decision and decision.get(field) is not None:
            return _safe_float(decision.get(field))
    return 0.0


def _stock_valuation_quantile(decision: dict) -> float:
    for field in ("stock_valuation_quantile", "stock_q_blended", "stock_pb_q_blended", "stock_pe_ttm_q_blended"):
        if field in decision and decision.get(field) is not None:
            return _safe_float(decision.get(field), 100.0)
    return 100.0


def _execution_action_type(decision: dict) -> str:
    intent = str(decision.get("strategy_intent", decision.get("action_enum", "")))
    current_tranches = _safe_int(decision.get("current_position_tranches"))
    current_shares = _safe_int(decision.get("current_shares"))
    if intent in BUY_INTENTS:
        return "NEW_BUY" if current_tranches <= 0 and current_shares <= 0 else "ADD"
    if intent == StrategyIntent.SELL_ALL:
        return "SELL"
    if intent == StrategyIntent.REDUCE:
        return "REDUCE"
    return "NONE"


def _rank_key(decision: dict, policy: AccountExecutionPolicy) -> tuple:
    action_type = str(decision.get("execution_action_type") or _execution_action_type(decision))
    held_priority = 0 if action_type == "ADD" else 1
    price = _safe_float(decision.get("close", decision.get("target_price_reference")))
    lot_notional = price * policy.round_lot if price > 0 and policy.round_lot > 0 else 0.0
    lot_budget = policy.account_equity * (1.0 - policy.cash_reserve_ratio) / max(policy.max_positions, 1)
    lot_fit = 0 if lot_notional <= lot_budget + 1e-9 else 1
    dividend = _safe_float(decision.get("dv_ttm")) if str(decision.get("bucket")) == "defensive_dividend" else 0.0
    return (
        held_priority,
        lot_fit,
        -_priority_score(decision),
        _stock_valuation_quantile(decision),
        -dividend,
        str(decision.get("industry", "")),
        str(decision.get("symbol", "")),
    )


def _infer_strategy_intent(decision: dict) -> str:
    original = str(decision.get("action_enum", StrategyIntent.EMPTY))
    blocked_reason = str(decision.get("blocked_reason") or "")
    if original == StrategyIntent.BLOCKED and blocked_reason not in STRATEGY_BLOCK_REASONS:
        intended = str(decision.get("intended_action_enum") or "")
        signal = str(decision.get("signal_level") or "")
        if intended in BUY_INTENTS:
            return intended
        if signal in BUY_INTENTS:
            return signal
    if original in {
        StrategyIntent.BUY_1,
        StrategyIntent.BUY_2,
        StrategyIntent.BUY_3,
        StrategyIntent.REDUCE,
        StrategyIntent.SELL_ALL,
        StrategyIntent.HOLD,
        StrategyIntent.HOLD_FROZEN,
        StrategyIntent.HOLD_WITH_PENDING_ADD,
        StrategyIntent.EMPTY,
        StrategyIntent.DATA_ERROR,
        StrategyIntent.BLOCKED,
    }:
        return original
    intended = str(decision.get("intended_action_enum") or "")
    return intended if intended else StrategyIntent.DATA_ERROR


def _reset_to_current(decision: dict, reason: str | None = None) -> None:
    current_tranches = _safe_int(decision.get("current_position_tranches"))
    current_weight = _safe_float(decision.get("current_weight"))
    current_shares = _safe_int(decision.get("current_shares"))
    price = _safe_float(decision.get("close", decision.get("target_price_reference")))
    decision["target_position_tranches"] = current_tranches
    decision["target_weight"] = round(current_weight, 6)
    decision["target_position_change"] = 0.0
    decision["target_shares"] = current_shares
    decision["delta_shares"] = 0
    decision["rounded_lots"] = 0
    decision["estimated_turnover"] = 0.0
    decision["estimated_commission"] = 0.0
    decision["estimated_stamp_duty"] = 0.0
    decision["estimated_total_cash_impact"] = 0.0
    decision["target_order_value"] = 0.0
    decision["target_price_reference"] = round(price, 4) if price > 0 else None
    if reason:
        decision["action_reason"] = reason


def _set_execution(decision: dict, status: str, reason: str, *, detail: str = "", hint: str = "") -> None:
    decision["execution_status"] = status
    decision["execution_reason"] = reason
    decision["execution_reason_detail"] = detail
    decision["all_failed_checks"] = [] if status == ExecutionStatus.EXECUTABLE else [reason]
    decision["unblock_hint"] = hint


def _watch(decision: dict, reason: str, detail: str, hint: str) -> None:
    decision["action_enum"] = StrategyIntent.HOLD
    decision["blocked_reason"] = decision.get("blocked_reason") if decision.get("blocked_reason") in STRATEGY_BLOCK_REASONS else ""
    decision["user_visible_action"] = False
    _reset_to_current(decision, detail)
    _set_execution(decision, ExecutionStatus.WATCH, reason, detail=detail, hint=hint)


def _apply_sizer_payload(
    decision: dict,
    payload: dict,
    policy: AccountExecutionPolicy,
    commission_rate: float,
) -> float:
    for field in (
        "lot_notional",
        "minimum_lot_order_value",
        "minimum_lots",
        "max_single_position_value",
        "remaining_single_name_capacity",
        "execution_eligible_for_new_buy",
        "execution_ineligible_reason",
        "pending_add_state",
        "pending_reason",
        "pending_until_condition",
        "execution_status",
        "execution_reason",
        "all_failed_checks",
        "unblock_hint",
    ):
        decision[field] = payload.get(field)
    decision["required_lot_notional"] = payload.get("lot_notional")
    decision["required_cash"] = payload.get("minimum_lot_order_value")
    decision["required_capacity"] = payload.get("lot_notional")

    if payload.get("execution_status") == ExecutionStatus.EXECUTABLE:
        price = _safe_float(decision.get("close", decision.get("target_price_reference")))
        current_shares = _safe_int(decision.get("current_shares"))
        delta_shares = int(payload["executable_shares"])
        target_shares = current_shares + delta_shares
        turnover = round(float(payload["executable_amount"]), 2)
        commission = round(turnover * commission_rate, 2)
        target_weight = round((target_shares * price) / policy.account_equity, 6) if policy.account_equity > 0 else 0.0
        decision["action_enum"] = decision["strategy_intent"]
        decision["user_visible_action"] = True
        decision["blocked_reason"] = ""
        decision["target_position_tranches"] = _safe_int(decision.get("desired_target_tranches", decision.get("target_position_tranches")))
        decision["target_weight"] = target_weight
        decision["target_position_change"] = round(target_weight - _safe_float(decision.get("current_weight")), 6)
        decision["target_shares"] = target_shares
        decision["delta_shares"] = delta_shares
        decision["rounded_lots"] = int(delta_shares // max(policy.round_lot, 1))
        decision["estimated_turnover"] = turnover
        decision["estimated_commission"] = commission
        decision["estimated_stamp_duty"] = 0.0
        decision["estimated_total_cash_impact"] = round(-(turnover + commission), 2)
        decision["target_order_value"] = turnover
        _set_execution(decision, ExecutionStatus.EXECUTABLE, ExecutionReason.EXECUTABLE)
        return turnover + commission

    if payload.get("execution_status") == ExecutionStatus.PENDING:
        reason = str(payload.get("execution_reason"))
        pending_reason = str(payload.get("pending_reason") or LEGACY_REASON_MAP.get(reason, reason))
        decision["action_enum"] = StrategyIntent.HOLD_WITH_PENDING_ADD if decision.get("execution_action_type") == "ADD" else StrategyIntent.HOLD
        decision["blocked_reason"] = ""
        decision["user_visible_action"] = False
        decision["pending_add_state"] = decision.get("execution_action_type") == "ADD"
        decision["pending_reason"] = pending_reason
        current_value = _safe_int(decision.get("current_shares")) * _safe_float(decision.get("close"))
        target_value = _target_position_value(decision, policy)
        intended = max(0.0, target_value - current_value)
        decision["pending_add_value"] = merge_pending_add_value(decision.get("pending_add_value", 0.0), target_value - current_value, intended)
        decision["pending_until_condition"] = payload.get("pending_until_condition")
        decision["unblock_hint"] = payload.get("unblock_hint") or build_pending_add_hint(
            pending_reason=pending_reason,
            required_lot_notional=_safe_float(payload.get("lot_notional")),
            required_cash=_safe_float(payload.get("minimum_lot_order_value")),
            required_capacity=_safe_float(payload.get("remaining_single_name_capacity")),
        )
        _reset_to_current(decision, "Buy intent is pending account execution conditions.")
        _set_execution(
            decision,
            ExecutionStatus.PENDING,
            reason,
            detail="Buy intent is preserved but not executable today.",
            hint=str(decision.get("unblock_hint") or ""),
        )
        return 0.0

    reason = str(payload.get("execution_reason"))
    legacy_reason = str(payload.get("block_reason") or LEGACY_REASON_MAP.get(reason, reason))
    decision["action_enum"] = StrategyIntent.BLOCKED
    decision["blocked_reason"] = legacy_reason
    decision["user_visible_action"] = False
    _reset_to_current(decision, "Buy intent is structurally blocked for this account.")
    _set_execution(
        decision,
        ExecutionStatus.BLOCKED,
        reason,
        detail="Buy intent is structurally ineligible under account constraints.",
        hint=str(payload.get("unblock_hint") or ""),
    )
    decision["execution_ineligible_reason"] = legacy_reason
    return 0.0


def _target_position_value(decision: dict, policy: AccountExecutionPolicy) -> float:
    target_weight = _safe_float(decision.get("desired_target_weight", decision.get("target_weight")))
    if target_weight <= 0 and decision.get("strategy_intent") in BUY_INTENTS:
        target_weight = policy.max_single_stock_weight
    return max(0.0, target_weight * policy.account_equity)


def _replacement_advisory(decision: dict, holdings: list[dict], policy: AccountExecutionPolicy) -> None:
    if not policy.replacement_enabled or not holdings:
        return
    candidates = [item for item in holdings if str(item.get("holding_state")) != "FORCE_EXIT"]
    if not candidates:
        return
    lowest = min(candidates, key=lambda item: (_priority_score(item), str(item.get("symbol", ""))))
    candidate_score = _priority_score(decision)
    holding_score = _priority_score(lowest)
    decision["replacement_candidate_symbol"] = lowest.get("symbol")
    decision["replacement_candidate_score"] = candidate_score
    if candidate_score >= holding_score + policy.replacement_score_threshold:
        decision["replacement_required"] = True
        decision["execution_reason_detail"] = (
            "Candidate score exceeds the lowest holding, but replacement is advisory only and no auto sell is generated."
        )
    else:
        decision["replacement_required"] = False
        decision["unblock_hint"] = "Wait for existing holdings to trigger REDUCE/SELL_ALL or for candidate score to exceed the replacement threshold."


def apply_portfolio_execution_allocator(
    decisions: list[dict],
    account_state: dict | None,
    strategy_cfg: dict | None,
    account_cfg: dict | None,
) -> list[dict]:
    policy = AccountExecutionPolicy.from_configs(account_state, strategy_cfg, account_cfg)
    account_cfg = account_cfg or {}
    execution_cfg = account_cfg.get("execution", {}) if isinstance(account_cfg, dict) else {}
    commission_rate = _safe_float(execution_cfg.get("commission_rate"), 0.0)
    output = copy.deepcopy(decisions)

    for decision in output:
        original = str(decision.get("action_enum", StrategyIntent.EMPTY))
        decision["original_action_enum"] = decision.get("original_action_enum", original)
        decision["strategy_intent"] = decision.get("strategy_intent") or _infer_strategy_intent(decision)
        decision["execution_action_type"] = _execution_action_type(decision)
        decision.setdefault("execution_reason_detail", "")
        decision.setdefault("all_failed_checks", [])
        decision.setdefault("unblock_hint", "")
        decision.setdefault("user_visible_action", bool(original in {StrategyIntent.BUY_1, StrategyIntent.BUY_2, StrategyIntent.BUY_3, StrategyIntent.REDUCE, StrategyIntent.SELL_ALL}))
        decision.setdefault("compact_rank", None)
        decision.setdefault("replacement_candidate_symbol", None)
        decision.setdefault("replacement_candidate_score", None)
        decision.setdefault("replacement_required", False)
        decision.setdefault("target_action_budget", None)
        decision.setdefault("pending_add_value", decision.get("pending_add_value", 0.0))
        decision.setdefault("first_pending_date", decision.get("first_pending_date"))
        decision.setdefault("required_lot_notional", None)
        decision.setdefault("required_cash", None)
        decision.setdefault("required_capacity", None)
        if "reason_codes" not in decision or decision.get("reason_codes") is None:
            decision["reason_codes"] = []
        if "risk_flags" not in decision or decision.get("risk_flags") is None:
            decision["risk_flags"] = []

    candidates: list[dict] = []
    holdings = [
        item
        for item in output
        if _safe_int(item.get("current_shares")) > 0 or _safe_int(item.get("current_position_tranches")) > 0
    ]
    for decision in output:
        intent = str(decision.get("strategy_intent"))
        original = str(decision.get("original_action_enum"))
        blocked_reason = str(decision.get("blocked_reason") or "")
        if intent == StrategyIntent.SELL_ALL:
            decision["action_enum"] = StrategyIntent.SELL_ALL
            decision["user_visible_action"] = True
            _set_execution(decision, ExecutionStatus.EXECUTABLE, ExecutionReason.EXECUTABLE)
            continue
        if intent == StrategyIntent.REDUCE:
            decision["action_enum"] = StrategyIntent.REDUCE
            decision["user_visible_action"] = True
            _set_execution(decision, ExecutionStatus.EXECUTABLE, ExecutionReason.EXECUTABLE)
            continue
        if original == StrategyIntent.DATA_ERROR or intent == StrategyIntent.DATA_ERROR:
            decision["action_enum"] = StrategyIntent.DATA_ERROR
            decision["user_visible_action"] = True
            _set_execution(decision, ExecutionStatus.BLOCKED, ExecutionReason.DATA_ERROR, detail="Data error requires manual review.", hint="Fix data quality before execution.")
            continue
        if original == StrategyIntent.BLOCKED and (intent == StrategyIntent.BLOCKED or blocked_reason in STRATEGY_BLOCK_REASONS):
            decision["action_enum"] = StrategyIntent.BLOCKED
            decision["strategy_intent"] = StrategyIntent.BLOCKED
            decision["user_visible_action"] = True
            _set_execution(
                decision,
                ExecutionStatus.BLOCKED,
                ExecutionReason.STRATEGY_BLOCKED,
                detail=blocked_reason,
                hint="Strategy or risk control must clear before execution.",
            )
            continue
        if intent in BUY_INTENTS and decision.get("execution_action_type") in {"NEW_BUY", "ADD"}:
            candidates.append(decision)
            continue
        decision["user_visible_action"] = False
        _set_execution(decision, ExecutionStatus.NO_ACTION, ExecutionReason.NO_ACTION)

    ranked = sorted(candidates, key=lambda item: _rank_key(item, policy))
    for index, decision in enumerate(ranked, start=1):
        decision["compact_rank"] = index

    remaining_cash = max(0.0, policy.current_cash - policy.reserved_cash - policy.account_equity * policy.cash_reserve_ratio)
    positions_count = len(holdings)
    if positions_count <= 0 and account_state:
        positions_count = max(0, _safe_int(account_state.get("holdings_count")))
    industry_counts = Counter(str(item.get("industry", "")) for item in holdings if _safe_int(item.get("current_shares")) > 0 or _safe_int(item.get("current_position_tranches")) > 0)
    new_buys_today = 0
    adds_today = 0
    new_seen = 0

    for decision in ranked:
        action_type = str(decision.get("execution_action_type"))
        industry = str(decision.get("industry", ""))
        target_value = _target_position_value(decision, policy)
        current_shares = _safe_int(decision.get("current_shares"))
        price = _safe_float(decision.get("close", decision.get("target_price_reference")))
        current_value = _safe_float(decision.get("current_position_value"), current_shares * price)
        if current_value <= 0 and current_shares > 0:
            current_value = current_shares * price
        intended_value = max(0.0, target_value - current_value)
        decision["target_action_budget"] = intended_value

        if action_type == "NEW_BUY":
            new_seen += 1
            if new_seen > policy.compact_candidate_limit:
                _watch(
                    decision,
                    ExecutionReason.WATCH_COMPACT_RANK_OUT,
                    "New buy candidate is outside the compact account candidate limit.",
                    "Wait for rank to move inside the compact candidate limit.",
                )
                continue
            if positions_count + new_buys_today >= policy.max_positions:
                _watch(
                    decision,
                    ExecutionReason.WATCH_PORTFOLIO_FULL,
                    "Portfolio is already at the configured max position count.",
                    "Wait for existing holdings to trigger REDUCE/SELL_ALL, or for replacement score to exceed the advisory threshold.",
                )
                _replacement_advisory(decision, holdings, policy)
                continue
            if new_buys_today >= policy.max_new_positions_per_day:
                _watch(
                    decision,
                    ExecutionReason.WATCH_DAILY_NEW_LIMIT,
                    "Daily new-position limit has been used.",
                    "Wait for the next trading day.",
                )
                continue
            if industry_counts[industry] >= policy.industry_max_positions:
                _watch(
                    decision,
                    ExecutionReason.WATCH_INDUSTRY_CONCENTRATION,
                    "Industry position count reached the compact account limit.",
                    "Wait for industry exposure to fall or for another industry candidate.",
                )
                continue
            payload = size_new_buy(
                symbol=str(decision.get("symbol", "")),
                price=price,
                account_equity=policy.account_equity,
                available_cash=remaining_cash / max(1.0 + commission_rate, 1e-9),
                min_trade_value=policy.min_trade_value,
                round_lot=policy.round_lot,
                max_single_stock_weight=policy.max_single_stock_weight,
                target_position_value=target_value,
            )
            cash_used = _apply_sizer_payload(decision, payload, policy, commission_rate)
            if payload.get("execution_status") == ExecutionStatus.EXECUTABLE:
                remaining_cash = max(0.0, remaining_cash - cash_used)
                new_buys_today += 1
                industry_counts[industry] += 1
            continue

        if action_type == "ADD":
            if adds_today >= policy.max_adds_per_day:
                _watch(
                    decision,
                    ExecutionReason.WATCH_DAILY_ADD_LIMIT,
                    "Daily add-position limit has been used.",
                    "Wait for the next trading day.",
                )
                continue
            payload = size_add(
                symbol=str(decision.get("symbol", "")),
                price=price,
                current_position_shares=current_shares,
                current_position_value=current_value,
                account_equity=policy.account_equity,
                available_cash=remaining_cash / max(1.0 + commission_rate, 1e-9),
                min_trade_value=policy.min_trade_value,
                round_lot=policy.round_lot,
                max_single_stock_weight=policy.max_single_stock_weight,
                target_position_value=target_value,
                intended_order_value=intended_value,
                pending_add_value=_safe_float(decision.get("pending_add_value")),
            )
            cash_used = _apply_sizer_payload(decision, payload, policy, commission_rate)
            if payload.get("execution_status") == ExecutionStatus.EXECUTABLE:
                remaining_cash = max(0.0, remaining_cash - cash_used)
                adds_today += 1

    return sorted(output, key=lambda item: (item.get("holding_state") == "NONE", str(item.get("symbol", ""))))
