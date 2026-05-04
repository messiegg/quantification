#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
import yaml

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.utils.config import load_yaml_optional, resolve_path


PAPER_COLUMNS = [
    "trade_id",
    "date",
    "profile",
    "ts_code",
    "name",
    "side",
    "action",
    "signal_level",
    "shares",
    "price",
    "amount",
    "fee",
    "tax",
    "slippage",
    "cash_before",
    "cash_after",
    "position_before",
    "position_after",
    "source",
    "source_report",
    "human_review_status",
    "notes",
]
ALLOWED_SOURCES = {"paper_next_bar_simulated", "manual_user_entered", "correction"}
ALLOWED_REVIEW_STATUS = {"pending", "approved", "rejected", "executed_paper", "corrected"}
EXAMPLE_DIR = ROOT / "fixtures" / "observation"


def _observation_paths() -> dict[str, Path]:
    cfg = load_yaml_optional("config/observation.yml").get("manual_observation", {})
    return {
        "account": resolve_path(cfg.get("paper_account_path", "data/observation/paper_account.yml")),
        "trades": resolve_path(cfg.get("paper_trades_path", "data/observation/paper_trades.csv")),
        "positions": resolve_path(cfg.get("paper_positions_path", "data/observation/paper_positions.yml")),
        "report_dir": resolve_path(cfg.get("observation_report_dir", "reports/observation")),
    }


def ensure_paper_observation_files(initial_capital: float | None = None) -> dict[str, Path]:
    paths = _observation_paths()
    cfg = load_yaml_optional("config/observation.yml").get("manual_observation", {})
    capital = float(initial_capital if initial_capital is not None else cfg.get("initial_paper_capital", 200000))
    for path in paths.values():
        if path.suffix:
            path.parent.mkdir(parents=True, exist_ok=True)
    if not paths["account"].exists() and (EXAMPLE_DIR / "paper_account.example.yml").exists():
        paths["account"].write_text((EXAMPLE_DIR / "paper_account.example.yml").read_text(encoding="utf-8"), encoding="utf-8")
    if not paths["account"].exists():
        payload = {
            "paper_account": {
                "initial_capital": capital,
                "current_cash": capital,
                "total_equity": capital,
                "mode": "paper_observation_only",
                "broker_connected": False,
                "auto_order_enabled": False,
            }
        }
        paths["account"].write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    if not paths["trades"].exists() and (EXAMPLE_DIR / "paper_trades.example.csv").exists():
        paths["trades"].write_text((EXAMPLE_DIR / "paper_trades.example.csv").read_text(encoding="utf-8"), encoding="utf-8")
    if not paths["trades"].exists():
        with paths["trades"].open("w", newline="", encoding="utf-8") as handle:
            writer = csv.DictWriter(handle, fieldnames=PAPER_COLUMNS)
            writer.writeheader()
    if not paths["positions"].exists() and (EXAMPLE_DIR / "paper_positions.example.yml").exists():
        paths["positions"].write_text((EXAMPLE_DIR / "paper_positions.example.yml").read_text(encoding="utf-8"), encoding="utf-8")
    if not paths["positions"].exists():
        payload = {
            "paper_positions": [],
            "broker_connected": False,
            "auto_order_enabled": False,
            "last_rebuilt_at": datetime.now(timezone.utc).isoformat(),
        }
        paths["positions"].write_text(yaml.safe_dump(payload, allow_unicode=True, sort_keys=False), encoding="utf-8")
    return paths


def _load_account(path: Path) -> dict:
    payload = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    return payload.get("paper_account", {})


def _write_account(path: Path, account: dict) -> None:
    path.write_text(yaml.safe_dump({"paper_account": account}, allow_unicode=True, sort_keys=False), encoding="utf-8")


def _load_trades(path: Path) -> pd.DataFrame:
    if not path.exists():
        return pd.DataFrame(columns=PAPER_COLUMNS)
    frame = pd.read_csv(path)
    for column in PAPER_COLUMNS:
        if column not in frame.columns:
            frame[column] = ""
    return frame[PAPER_COLUMNS].copy()


def _rebuild_positions(trades: pd.DataFrame) -> pd.DataFrame:
    executed = trades[trades["human_review_status"].isin(["executed_paper", "corrected"])].copy()
    if executed.empty:
        return pd.DataFrame(columns=["ts_code", "name", "profile", "shares", "avg_cost", "market_value"])
    rows = []
    for symbol, group in executed.groupby("ts_code", sort=True):
        shares = 0.0
        cost = 0.0
        latest_name = ""
        latest_profile = ""
        latest_price = 0.0
        for row in group.to_dict(orient="records"):
            side = str(row.get("side", "")).upper()
            qty = float(row.get("shares", 0.0) or 0.0)
            price = float(row.get("price", 0.0) or 0.0)
            latest_name = str(row.get("name", latest_name) or latest_name)
            latest_profile = str(row.get("profile", latest_profile) or latest_profile)
            latest_price = price or latest_price
            if side == "BUY":
                cost += qty * price
                shares += qty
            elif side == "SELL":
                if shares > 0:
                    avg = cost / shares
                    cost -= min(qty, shares) * avg
                shares -= min(qty, shares)
        if shares > 1e-9:
            rows.append(
                {
                    "ts_code": symbol,
                    "name": latest_name,
                    "profile": latest_profile,
                    "shares": shares,
                    "avg_cost": cost / shares if shares else 0.0,
                    "market_value": shares * latest_price,
                }
            )
    return pd.DataFrame(rows)


def update_paper_observation(as_of_date: str, profile: str = "combined_v2") -> dict:
    paths = ensure_paper_observation_files()
    report_dir = paths["report_dir"] / as_of_date
    report_dir.mkdir(parents=True, exist_ok=True)
    order_path = report_dir / f"{profile}_manual_order_list.csv"
    trades = _load_trades(paths["trades"])
    account = _load_account(paths["account"])
    cash = float(account.get("current_cash", account.get("initial_capital", 200000)))
    generated = 0
    skipped = 0
    new_rows: list[dict] = []
    if order_path.exists():
        orders = pd.read_csv(order_path)
        for index, order in enumerate(orders.to_dict(orient="records"), start=1):
            symbol = str(order.get("ts_code", ""))
            if not symbol:
                skipped += 1
                continue
            side = str(order.get("side", "")).upper()
            shares = float(order.get("shares", 0.0) or 0.0)
            price = float(order.get("next_bar_price", order.get("price", 0.0)) or 0.0)
            amount = shares * price if shares > 0 and price > 0 else 0.0
            status = "executed_paper" if price > 0 and shares > 0 else "pending"
            source = "paper_next_bar_simulated" if status == "executed_paper" else "manual_user_entered"
            cash_before = cash
            if status == "executed_paper":
                cash = cash - amount if side == "BUY" else cash + amount
            new_rows.append(
                {
                    "trade_id": f"{as_of_date}-{profile}-{index:04d}",
                    "date": as_of_date,
                    "profile": profile,
                    "ts_code": symbol,
                    "name": order.get("name", ""),
                    "side": side,
                    "action": order.get("action", ""),
                    "signal_level": order.get("signal_level", ""),
                    "shares": shares,
                    "price": price,
                    "amount": amount,
                    "fee": 0.0,
                    "tax": 0.0,
                    "slippage": 0.0,
                    "cash_before": cash_before,
                    "cash_after": cash,
                    "position_before": "",
                    "position_after": "",
                    "source": source,
                    "source_report": str(order_path),
                    "human_review_status": status,
                    "notes": "纸面观察记录；不连接券商，不自动下单。",
                }
            )
            generated += 1
    if new_rows:
        trades = pd.concat([trades, pd.DataFrame(new_rows)], ignore_index=True)
    for column in PAPER_COLUMNS:
        if column not in trades.columns:
            trades[column] = ""
    trades[PAPER_COLUMNS].to_csv(paths["trades"], index=False)
    positions = _rebuild_positions(trades)
    paths["positions"].write_text(
        yaml.safe_dump(
            {
                "paper_positions": positions.to_dict(orient="records"),
                "broker_connected": False,
                "auto_order_enabled": False,
                "last_rebuilt_at": datetime.now(timezone.utc).isoformat(),
            },
            allow_unicode=True,
            sort_keys=False,
        ),
        encoding="utf-8",
    )
    account["current_cash"] = cash
    account["total_equity"] = cash + float(positions.get("market_value", pd.Series(dtype=float)).sum())
    account["mode"] = "paper_observation_only"
    account["broker_connected"] = False
    account["auto_order_enabled"] = False
    _write_account(paths["account"], account)
    positions_snapshot = report_dir / "paper_positions_snapshot.csv"
    positions.to_csv(positions_snapshot, index=False)
    update = {
        "as_of_date": as_of_date,
        "profile": profile,
        "broker_connected": False,
        "auto_order_enabled": False,
        "manual_order_list": str(order_path),
        "generated_rows": generated,
        "skipped_rows": skipped,
        "paper_trades_path": str(paths["trades"]),
        "paper_positions_path": str(paths["positions"]),
        "paper_positions_snapshot": str(positions_snapshot),
    }
    lines = [
        "# 纸面观察账户更新",
        "",
        f"- as_of_date: {as_of_date}",
        f"- profile: {profile}",
        "- broker_connected: false",
        "- auto_order_enabled: false",
        f"- manual_order_list: {order_path if order_path.exists() else '缺失'}",
        f"- generated_rows: {generated}",
        f"- skipped_rows: {skipped}",
        "- 说明: 仅记录人工确认或纸面模拟，不连接券商，不自动下单。",
    ]
    (report_dir / "paper_ledger_update.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return update


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Update paper observation ledger from observation manual order list.")
    parser.add_argument("--as-of-date", required=True)
    parser.add_argument("--profile", default="combined_v2")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    update_paper_observation(args.as_of_date, args.profile)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
