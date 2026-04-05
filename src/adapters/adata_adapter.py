from __future__ import annotations

import inspect

import pandas as pd

from src.adapters.base import DataAdapter
from src.adapters.common import cache_file, normalize_symbol, retry_call
from src.utils.config import resolve_path
from src.utils.exceptions import DataSourceError


class ADataAdapter(DataAdapter):
    name = "adata"

    def __init__(self, config: dict) -> None:
        self.config = config
        self.retry_cfg = config.get("retry", {})
        raw_dir = config.get("storage", {}).get("raw_dir", "data/raw")
        self.cache_root = resolve_path(raw_dir) / self.name

    def is_available(self) -> bool:
        try:
            self._adata()
        except DataSourceError:
            return False
        return True

    def _adata(self):
        try:
            import adata
        except ImportError as exc:
            raise DataSourceError("adata is not installed.") from exc
        return adata

    def _call_with_cache(self, namespace: str, loader, *cache_parts: object) -> pd.DataFrame:
        path = cache_file(self.cache_root, namespace, *cache_parts)
        if path.exists():
            return pd.read_parquet(path)
        frame = retry_call(
            loader,
            attempts=int(self.retry_cfg.get("attempts", 3)),
            backoff_seconds=float(self.retry_cfg.get("backoff_seconds", 1.5)),
        )
        frame.to_parquet(path, index=False)
        return frame

    def _call(self, func, namespace: str, *cache_parts: object, **kwargs) -> pd.DataFrame:
        signature = inspect.signature(func)
        filtered_kwargs = {key: value for key, value in kwargs.items() if key in signature.parameters}
        return self._call_with_cache(namespace, lambda: func(**filtered_kwargs), *cache_parts)

    @staticmethod
    def _stock_code(symbol: str) -> str:
        return normalize_symbol(symbol).split(".")[0]

    def _share_history(self, symbol: str) -> pd.DataFrame:
        code = self._stock_code(symbol)
        frame = self._call(
            self._adata().stock.info.get_stock_shares,
            "stock_shares",
            code,
            "history",
            stock_code=code,
            is_history=True,
        )
        if frame.empty:
            raise DataSourceError(f"AData stock shares empty for {symbol}.")
        frame = frame.rename(columns={"stock_code": "code", "change_date": "effective_date", "total_shares": "total_shares"})
        frame["code"] = frame["code"].astype(str).map(normalize_symbol)
        frame["effective_date"] = pd.to_datetime(frame["effective_date"], errors="coerce")
        frame["total_shares"] = pd.to_numeric(frame["total_shares"], errors="coerce")
        frame = frame.dropna(subset=["effective_date", "total_shares"]).sort_values("effective_date")
        if frame.empty:
            raise DataSourceError(f"AData stock shares invalid for {symbol}.")
        return frame[["code", "effective_date", "total_shares"]]

    def get_symbol_industries(self, symbol: str, as_of_date: str) -> pd.DataFrame:
        code = self._stock_code(symbol)
        frame = self._call(
            self._adata().stock.info.get_industry_sw,
            "industry_symbol_map",
            code,
            as_of_date,
            stock_code=code,
        )
        if frame.empty:
            raise DataSourceError(f"AData industry mapping empty for {symbol}.")
        frame = frame.rename(
            columns={
                "stock_code": "code",
                "sw_code": "industry_code",
                "industry_name": "industry_name",
                "industry_type": "industry_level",
            }
        ).copy()
        frame["code"] = frame["code"].astype(str).map(normalize_symbol)
        frame["industry_level"] = frame["industry_level"].replace({"申万一级": "first", "申万二级": "second", "申万三级": "third"})
        frame["as_of_date"] = as_of_date
        required = {"code", "industry_code", "industry_name", "industry_level"}
        missing = required - set(frame.columns)
        if missing:
            raise DataSourceError(f"AData industry mapping missing columns: {sorted(missing)}")
        return frame[["code", "industry_code", "industry_name", "industry_level", "as_of_date"]].dropna(
            subset=["code", "industry_code", "industry_name"]
        )

    def get_stock_list(self, as_of_date: str) -> pd.DataFrame:
        raise DataSourceError("AData stock list is not used as a primary source in this project.")

    def get_price_daily(
        self, symbols: list[str], start_date: str, end_date: str, adjust: str
    ) -> pd.DataFrame:
        raise DataSourceError("AData price history is not enabled in this project due endpoint instability.")

    def get_index_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        raise DataSourceError("AData index history is not enabled in this project.")

    def get_stock_valuation_history(self, symbol: str, metric: str, period: str) -> pd.DataFrame:
        raise DataSourceError("AData valuation history is not implemented in this project.")

    def get_industry_daily(self, start_date: str, end_date: str, level: str) -> pd.DataFrame:
        raise DataSourceError("AData does not provide industry daily history in this project.")

    def get_industry_members(self, industry_code: str, as_of_date: str | None = None) -> pd.DataFrame:
        raise DataSourceError("AData industry mapping is symbol-based; use get_symbol_industries instead.")

    def get_financials(
        self, symbol: str, start_date: str | None = None, end_date: str | None = None
    ) -> pd.DataFrame:
        code = self._stock_code(symbol)
        frame = self._call(
            self._adata().stock.finance.get_core_index,
            "financial_core_index",
            code,
            stock_code=code,
        )
        if frame.empty:
            raise DataSourceError(f"AData core financials empty for {symbol}.")
        frame = frame.rename(
            columns={
                "stock_code": "code",
                "report_date": "report_date",
                "notice_date": "announcement_date",
                "roe_wtd": "roe",
                "net_profit_attr_sh": "net_profit",
                "asset_liab_ratio": "debt_to_assets",
                "oper_cf_ps": "oper_cf_ps",
                "net_asset_ps": "net_asset_ps",
            }
        ).copy()
        frame["code"] = frame["code"].astype(str).map(normalize_symbol)
        frame["report_date"] = pd.to_datetime(frame["report_date"], errors="coerce")
        frame["announcement_date"] = pd.to_datetime(frame["announcement_date"], errors="coerce")
        for column in ("roe", "net_profit", "debt_to_assets", "oper_cf_ps", "net_asset_ps"):
            if column in frame.columns:
                frame[column] = pd.to_numeric(frame[column], errors="coerce")
            else:
                frame[column] = pd.NA
        shares = self._share_history(symbol)
        merged = pd.merge_asof(
            frame.sort_values("report_date"),
            shares.sort_values("effective_date"),
            left_on="report_date",
            right_on="effective_date",
            by="code",
            direction="backward",
        )
        merged["cfo"] = merged["oper_cf_ps"] * merged["total_shares"]
        merged["equity"] = merged["net_asset_ps"] * merged["total_shares"]
        merged["date"] = merged["report_date"].dt.strftime("%Y-%m-%d")
        merged["report_date"] = merged["report_date"].dt.strftime("%Y-%m-%d")
        merged["announcement_date"] = merged["announcement_date"].dt.strftime("%Y-%m-%d")
        if start_date:
            merged = merged[merged["report_date"] >= start_date].copy()
        if end_date:
            merged = merged[merged["report_date"] <= end_date].copy()
        merged["is_st"] = False
        merged = merged.drop_duplicates(subset=["code", "report_date", "announcement_date"]).sort_values("report_date")
        if merged.empty:
            raise DataSourceError(f"AData core financials filtered empty for {symbol}.")
        return merged[
            [
                "code",
                "date",
                "report_date",
                "announcement_date",
                "roe",
                "net_profit",
                "cfo",
                "debt_to_assets",
                "equity",
                "net_asset_ps",
                "is_st",
            ]
        ]

    def get_st_flags(self, symbols: list[str], as_of_date: str) -> pd.DataFrame:
        raise DataSourceError("AData ST flags are not implemented in this project.")

    def get_market_caps(self, symbols: list[str], as_of_date: str) -> pd.DataFrame:
        raise DataSourceError("AData market caps are not implemented in this project.")
