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


class YFinanceDataFetcher(BaseDataFetcher):
    """使用 yfinance 抓取台股歷史資料"""

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
        self._fetcher = fetcher or YFinanceDataFetcher()

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
