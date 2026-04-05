from __future__ import annotations

import base64
import contextlib
import io
from multiprocessing import get_context
import time
from pathlib import Path

import pandas as pd
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from src.adapters.baostock_adapter import BaoStockAdapter
from src.adapters.common import is_a_share_equity_symbol, normalize_frame, normalize_symbol
from src.adapters.factory import create_default_adapter
from src.utils.config import resolve_path
from src.utils.exceptions import DataSourceError


def strict_run_dates(as_of_date: str, data_cfg: dict) -> dict[str, str]:
    strict_cfg = data_cfg.get("strict_run", {})
    return {
        "start_date": str(strict_cfg.get("price_history_start_date", "2021-01-01")),
        "financial_start_date": str(strict_cfg.get("financial_history_start_date", "2020-01-01")),
        "as_of_date": as_of_date,
        "blocker_dir": str(strict_cfg.get("blocker_dir", "reports/strict")),
    }


def blocker_dir(data_cfg: dict) -> Path:
    strict_cfg = data_cfg.get("strict_run", {})
    return resolve_path(str(strict_cfg.get("blocker_dir", "reports/strict")))


def first_existing_tdx_dir(data_cfg: dict) -> Path | None:
    for item in data_cfg.get("tdx", {}).get("local_dirs", []):
        path = resolve_path(str(item))
        if path.exists():
            return path
    return None


def fetch_pytdx_stock_list(data_cfg: dict, as_of_date: str) -> pd.DataFrame:
    try:
        from pytdx.hq import TdxHq_API
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise DataSourceError("pytdx is not installed.") from exc

    hosts = data_cfg.get("tdx", {}).get("pytdx_hosts", [])
    last_error: Exception | None = None
    for item in hosts:
        if len(item) < 3:
            continue
        _, host, port = item
        api = TdxHq_API(heartbeat=True)
        try:
            connected = api.connect(str(host), int(port), time_out=5)
            if not connected:
                continue
            frames: list[pd.DataFrame] = []
            for market in (0, 1):
                count = int(api.get_security_count(market))
                for start in range(0, count, 1000):
                    data = api.get_security_list(market, start)
                    if not data:
                        continue
                    frame = api.to_df(data)
                    if frame is None or frame.empty:
                        continue
                    frame["market"] = "sz" if market == 0 else "sh"
                    frames.append(frame)
            api.disconnect()
            if not frames:
                raise DataSourceError("pytdx returned no securities.")
            combined = pd.concat(frames, ignore_index=True)
            if "code" not in combined.columns or "name" not in combined.columns:
                raise DataSourceError("pytdx security list missing code/name columns.")
            combined["code"] = [
                normalize_symbol(f"{code}.{market}") for code, market in zip(combined["code"], combined["market"], strict=False)
            ]
            combined = combined[combined["code"].map(is_a_share_equity_symbol)].copy()
            combined["as_of_date"] = as_of_date
            combined["listed_date"] = pd.NA
            combined = combined.rename(columns={"name": "name"})
            return combined[["code", "name", "listed_date", "as_of_date"]].drop_duplicates(subset=["code"]).sort_values("code")
        except Exception as exc:  # pragma: no cover - exercised in live runs
            last_error = exc
            try:
                api.disconnect()
            except Exception:
                pass
            continue
    raise DataSourceError(f"pytdx stock list failed: {last_error}")


def fetch_tdx_local_prices(tdx_dir: Path, symbols: list[str], start_date: str, end_date: str) -> pd.DataFrame:
    try:
        from mootdx.reader import Reader
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise DataSourceError("mootdx is not installed but a local TDX directory is configured.") from exc

    reader = Reader.factory(market="std", tdxdir=str(tdx_dir))
    frames: list[pd.DataFrame] = []
    for symbol in symbols:
        code, market = normalize_symbol(symbol).split(".", 1)
        frame = reader.daily(symbol=code)
        if frame is None or frame.empty:
            continue
        renamed = frame.rename(columns={"datetime": "date"}).copy()
        renamed["date"] = pd.to_datetime(renamed["date"], errors="coerce").dt.strftime("%Y-%m-%d")
        renamed["code"] = f"{code}.{market}"
        for column in ("open", "high", "low", "close", "volume", "amount", "turn"):
            if column not in renamed.columns:
                renamed[column] = pd.NA
            renamed[column] = pd.to_numeric(renamed[column], errors="coerce")
        renamed = renamed[(renamed["date"] >= start_date) & (renamed["date"] <= end_date)].copy()
        frames.append(renamed[["code", "date", "open", "high", "low", "close", "volume", "amount", "turn"]])
    if not frames:
        raise DataSourceError("Local TDX reader returned no price rows.")
    return clean_price_frame(pd.concat(frames, ignore_index=True))


def _fetch_akshare_tx_prices_impl(symbols: list[str], start_date: str, end_date: str, adjust: str) -> pd.DataFrame:
    try:
        import akshare as ak
    except ImportError as exc:  # pragma: no cover - optional dependency
        raise DataSourceError("akshare is not installed.") from exc

    rows: list[pd.DataFrame] = []
    start = start_date.replace("-", "")
    end = end_date.replace("-", "")
    for symbol in symbols:
        normalized = normalize_symbol(symbol)
        code, market = normalized.split(".", 1)
        tx_symbol = f"{market}{code}"
        try:
            with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                frame = ak.stock_zh_a_hist_tx(symbol=tx_symbol, start_date=start, end_date=end, adjust=adjust, timeout=30)
        except Exception as exc:  # pragma: no cover - exercised in live runs
            raise DataSourceError(f"AkShare TX price history failed for {normalized}: {exc}") from exc
        if frame is None or frame.empty:
            raise DataSourceError(f"AkShare TX price history empty for {normalized}.")
        normalized_frame = normalize_frame(frame, {"code": normalized})
        for column in ("open", "high", "low", "close", "volume", "amount", "turn"):
            if column not in normalized_frame.columns:
                normalized_frame[column] = pd.NA
            normalized_frame[column] = pd.to_numeric(normalized_frame[column], errors="coerce")
        rows.append(normalized_frame[["code", "date", "open", "high", "low", "close", "volume", "amount", "turn"]])
    if not rows:
        raise DataSourceError("AkShare TX price history returned no rows.")
    return clean_price_frame(pd.concat(rows, ignore_index=True))


def _queue_frame(queue, frame: pd.DataFrame | None = None, error: str | None = None) -> None:
    payload: dict[str, object] = {"ok": error is None}
    if error is not None:
        payload["error"] = error
    if frame is not None:
        payload["records"] = frame.to_dict(orient="records")
    queue.put(payload)


def _run_frame_process(target, args: tuple, timeout_seconds: int, label: str) -> pd.DataFrame:
    ctx = get_context("spawn")
    queue = ctx.Queue()
    process = ctx.Process(target=target, args=(*args, queue))
    process.start()
    process.join(timeout_seconds)
    if process.is_alive():
        process.terminate()
        process.join(timeout=5)
        raise DataSourceError(f"{label} timed out after {timeout_seconds}s.")
    if queue.empty():
        raise DataSourceError(f"{label} exited without payload (exit_code={process.exitcode}).")
    payload = queue.get()
    if not payload.get("ok"):
        raise DataSourceError(str(payload.get("error") or f"{label} failed."))
    frame = pd.DataFrame(payload.get("records", []))
    if frame.empty:
        raise DataSourceError(f"{label} returned no rows.")
    return frame


def _akshare_tx_price_worker(symbol: str, start_date: str, end_date: str, adjust: str, queue) -> None:
    try:
        frame = _fetch_akshare_tx_prices_impl([symbol], start_date, end_date, adjust)
        _queue_frame(queue, frame=frame)
    except Exception as exc:  # pragma: no cover - exercised in live runs
        _queue_frame(queue, error=str(exc))


def fetch_akshare_tx_prices(
    symbols: list[str],
    start_date: str,
    end_date: str,
    adjust: str,
    timeout_seconds: int = 45,
) -> pd.DataFrame:
    del timeout_seconds
    return _fetch_akshare_tx_prices_impl(symbols, start_date, end_date, adjust)


def _baostock_price_worker(config: dict, symbol: str, start_date: str, end_date: str, adjust: str, queue) -> None:
    try:
        frame = BaoStockAdapter(config).get_price_daily([symbol], start_date, end_date, adjust)
        _queue_frame(queue, frame=frame)
    except Exception as exc:  # pragma: no cover - exercised in live runs
        _queue_frame(queue, error=str(exc))


def fetch_baostock_prices_safe(
    config: dict,
    symbols: list[str],
    start_date: str,
    end_date: str,
    adjust: str,
    timeout_seconds: int = 45,
) -> pd.DataFrame:
    frames: list[pd.DataFrame] = []
    for symbol in symbols:
        label = f"BaoStock price history for {normalize_symbol(symbol)}"
        frame = _run_frame_process(
            _baostock_price_worker,
            (config, normalize_symbol(symbol), start_date, end_date, adjust),
            timeout_seconds=timeout_seconds,
            label=label,
        )
        frames.append(frame)
    return clean_price_frame(pd.concat(frames, ignore_index=True)) if frames else pd.DataFrame()


def _financial_worker(config: dict, symbol: str, start_date: str, end_date: str, queue) -> None:
    try:
        adapter = create_default_adapter(config)
        frame = adapter.get_financials(symbol, start_date=start_date, end_date=end_date)
        frame["code"] = normalize_symbol(symbol)
        _queue_frame(queue, frame=frame)
    except Exception as exc:  # pragma: no cover - exercised in live runs
        _queue_frame(queue, error=str(exc))


def fetch_financials_safe(
    config: dict,
    symbol: str,
    start_date: str,
    end_date: str,
    timeout_seconds: int = 60,
) -> pd.DataFrame:
    label = f"Financial history for {normalize_symbol(symbol)}"
    return _run_frame_process(
        _financial_worker,
        (config, normalize_symbol(symbol), start_date, end_date),
        timeout_seconds=timeout_seconds,
        label=label,
    )


def clean_price_frame(frame: pd.DataFrame) -> pd.DataFrame:
    if frame.empty:
        return frame.copy()
    cleaned = frame.copy()
    cleaned["code"] = cleaned["code"].astype(str).map(normalize_symbol)
    cleaned["date"] = pd.to_datetime(cleaned["date"], errors="coerce").dt.strftime("%Y-%m-%d")
    for column in ("open", "high", "low", "close", "volume", "amount", "turn"):
        if column not in cleaned.columns:
            cleaned[column] = pd.NA
        cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
    cleaned = cleaned.dropna(subset=["code", "date", "close"]).drop_duplicates(subset=["code", "date"], keep="last")
    return cleaned.sort_values(["code", "date"]).reset_index(drop=True)


def clean_benchmark_frame(frame: pd.DataFrame) -> pd.DataFrame:
    cleaned = clean_price_frame(frame)
    if cleaned.empty:
        return cleaned
    cleaned = cleaned[cleaned["close"] > 0].copy()
    return cleaned.sort_values(["date", "code"]).drop_duplicates(subset=["date"], keep="last").reset_index(drop=True)


def fetch_benchmark_daily(data_cfg: dict, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
    hints = [str(item).strip() for item in data_cfg.get("strict_run", {}).get("benchmark_index_market_hints", ["sh", "sz"])]
    adapter = BaoStockAdapter(data_cfg)
    candidates: list[str] = []
    if "." in str(symbol):
        candidates.append(normalize_symbol(symbol))
    else:
        candidates.extend([f"{symbol}.{market}" for market in hints])
    errors: list[str] = []
    for candidate in candidates:
        try:
            frame = adapter.get_price_daily([candidate], start_date, end_date, adjust="none")
        except Exception as exc:  # pragma: no cover - exercised in live runs
            errors.append(f"{candidate}: {exc}")
            continue
        if frame.empty:
            continue
        return clean_benchmark_frame(frame)
    raise DataSourceError(f"BaoStock benchmark download failed for {symbol}: {' | '.join(errors)}")


def cninfo_accept_enckey() -> str:
    key = b"1234567887654321"
    iv = b"1234567887654321"
    payload = str(int(time.time())).encode("utf-8")
    padder = PKCS7(128).padder()
    padded = padder.update(payload) + padder.finalize()
    cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
    encryptor = cipher.encryptor()
    ciphertext = encryptor.update(padded) + encryptor.finalize()
    return base64.b64encode(ciphertext).decode("utf-8")


def build_shares_daily(price_daily: pd.DataFrame, share_change: pd.DataFrame) -> pd.DataFrame:
    if price_daily.empty or share_change.empty:
        return pd.DataFrame(columns=["symbol", "date", "total_shares", "float_shares", "source"])
    calendar = price_daily[["code", "date"]].drop_duplicates().rename(columns={"code": "symbol"}).copy()
    calendar["date"] = pd.to_datetime(calendar["date"], errors="coerce")
    changes = share_change.copy()
    changes["symbol"] = changes["symbol"].astype(str).map(normalize_symbol)
    changes["change_date"] = pd.to_datetime(changes["change_date"], errors="coerce")
    changes = changes.dropna(subset=["symbol", "change_date"]).sort_values(["symbol", "change_date"])
    merged = pd.merge_asof(
        calendar.sort_values(["date", "symbol"]),
        changes.sort_values(["change_date", "symbol"]),
        left_on="date",
        right_on="change_date",
        by="symbol",
        direction="backward",
    )
    merged["date"] = merged["date"].dt.strftime("%Y-%m-%d")
    merged["source"] = merged["source"].fillna("share_change_cninfo")
    return merged[["symbol", "date", "total_shares", "float_shares", "source"]].drop_duplicates(subset=["symbol", "date"])


def build_market_cap_daily(price_daily: pd.DataFrame, shares_daily: pd.DataFrame) -> pd.DataFrame:
    prices = clean_price_frame(price_daily).rename(columns={"code": "symbol"})
    shares = shares_daily.copy()
    merged = prices.merge(shares, how="left", on=["symbol", "date"])
    merged["total_shares"] = pd.to_numeric(merged["total_shares"], errors="coerce")
    merged["float_shares"] = pd.to_numeric(merged["float_shares"], errors="coerce")
    merged["total_mv"] = pd.to_numeric(merged["close"], errors="coerce") * merged["total_shares"]
    merged["float_mv"] = pd.to_numeric(merged["close"], errors="coerce") * merged["float_shares"]
    merged["market_cap_billion"] = merged["total_mv"] / 1e8
    return merged[
        [
            "symbol",
            "date",
            "close",
            "total_shares",
            "float_shares",
            "total_mv",
            "float_mv",
            "market_cap_billion",
        ]
    ].drop_duplicates(subset=["symbol", "date"])


def _daily_industry_lookup(sw_category: pd.DataFrame) -> tuple[dict[str, str], dict[str, str], dict[str, str]]:
    categories = sw_category.copy()
    categories["sort_code"] = categories["sort_code"].astype(str)
    categories["code"] = categories["code"].astype(str)
    name_by_code = categories.set_index("code")["industry_name"].astype(str).to_dict()
    parent_by_code = categories.set_index("code")["parent_code"].astype(str).str.removeprefix("S").to_dict()
    sort_by_code = categories.set_index("code")["sort_code"].astype(str).to_dict()
    return name_by_code, parent_by_code, sort_by_code


def build_industry_members_effective(
    price_daily: pd.DataFrame,
    industry_history: pd.DataFrame,
    sw_category: pd.DataFrame,
    stock_list: pd.DataFrame | None = None,
) -> pd.DataFrame:
    if price_daily.empty or industry_history.empty:
        return pd.DataFrame(
            columns=[
                "symbol",
                "date",
                "name",
                "industry_raw_code",
                "industry_l1_code",
                "industry_l1",
                "industry_l2_code",
                "industry_l2",
                "industry_l3_code",
                "industry_l3",
                "industry_code",
                "industry",
                "source",
            ]
        )
    prices = price_daily[["code", "date"]].drop_duplicates().rename(columns={"code": "symbol"}).copy()
    prices["symbol"] = prices["symbol"].astype(str).map(normalize_symbol)
    prices["date"] = pd.to_datetime(prices["date"], errors="coerce")

    hist = industry_history.copy()
    hist["symbol"] = hist["symbol"].astype(str).map(normalize_symbol)
    hist["start_date"] = pd.to_datetime(hist["start_date"], errors="coerce")
    hist["industry_raw_code"] = hist["industry_code"].astype(str).str.removeprefix("S")

    name_by_code, parent_by_code, _ = _daily_industry_lookup(sw_category)

    hist["industry_l1_code"] = hist["industry_raw_code"].str[:2]
    hist["industry_l2_code"] = hist["industry_raw_code"].str[:4]
    hist["industry_l3_code"] = hist["industry_raw_code"]
    hist["industry_l1"] = hist["industry_l1_code"].map(name_by_code)
    hist["industry_l2"] = hist["industry_l2_code"].map(name_by_code)
    hist["industry_l3"] = hist["industry_l3_code"].map(name_by_code)

    merged = pd.merge_asof(
        prices.sort_values(["date", "symbol"]),
        hist.sort_values(["start_date", "symbol"]),
        left_on="date",
        right_on="start_date",
        by="symbol",
        direction="backward",
    )
    merged["date"] = merged["date"].dt.strftime("%Y-%m-%d")
    if stock_list is not None and not stock_list.empty and {"code", "name"} <= set(stock_list.columns):
        name_map = stock_list[["code", "name"]].drop_duplicates(subset=["code"]).set_index("code")["name"].astype(str).to_dict()
        merged["name"] = merged["symbol"].map(name_map)
    else:
        merged["name"] = merged["symbol"]
    merged["industry_code"] = merged["industry_l1_code"]
    merged["industry"] = merged["industry_l1"]
    merged["source"] = merged.get("source", "sw_hist")
    return merged[
        [
            "symbol",
            "date",
            "name",
            "industry_raw_code",
            "industry_l1_code",
            "industry_l1",
            "industry_l2_code",
            "industry_l2",
            "industry_l3_code",
            "industry_l3",
            "industry_code",
            "industry",
            "source",
        ]
    ].drop_duplicates(subset=["symbol", "date"])


def build_stock_valuation_daily(market_cap_daily: pd.DataFrame, financials_effective: pd.DataFrame) -> pd.DataFrame:
    if market_cap_daily.empty:
        return pd.DataFrame(columns=["symbol", "date", "pb", "pe_ttm"])
    left = market_cap_daily.copy()
    right = financials_effective.rename(columns={"code": "symbol"}).copy()
    left["date"] = pd.to_datetime(left["date"], errors="coerce")
    right["date"] = pd.to_datetime(right["date"], errors="coerce")
    right = right.sort_values(["date", "symbol"])
    merged = pd.merge_asof(
        left.sort_values(["date", "symbol"]),
        right[
            [
                "symbol",
                "date",
                "equity_effective",
                "net_profit_ttm_effective",
                "report_date",
                "announcement_date",
                "effective_date",
            ]
        ],
        on="date",
        by="symbol",
        direction="backward",
    )
    merged["pb"] = pd.NA
    equity = pd.to_numeric(merged["equity_effective"], errors="coerce")
    profit_ttm = pd.to_numeric(merged["net_profit_ttm_effective"], errors="coerce")
    total_mv = pd.to_numeric(merged["total_mv"], errors="coerce")
    valid_pb = equity > 0
    valid_pe = profit_ttm > 0
    merged.loc[valid_pb, "pb"] = total_mv[valid_pb] / equity[valid_pb]
    merged["pe_ttm"] = pd.NA
    merged.loc[valid_pe, "pe_ttm"] = total_mv[valid_pe] / profit_ttm[valid_pe]
    merged["date"] = merged["date"].dt.strftime("%Y-%m-%d")
    return merged[
        [
            "symbol",
            "date",
            "total_mv",
            "float_mv",
            "market_cap_billion",
            "equity_effective",
            "net_profit_ttm_effective",
            "pb",
            "pe_ttm",
            "report_date",
            "announcement_date",
            "effective_date",
        ]
    ].drop_duplicates(subset=["symbol", "date"])


def build_industry_daily(stock_valuation_daily: pd.DataFrame, industry_members_effective: pd.DataFrame) -> pd.DataFrame:
    if stock_valuation_daily.empty or industry_members_effective.empty:
        return pd.DataFrame(columns=["date", "industry_code", "industry_name", "pb", "pe_ttm", "sample_count"])
    merged = stock_valuation_daily.merge(
        industry_members_effective[["symbol", "date", "industry_code", "industry"]],
        how="left",
        on=["symbol", "date"],
    )
    merged = merged.dropna(subset=["industry_code", "industry"]).copy()
    merged["equity_effective"] = pd.to_numeric(merged["equity_effective"], errors="coerce")
    merged["net_profit_ttm_effective"] = pd.to_numeric(merged["net_profit_ttm_effective"], errors="coerce")
    merged["total_mv"] = pd.to_numeric(merged["total_mv"], errors="coerce")
    merged["valid_pb"] = merged["equity_effective"] > 0
    merged["valid_pe"] = merged["net_profit_ttm_effective"] > 0
    grouped = merged.groupby(["date", "industry_code", "industry"], dropna=False)
    panel = grouped.apply(
        lambda frame: pd.Series(
            {
                "pb": frame.loc[frame["valid_pb"], "total_mv"].sum() / frame.loc[frame["valid_pb"], "equity_effective"].sum()
                if frame["valid_pb"].any() and frame.loc[frame["valid_pb"], "equity_effective"].sum() > 0
                else pd.NA,
                "pe_ttm": frame.loc[frame["valid_pe"], "total_mv"].sum()
                / frame.loc[frame["valid_pe"], "net_profit_ttm_effective"].sum()
                if frame["valid_pe"].any() and frame.loc[frame["valid_pe"], "net_profit_ttm_effective"].sum() > 0
                else pd.NA,
                "sample_count": int(frame["symbol"].nunique()),
            }
        )
    ).reset_index()
    return panel.rename(columns={"industry": "industry_name"})
