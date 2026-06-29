"""
Data 模組單元測試

測試重點：邊界條件 -- 整週/整月資料缺失（空值）、成交量為 0 時的週期轉換行為
"""
import numpy as np
import pandas as pd
import pytest

from modules.data_module import BaseDataFetcher, StockDataService


class _FakeFetcher(BaseDataFetcher):
    """測試用假資料來源，不需要連線網路即可驗證 StockDataService 的邏輯"""

    def __init__(self, df: pd.DataFrame):
        self._df = df

    def fetch_daily_ohlcv(self, stock_code, start_date=None, end_date=None):
        return self._df


class TestResampleBoundaryConditions:
    """日線轉週線／月線時的邊界條件"""

    def test_weekly_resample_basic_aggregation(self, make_ohlcv):
        """基本週期轉換：open取首筆、close取末筆、high/low取極值、volume加總"""
        df = make_ohlcv(
            {
                "close": [10.0, 11.0, 12.0, 13.0, 14.0],
                "volume": [100, 100, 100, 100, 100],
            },
            start="2025-01-06",  # 星期一，確保5個交易日落在同一週（週五結算）
        )
        weekly = StockDataService.resample_to_weekly(df)

        assert len(weekly) == 1
        row = weekly.iloc[0]
        assert row["open"] == 10.0
        assert row["close"] == 14.0
        assert row["high"] == 14.0
        assert row["low"] == 10.0
        assert row["volume"] == 500

    def test_entirely_missing_period_is_dropped(self, make_ohlcv):
        """若某週收盤價全數缺失（NaN），該週應從結果中被剔除，而不是以NaN殘留"""
        close = [10, 11, 12, 13, 14, 15, 16] + [np.nan] * 7
        df = make_ohlcv({"close": close, "volume": [100] * 14})

        weekly = StockDataService.resample_to_weekly(df)

        assert weekly["close"].isna().sum() == 0
        assert len(weekly) == 2  # 第三週(僅剩2天且全缺值)應被剔除，不殘留NaN列

    def test_zero_volume_week_sums_to_zero(self, make_ohlcv):
        """整週成交量皆為0時，加總後應為0，而非NaN或錯誤"""
        df = make_ohlcv({
            "close": [10.0, 11.0, 12.0, 13.0, 14.0],
            "volume": [0, 0, 0, 0, 0],
        })
        weekly = StockDataService.resample_to_weekly(df)
        assert weekly.iloc[0]["volume"] == 0

    def test_partial_missing_volume_sums_ignore_nan(self, make_ohlcv):
        """部分成交量缺值時加總應忽略NaN，而不是讓整週結果變成NaN"""
        df = make_ohlcv(
            {
                "close": [10.0, 11.0, 12.0, 13.0, 14.0],
                "volume": [100, np.nan, 100, 0, 100],
            },
            start="2025-01-06",  # 星期一，確保5個交易日落在同一週
        )
        weekly = StockDataService.resample_to_weekly(df)
        assert weekly.iloc[0]["volume"] == 300

    def test_multi_timeframe_data_lengths_are_consistent(self, make_ohlcv):
        """月線資料筆數應少於週線，週線應少於日線（資料壓縮關係應成立）"""
        np.random.seed(0)
        n = 90
        close = (100 + np.cumsum(np.random.randn(n))).tolist()
        df = make_ohlcv({"close": close, "volume": [1000] * n})

        weekly = StockDataService.resample_to_weekly(df)
        monthly = StockDataService.resample_to_monthly(df)

        assert len(weekly) < len(df)
        assert len(monthly) < len(weekly)


class TestDependencyInjection:
    """StockDataService 應可透過抽象介面替換資料來源，不應綁定 yfinance"""

    def test_get_multi_timeframe_data_uses_injected_fetcher(self, make_ohlcv):
        """注入假資料來源後，應能正常產生日／週／月三種週期的資料"""
        df = make_ohlcv({
            "close": list(range(10, 10 + 30)),
            "volume": [1000] * 30,
        })
        service = StockDataService(fetcher=_FakeFetcher(df))

        result = service.get_multi_timeframe_data("0000")

        assert set(result.keys()) == {"daily", "weekly", "monthly"}
        assert len(result["daily"]) == 30
        assert len(result["weekly"]) > 0
        assert len(result["monthly"]) > 0
