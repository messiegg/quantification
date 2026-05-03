from __future__ import annotations

import base64
import inspect
import time

import pandas as pd
import requests
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.primitives.padding import PKCS7

from src.adapters.base import DataAdapter
from src.adapters.common import cache_file, normalize_frame, normalize_symbol, retry_call
from src.utils.config import resolve_path
from src.utils.exceptions import DataSourceError


class AkshareAdapter(DataAdapter):
    name = "akshare"

    def __init__(self, config: dict) -> None:
        self.config = config
        self.retry_cfg = config.get("retry", {})
        raw_dir = config.get("storage", {}).get("raw_dir", "data/raw")
        self.cache_root = resolve_path(raw_dir) / self.name

    def _ak(self):
        try:
            import akshare as ak
        except ImportError as exc:
            raise DataSourceError("akshare is not installed.") from exc
        return ak

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

    def _invoke(self, fn_name: str, **kwargs):
        fn = getattr(self._ak(), fn_name)
        signature = inspect.signature(fn)
        filtered_kwargs = {key: value for key, value in kwargs.items() if key in signature.parameters}
        return fn(**filtered_kwargs)

    @staticmethod
    def _cninfo_accept_enckey() -> str:
        key = b"1234567887654321"
        iv = b"1234567887654321"
        payload = str(int(time.time())).encode("utf-8")
        padder = PKCS7(128).padder()
        padded = padder.update(payload) + padder.finalize()
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv))
        encryptor = cipher.encryptor()
        ciphertext = encryptor.update(padded) + encryptor.finalize()
        return base64.b64encode(ciphertext).decode("utf-8")

    def _cninfo_headers(self) -> dict[str, str]:
        return {
            "Accept": "*/*",
            "Accept-Enckey": self._cninfo_accept_enckey(),
            "Accept-Encoding": "gzip, deflate",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Cache-Control": "no-cache",
            "Host": "webapi.cninfo.com.cn",
            "Origin": "https://webapi.cninfo.com.cn",
            "Pragma": "no-cache",
            "Referer": "https://webapi.cninfo.com.cn/",
            "User-Agent": "Mozilla/5.0",
            "X-Requested-With": "XMLHttpRequest",
        }

    def _cninfo_json(self, method: str, url: str, params: dict[str, object]) -> dict:
        request = requests.get if method.upper() == "GET" else requests.post
        response = request(url, params=params, headers=self._cninfo_headers(), timeout=30)
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise DataSourceError("CNInfo returned a non-dict payload.")
        return payload

    def get_stock_list(self, as_of_date: str) -> pd.DataFrame:
        detail_frames: list[pd.DataFrame] = []
        stock_list_specs = (
            ("stock_list_sh_main", "stock_info_sh_name_code", {"symbol": "主板A股"}, {"证券代码": "code", "证券简称": "name", "上市日期": "listed_date"}),
            ("stock_list_sh_star", "stock_info_sh_name_code", {"symbol": "科创板"}, {"证券代码": "code", "证券简称": "name", "上市日期": "listed_date"}),
            ("stock_list_sz_a", "stock_info_sz_name_code", {"symbol": "A股列表"}, {"A股代码": "code", "A股简称": "name", "A股上市日期": "listed_date"}),
        )
        for namespace, fn_name, kwargs, rename_map in stock_list_specs:
            try:
                frame = self._call_with_cache(
                    namespace,
                    lambda fn_name=fn_name, kwargs=kwargs: self._invoke(fn_name, **kwargs),
                    as_of_date,
                    namespace,
                )
            except DataSourceError:
                continue
            if frame.empty:
                continue
            normalized = frame.rename(columns=rename_map)
            if {"code", "name"} - set(normalized.columns):
                continue
            selected_columns = ["code", "name"]
            if "listed_date" in normalized.columns:
                selected_columns.append("listed_date")
            detail_frames.append(normalized[selected_columns].copy())

        if detail_frames:
            renamed = pd.concat(detail_frames, ignore_index=True)
        else:
            frame = self._call_with_cache(
                "stock_list",
                lambda: self._invoke("stock_info_a_code_name"),
                as_of_date,
            )
            renamed = frame.rename(columns={"code": "code", "name": "name"})
        renamed["code"] = renamed["code"].map(normalize_symbol)
        if "listed_date" in renamed.columns:
            renamed["listed_date"] = pd.to_datetime(renamed["listed_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        else:
            renamed["listed_date"] = pd.NA
        renamed["as_of_date"] = as_of_date
        renamed = renamed.drop_duplicates(subset=["code"]).sort_values("code").reset_index(drop=True)
        return renamed[["code", "name", "listed_date", "as_of_date"]]

    def get_sw_industry_hist(self) -> pd.DataFrame:
        frame = self._call_with_cache(
            "sw_industry_hist",
            lambda: self._invoke("stock_industry_clf_hist_sw"),
            "all",
        )
        if frame.empty:
            raise DataSourceError("AkShare SW industry history is empty.")
        frame["symbol"] = frame["symbol"].astype(str).map(normalize_symbol)
        frame["industry_code"] = frame["industry_code"].astype(str).str.removeprefix("S")
        frame["start_date"] = pd.to_datetime(frame["start_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        frame["update_time"] = pd.to_datetime(frame["update_time"], errors="coerce").dt.strftime("%Y-%m-%d")
        frame["source"] = "sw_hist_akshare"
        return frame[["symbol", "start_date", "industry_code", "update_time", "source"]]

    def get_sw_industry_category_cninfo(self) -> pd.DataFrame:
        def _loader() -> pd.DataFrame:
            payload = self._cninfo_json(
                "GET",
                "https://webapi.cninfo.com.cn/api/stock/p_public0002",
                {"indcode": "", "indtype": "008003", "format": "json"},
            )
            return pd.DataFrame(payload.get("records", []))

        frame = self._call_with_cache("cninfo_sw_category", _loader, "008003")
        if frame.empty:
            raise DataSourceError("CNInfo SW category table is empty.")
        frame = frame.rename(
            columns={
                "SORTCODE": "sort_code",
                "PARENTCODE": "parent_code",
                "SORTNAME": "industry_name",
                "F001V": "industry_name_en",
                "F002D": "end_date",
                "F003V": "industry_standard_code",
                "F004V": "industry_standard_name",
            }
        ).copy()
        frame["sort_code"] = frame["sort_code"].astype(str)
        frame["code"] = frame["sort_code"].str.removeprefix("S")
        frame["level"] = frame["code"].map(
            lambda value: 0
            if value == ""
            else 1
            if len(value) == 2
            else 2
            if len(value) == 4
            else 3
            if len(value) == 6
            else pd.NA
        )
        frame["end_date"] = pd.to_datetime(frame["end_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        frame["source"] = "cninfo_sw_category"
        return frame[
            [
                "sort_code",
                "code",
                "parent_code",
                "industry_name",
                "industry_name_en",
                "industry_standard_code",
                "industry_standard_name",
                "end_date",
                "level",
                "source",
            ]
        ]

    def get_share_change_cninfo(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        code = normalize_symbol(symbol).split(".")[0]

        def _loader() -> pd.DataFrame:
            payload = self._cninfo_json(
                "POST",
                "https://webapi.cninfo.com.cn/api/stock/p_stock2215",
                {
                    "scode": code,
                    "sdate": pd.Timestamp(start_date).strftime("%Y-%m-%d"),
                    "edate": pd.Timestamp(end_date).strftime("%Y-%m-%d"),
                },
            )
            return pd.DataFrame(payload.get("records", []))

        frame = self._call_with_cache("cninfo_share_change", _loader, code, start_date, end_date)
        if frame.empty:
            raise DataSourceError(f"CNInfo share change empty for {symbol}.")
        frame = frame.rename(
            columns={
                "SECCODE": "symbol",
                "SECNAME": "security_name",
                "DECLAREDATE": "announce_date",
                "VARYDATE": "change_date",
                "F001V": "reason_code",
                "F002V": "reason",
                "F003N": "total_shares",
                "F021N": "float_shares",
            }
        ).copy()
        frame["symbol"] = frame["symbol"].astype(str).map(normalize_symbol)
        frame["announce_date"] = pd.to_datetime(frame["announce_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        frame["change_date"] = pd.to_datetime(frame["change_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        for column in ("total_shares", "float_shares"):
            frame[column] = pd.to_numeric(frame[column], errors="coerce") * 10000.0
        frame["source"] = "cninfo_share_change"
        return frame[
            [
                "symbol",
                "security_name",
                "announce_date",
                "change_date",
                "total_shares",
                "float_shares",
                "reason",
                "reason_code",
                "source",
            ]
        ]

    def get_industry_change_cninfo(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        code = normalize_symbol(symbol).split(".")[0]

        def _loader() -> pd.DataFrame:
            payload = self._cninfo_json(
                "POST",
                "https://webapi.cninfo.com.cn/api/stock/p_stock2110",
                {
                    "scode": code,
                    "sdate": pd.Timestamp(start_date).strftime("%Y-%m-%d"),
                    "edate": pd.Timestamp(end_date).strftime("%Y-%m-%d"),
                },
            )
            return pd.DataFrame(payload.get("records", []))

        frame = self._call_with_cache("cninfo_industry_change", _loader, code, start_date, end_date)
        if frame.empty:
            raise DataSourceError(f"CNInfo industry change empty for {symbol}.")
        frame = frame.rename(
            columns={
                "SECCODE": "symbol",
                "SECNAME": "security_name",
                "VARYDATE": "change_date",
                "F002V": "standard_name",
                "F003V": "industry_code",
                "F004V": "industry_l1",
                "F005V": "industry_l2",
                "F006V": "industry_l3",
                "F007V": "industry_l4",
            }
        ).copy()
        frame["symbol"] = frame["symbol"].astype(str).map(normalize_symbol)
        frame["change_date"] = pd.to_datetime(frame["change_date"], errors="coerce").dt.strftime("%Y-%m-%d")
        frame["industry_code"] = frame["industry_code"].astype(str).str.removeprefix("S")
        frame["source"] = "cninfo_industry_change"
        return frame[
            [
                "symbol",
                "security_name",
                "change_date",
                "standard_name",
                "industry_code",
                "industry_l1",
                "industry_l2",
                "industry_l3",
                "industry_l4",
                "source",
            ]
        ]

    def get_price_daily(
        self, symbols: list[str], start_date: str, end_date: str, adjust: str
    ) -> pd.DataFrame:
        rows: list[pd.DataFrame] = []
        for symbol in symbols:
            code = symbol.split(".")[0]
            frame = self._call_with_cache(
                "price_daily",
                lambda code=code: self._invoke(
                    "stock_zh_a_hist",
                    symbol=code,
                    period="daily",
                    start_date=start_date.replace("-", ""),
                    end_date=end_date.replace("-", ""),
                    adjust=adjust,
                ),
                code,
                start_date,
                end_date,
                adjust,
            )
            frame = normalize_frame(frame, {"code": normalize_symbol(code)})
            rows.append(frame[["code", "date", "open", "high", "low", "close", "volume", "amount"]])
        if not rows:
            raise DataSourceError("AkShare price_daily received no symbols.")
        return pd.concat(rows, ignore_index=True)

    def get_index_daily(self, symbol: str, start_date: str, end_date: str) -> pd.DataFrame:
        frame = self._call_with_cache(
            "index_daily",
            lambda: self._invoke(
                "index_zh_a_hist",
                symbol=symbol,
                period="daily",
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
            ),
            symbol,
            start_date,
            end_date,
        )
        frame = normalize_frame(frame, {"code": normalize_symbol(symbol)})
        return frame[["code", "date", "open", "high", "low", "close", "volume", "amount"]]

    def get_stock_valuation_history(self, symbol: str, metric: str, period: str) -> pd.DataFrame:
        code = symbol.split(".")[0]
        indicator_map = {
            "pb": "市净率",
            "pe_ttm": "市盈率(TTM)",
        }
        indicator = indicator_map.get(metric)
        if indicator is None:
            raise DataSourceError(f"AkShare does not support valuation metric {metric}.")
        frame = self._call_with_cache(
            "valuation_history",
            lambda: self._invoke(
                "stock_zh_valuation_baidu",
                symbol=code,
                indicator=indicator,
                period="全部",
            ),
            code,
            metric,
            "all",
        )
        frame = normalize_frame(frame, {"code": normalize_symbol(code), "metric": metric})
        cutoff = pd.to_datetime(period, errors="coerce")
        if pd.notna(cutoff) and "date" in frame.columns:
            frame = frame[pd.to_datetime(frame["date"], errors="coerce") <= cutoff].copy()
        value_column = "value"
        if value_column not in frame.columns:
            candidate_columns = [column for column in frame.columns if column not in {"code", "date", "metric"}]
            if not candidate_columns:
                raise DataSourceError(f"Cannot detect valuation value column for {symbol} {metric}.")
            frame = frame.rename(columns={candidate_columns[-1]: value_column})
        frame[value_column] = pd.to_numeric(frame[value_column], errors="coerce")
        frame = frame.dropna(subset=["date", value_column])
        if frame.empty:
            raise DataSourceError(f"AkShare valuation history empty for {symbol} {metric}.")
        return frame[["code", "date", "metric", "value"]]

    def get_industry_daily(self, start_date: str, end_date: str, level: str) -> pd.DataFrame:
        frame = self._call_with_cache(
            "industry_daily",
            lambda: self._invoke(
                "index_analysis_daily_sw",
                symbol=level,
                start_date=start_date.replace("-", ""),
                end_date=end_date.replace("-", ""),
            ),
            start_date,
            end_date,
            level,
        )
        frame = normalize_frame(frame)
        frame = frame.rename(
            columns={
                "指数代码": "industry_code",
                "指数名称": "industry_name",
                "发布日期": "date",
                "市盈率": "pe_ttm",
                "市净率": "pb",
            }
        )
        required = ["industry_code", "industry_name", "date"]
        missing = [item for item in required if item not in frame.columns]
        if missing:
            raise DataSourceError(f"Industry daily missing columns: {missing}")
        return frame

    def get_industry_members(self, industry_code: str, as_of_date: str | None = None) -> pd.DataFrame:
        def _load_primary():
            return self._invoke("sw_index_third_cons", symbol=industry_code)

        def _load_fallback():
            return self._invoke("index_component_sw", symbol=industry_code)

        try:
            frame = self._call_with_cache("industry_members", _load_primary, industry_code, as_of_date)
            if frame.empty:
                raise DataSourceError(f"AkShare primary industry_members empty for {industry_code}.")
        except DataSourceError:
            frame = self._call_with_cache("industry_members_fallback", _load_fallback, industry_code, as_of_date)
        frame = frame.rename(
            columns={
                "证券代码": "code",
                "成分券代码": "code",
                "股票代码": "code",
                "证券简称": "name",
                "股票简称": "name",
                "证券名称": "name",
            }
        )
        required = {"code", "name"}
        missing = required - set(frame.columns)
        if missing:
            raise DataSourceError(f"Industry members missing columns: {sorted(missing)}")
        frame["code"] = frame["code"].astype(str).map(normalize_symbol)
        frame["industry_code"] = industry_code
        frame["as_of_date"] = as_of_date
        return frame[["industry_code", "code", "name", "as_of_date"]]

    def get_financials(
        self, symbol: str, start_date: str | None = None, end_date: str | None = None
    ) -> pd.DataFrame:
        code = symbol.split(".")[0]
        frame = self._call_with_cache(
            "financial_abstract",
            lambda: self._invoke("stock_financial_abstract", symbol=code),
            code,
        )
        if frame.empty:
            raise DataSourceError(f"AkShare financial abstract empty for {symbol}.")

        metric_aliases = {
            "roe": ["净资产收益率(ROE)", "净资产收益率_平均", "摊薄净资产收益率"],
            "net_profit": ["归母净利润", "净利润"],
            "cfo": ["经营现金流量净额"],
            "debt_to_assets": ["资产负债率"],
        }
        value_columns = [column for column in frame.columns if str(column).isdigit()]
        if not value_columns:
            raise DataSourceError(f"AkShare financial abstract has no report-date columns for {symbol}.")

        normalized = frame.rename(columns={"指标": "metric_name"})[["metric_name", *value_columns]].copy()
        normalized["metric_name"] = normalized["metric_name"].astype(str)
        rows: list[pd.DataFrame] = []
        for target_field, aliases in metric_aliases.items():
            subset = normalized[normalized["metric_name"].isin(aliases)].copy()
            if subset.empty:
                continue
            selected = subset.iloc[0]
            melted = selected[value_columns].rename_axis("report_date").reset_index(name=target_field)
            rows.append(melted)
        if not rows:
            raise DataSourceError(f"AkShare financial abstract missing required metrics for {symbol}.")

        merged = rows[0]
        for extra in rows[1:]:
            merged = merged.merge(extra, how="outer", on="report_date")
        merged["report_date"] = pd.to_datetime(merged["report_date"], format="%Y%m%d", errors="coerce")
        merged = merged.dropna(subset=["report_date"]).copy()
        merged["announcement_date"] = pd.NaT
        merged["code"] = normalize_symbol(code)
        merged["date"] = merged["report_date"].dt.strftime("%Y-%m-%d")
        merged["report_date"] = merged["report_date"].dt.strftime("%Y-%m-%d")
        for column in ("roe", "net_profit", "cfo", "debt_to_assets"):
            if column not in merged.columns:
                merged[column] = pd.NA
            merged[column] = pd.to_numeric(merged[column], errors="coerce")
        if start_date:
            merged = merged[merged["report_date"] >= start_date].copy()
        if end_date:
            merged = merged[merged["report_date"] <= end_date].copy()
        if merged.empty:
            raise DataSourceError(f"AkShare financial abstract filtered empty for {symbol}.")
        return merged[
            ["code", "date", "report_date", "announcement_date", "roe", "net_profit", "cfo", "debt_to_assets"]
        ].sort_values("report_date")

    def get_dividend_events(self, report_date: str) -> pd.DataFrame:
        report_ts = pd.Timestamp(report_date)
        date_arg = report_ts.strftime("%Y%m%d")
        frame = self._call_with_cache(
            "dividend_events",
            lambda: self._invoke("stock_fhps_em", date=date_arg),
            date_arg,
        )
        if frame.empty:
            raise DataSourceError(f"AkShare dividend batch empty for report_date={report_date}.")

        normalized = frame.rename(
            columns={
                "代码": "code",
                "名称": "name",
                "现金分红-现金分红比例": "cash_dividend_per_10",
                "现金分红-股息率": "dividend_yield",
                "预案公告日": "plan_announcement_date",
                "股权登记日": "record_date",
                "除权除息日": "ex_dividend_date",
                "方案进度": "progress",
                "最新公告日期": "announcement_date",
                "总股本": "total_shares",
            }
        ).copy()
        required = {"code", "cash_dividend_per_10"}
        missing = required - set(normalized.columns)
        if missing:
            raise DataSourceError(f"AkShare dividend batch missing columns: {sorted(missing)}")

        normalized["code"] = normalized["code"].astype(str).map(normalize_symbol)
        normalized["report_date"] = report_ts.strftime("%Y-%m-%d")
        for column in ("announcement_date", "plan_announcement_date", "record_date", "ex_dividend_date"):
            if column not in normalized.columns:
                normalized[column] = pd.NaT
            normalized[column] = pd.to_datetime(normalized[column], errors="coerce").dt.strftime("%Y-%m-%d")
        for column in ("cash_dividend_per_10", "dividend_yield", "total_shares"):
            if column not in normalized.columns:
                normalized[column] = pd.NA
            normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        normalized["cash_dividend_per_share"] = normalized["cash_dividend_per_10"] / 10.0
        normalized["source"] = "stock_fhps_em"
        return normalized[
            [
                "code",
                "name",
                "report_date",
                "announcement_date",
                "plan_announcement_date",
                "record_date",
                "ex_dividend_date",
                "cash_dividend_per_10",
                "cash_dividend_per_share",
                "dividend_yield",
                "progress",
                "total_shares",
                "source",
            ]
        ].sort_values(["report_date", "code"]).reset_index(drop=True)

    def get_st_flags(self, symbols: list[str], as_of_date: str) -> pd.DataFrame:
        listing = self.get_stock_list(as_of_date)
        listing["is_st"] = listing["name"].astype(str).str.contains("ST", case=False, na=False)
        filtered = listing[listing["code"].isin([normalize_symbol(item) for item in symbols])].copy()
        filtered["date"] = as_of_date
        return filtered[["code", "date", "is_st"]]

    def get_market_caps(self, symbols: list[str], as_of_date: str) -> pd.DataFrame:
        raise DataSourceError("AkShare market cap retrieval is delegated to EfinanceAdapter for stability.")
