"""
Data 模組
負責抓取台股歷史資料，並提供日線轉週線／月線的週期轉換功能
"""
from abc import ABC, abstractmethod
from datetime import date, timedelta
from typing import Optional

import pandas as pd


class BaseDataFetcher(ABC):
    """資料來源的抽象介面，方便日後擴充不同資料來源（例如證交所開放資料）"""

    @abstractmethod
    def fetch_daily_ohlcv(
        self,
        stock_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """
        抓取日線 OHLCV 歷史資料

        回傳的 DataFrame 必須包含以下欄位：
        open, high, low, close, volume
        並以交易日期作為索引（datetime 格式）
        """
        raise NotImplementedError


class TWSEDataFetcher(BaseDataFetcher):
    """
    使用台灣證券交易所（TWSE）官方公開資料抓取上市股票歷史資料

    相較於 yfinance（實質上是在抓取 Yahoo Finance 網頁/API），
    TWSE 是政府單位自己開放的公開資料，從雲端主機（Render、AWS等）呼叫
    不會遇到 Yahoo 近年針對雲端機房IP的反爬蟲封鎖問題，較適合正式部署使用

    僅支援「上市」股票；上櫃股票需改接證券櫃買中心（TPEx）對應的端點，
    目前尚未實作
    """

    BASE_URL = "https://www.twse.com.tw/exchangeReport/STOCK_DAY"

    def fetch_daily_ohlcv(
        self,
        stock_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        import time

        import requests

        if end_date is None:
            end_date = date.today()
        if start_date is None:
            # 預設抓取兩年資料，足夠計算月線、週線指標
            start_date = end_date - timedelta(days=365 * 2)

        session = requests.Session()
        session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; StockAnalysisAPI/1.0)"})

        frames = []
        for i, month_start in enumerate(self._month_range(start_date, end_date)):
            if i > 0:
                time.sleep(0.15)  # 避免短時間內過於密集地呼叫，對伺服器友善一點

            payload = self._fetch_month(session, stock_code, month_start)
            if payload is None:
                continue

            month_df = self._parse_month_payload(payload)
            if month_df is not None and not month_df.empty:
                frames.append(month_df)

        if not frames:
            raise ValueError(f"查無股票代碼 {stock_code} 的歷史資料")

        full_df = pd.concat(frames).sort_index()
        full_df = full_df.loc[
            (full_df.index >= pd.Timestamp(start_date)) & (full_df.index <= pd.Timestamp(end_date))
        ]
        if full_df.empty:
            raise ValueError(f"查無股票代碼 {stock_code} 的歷史資料")

        return full_df[["open", "high", "low", "close", "volume"]]

    def _fetch_month(self, session, stock_code: str, month_start: date) -> Optional[dict]:
        """呼叫TWSE單月份歷史資料端點，失敗或無資料時回傳 None（不中斷整體流程）"""
        import requests

        try:
            resp = session.get(
                self.BASE_URL,
                params={
                    "response": "json",
                    "date": month_start.strftime("%Y%m%d"),
                    "stockNo": stock_code,
                },
                timeout=10,
            )
            resp.raise_for_status()
            payload = resp.json()
        except (requests.RequestException, ValueError):
            return None

        if payload.get("stat") != "OK" or not payload.get("data"):
            return None
        return payload

    @staticmethod
    def _month_range(start_date: date, end_date: date) -> list:
        """產生 start_date 到 end_date 之間，每個月第一天的清單（TWSE以月為單位查詢）"""
        months = []
        cursor = start_date.replace(day=1)
        last = end_date.replace(day=1)
        while cursor <= last:
            months.append(cursor)
            if cursor.month == 12:
                cursor = cursor.replace(year=cursor.year + 1, month=1)
            else:
                cursor = cursor.replace(month=cursor.month + 1)
        return months

    @staticmethod
    def _parse_month_payload(payload: dict) -> Optional[pd.DataFrame]:
        """
        將TWSE單月回應轉換為標準OHLCV DataFrame

        注意兩個TWSE特有的資料格式：
        1. 日期為民國年（例如 "113/06/03"），須轉換為西元年才能當索引
        2. 數值欄位含千分位逗號（例如 "36,322,931"），須先去除才能轉為浮點數
        """
        fields = payload.get("fields", [])
        rows = payload.get("data", [])

        col_map = {
            "日期": "date",
            "開盤價": "open",
            "最高價": "high",
            "最低價": "low",
            "收盤價": "close",
            "成交股數": "volume",
        }
        idx = {name: fields.index(name) for name in col_map if name in fields}
        if "日期" not in idx or "收盤價" not in idx:
            return None

        records = []
        for row in rows:
            try:
                roc_date = row[idx["日期"]]
                roc_year, month, day = roc_date.split("/")
                greg_date = date(int(roc_year) + 1911, int(month), int(day))

                record = {"date": greg_date}
                for name, key in col_map.items():
                    if name == "日期" or name not in idx:
                        continue
                    raw_value = str(row[idx[name]]).replace(",", "").strip()
                    record[key] = float(raw_value) if raw_value not in ("", "--") else float("nan")
                records.append(record)
            except (ValueError, IndexError):
                continue  # 跳過格式異常的單列資料（例如該日無交易的特殊標記）

        if not records:
            return None

        month_df = pd.DataFrame(records).set_index("date")
        month_df.index = pd.to_datetime(month_df.index)
        month_df.index.name = "date"
        for col in ("open", "high", "low", "close", "volume"):
            if col not in month_df.columns:
                month_df[col] = float("nan")
        return month_df


class YFinanceDataFetcher(BaseDataFetcher):
    """
    使用 yfinance 抓取台股歷史資料

    注意：yfinance 實質上是在抓取 Yahoo Finance 網頁/API，從雲端主機
    （Render、AWS等資料中心IP）呼叫時，常會遇到 Yahoo 的反爬蟲機制
    導致請求被拒或回傳空結果。正式部署建議改用 TWSEDataFetcher；
    這個類別保留供本機開發、或未來需要查詢非台股商品時使用
    """

    def __init__(self, market_suffix: str = ".TW"):
        # 上市股票後綴為 .TW；上櫃股票請改為 .TWO
        self._suffix = market_suffix

    def fetch_daily_ohlcv(
        self,
        stock_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        import yfinance as yf

        if end_date is None:
            end_date = date.today()
        if start_date is None:
            # 預設抓取兩年資料，足夠計算月線、週線指標
            start_date = end_date - timedelta(days=365 * 2)

        ticker = f"{stock_code}{self._suffix}"
        raw_df = yf.download(ticker, start=start_date, end=end_date, progress=False)

        if raw_df.empty:
            raise ValueError(f"查無股票代碼 {stock_code} 的歷史資料")

        raw_df = raw_df.rename(
            columns={
                "Open": "open",
                "High": "high",
                "Low": "low",
                "Close": "close",
                "Volume": "volume",
            }
        )
        raw_df.index.name = "date"
        return raw_df[["open", "high", "low", "close", "volume"]]


class StockDataService:
    """
    Data 模組對外的主要服務介面
    整合資料抓取與週期轉換（日線 → 週線 → 月線）
    """

    _RESAMPLE_RULE = {
        "open": "first",
        "high": "max",
        "low": "min",
        "close": "last",
        "volume": "sum",
    }

    def __init__(self, fetcher: Optional[BaseDataFetcher] = None):
        self._fetcher = fetcher or TWSEDataFetcher()

    def get_daily_data(
        self,
        stock_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> pd.DataFrame:
        """取得日線資料"""
        return self._fetcher.fetch_daily_ohlcv(stock_code, start_date, end_date)

    @classmethod
    def resample_to_weekly(cls, daily_df: pd.DataFrame) -> pd.DataFrame:
        """將日線資料轉換為週線資料（以週五為週期結算日）"""
        return daily_df.resample("W-FRI").agg(cls._RESAMPLE_RULE).dropna()

    @classmethod
    def resample_to_monthly(cls, daily_df: pd.DataFrame) -> pd.DataFrame:
        """將日線資料轉換為月線資料（以月底為週期結算日）"""
        return daily_df.resample("ME").agg(cls._RESAMPLE_RULE).dropna()

    def get_multi_timeframe_data(
        self,
        stock_code: str,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
    ) -> dict:
        """
        一次取得日／週／月三種週期的資料
        回傳格式：{"daily": df, "weekly": df, "monthly": df}
        """
        daily_df = self.get_daily_data(stock_code, start_date, end_date)
        return {
            "daily": daily_df,
            "weekly": self.resample_to_weekly(daily_df),
            "monthly": self.resample_to_monthly(daily_df),
        }
