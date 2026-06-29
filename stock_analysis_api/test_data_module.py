"""
Data 模組單元測試

測試重點：邊界條件 -- 整週/整月資料缺失（空值）、成交量為 0 時的週期轉換行為
"""
import numpy as np
import pandas as pd
import pytest

from modules.data_module import BaseDataFetcher, StockDataService, TWSEDataFetcher


class _FakeFetcher(BaseDataFetcher):
    """測試用假資料來源，不需要連線網路即可驗證 StockDataService 的邏輯"""

    def __init__(self, df: pd.DataFrame):
        self._df = df

    def fetch_daily_ohlcv(self, stock_code, start_date=None, end_date=None):
        return self._df


class TestTWSEDataFetcherParsing:
    """
    TWSEDataFetcher 的解析邏輯測試（不連線真實網路）

    使用與台灣證交所 STOCK_DAY 端點相同格式的模擬回應，
    驗證民國年轉換、千分位逗號清除等格式轉換是否正確
    """

    SAMPLE_PAYLOAD = {
        "stat": "OK",
        "date": "20240601",
        "title": "113年06月 2330 台積電 各日成交資訊",
        "fields": ["日期", "成交股數", "成交金額", "開盤價", "最高價", "最低價", "收盤價", "漲跌價差", "成交筆數"],
        "data": [
            ["113/06/03", "36,322,931", "31,234,123,456", "855.00", "860.00", "850.00", "858.00", "+5.00", "18,234"],
            ["113/06/04", "28,150,000", "24,500,000,000", "858.00", "865.00", "856.00", "862.00", "+4.00", "15,920"],
        ],
    }

    def test_parses_roc_date_to_gregorian(self):
        """民國年日期（113/06/03）應正確轉換為西元年（2024-06-03）"""
        df = TWSEDataFetcher._parse_month_payload(self.SAMPLE_PAYLOAD)
        assert pd.Timestamp("2024-06-03") in df.index
        assert pd.Timestamp("2024-06-04") in df.index

    def test_strips_thousands_separator_commas(self):
        """數值欄位的千分位逗號（例如 "36,322,931"）應正確轉為浮點數，而非字串或NaN"""
        df = TWSEDataFetcher._parse_month_payload(self.SAMPLE_PAYLOAD)
        row = df.loc["2024-06-03"]
        assert row["volume"] == 36_322_931
        assert row["close"] == 858.00
        assert row["open"] == 855.00

    def test_missing_required_fields_returns_none(self):
        """若回應中缺少日期或收盤價欄位，應安全回傳 None 而不是拋出例外"""
        broken_payload = {
            "fields": ["開盤價", "最高價"],
            "data": [["855.00", "860.00"]],
        }
        assert TWSEDataFetcher._parse_month_payload(broken_payload) is None

    def test_malformed_row_is_skipped_not_raised(self):
        """格式異常的單列資料（例如日期格式跑掉）應被跳過，而不是讓整批解析失敗"""
        payload = {
            "fields": self.SAMPLE_PAYLOAD["fields"],
            "data": [
                ["格式錯誤的日期", "1", "1", "1", "1", "1", "1", "1", "1"],
                ["113/06/03", "36,322,931", "31,234,123,456", "855.00", "860.00", "850.00", "858.00", "+5.00", "18,234"],
            ],
        }
        df = TWSEDataFetcher._parse_month_payload(payload)
        assert len(df) == 1  # 異常列被跳過，正常列仍然保留

    def test_month_range_covers_inclusive_span(self):
        """月份清單應包含起訖月份本身，且依序遞增（用於決定要呼叫TWSE幾次）"""
        months = TWSEDataFetcher._month_range(
            pd.Timestamp("2024-11-15").date(), pd.Timestamp("2025-02-03").date()
        )
        assert months == [
            pd.Timestamp("2024-11-01").date(),
            pd.Timestamp("2024-12-01").date(),
            pd.Timestamp("2025-01-01").date(),
            pd.Timestamp("2025-02-01").date(),
        ]

    def test_fetch_daily_ohlcv_concatenates_months_without_real_network(self, monkeypatch):
        """模擬兩個月份的回應，驗證 fetch_daily_ohlcv 會正確串接並依日期區間篩選"""
        import requests

        payload_a = {
            "fields": self.SAMPLE_PAYLOAD["fields"],
            "data": [
                ["113/05/30", "1,000", "1", "850.00", "852.00", "848.00", "851.00", "+1.00", "100"],
            ],
            "stat": "OK",
        }
        payload_b = self.SAMPLE_PAYLOAD

        def fake_get(self, url, params=None, timeout=None):
            month = params["date"][:6]  # YYYYMM
            body = payload_a if month == "202405" else payload_b
            return _FakeResponse(body)

        monkeypatch.setattr(requests.Session, "get", fake_get)

        fetcher = TWSEDataFetcher()
        df = fetcher.fetch_daily_ohlcv(
            "2330",
            start_date=pd.Timestamp("2024-05-30").date(),
            end_date=pd.Timestamp("2024-06-04").date(),
        )

        assert list(df.index.strftime("%Y-%m-%d")) == ["2024-05-30", "2024-06-03", "2024-06-04"]
        assert df.loc["2024-06-03", "close"] == 858.00

    def test_fetch_daily_ohlcv_raises_value_error_when_stock_not_found(self, monkeypatch):
        """所有月份皆查無資料時（例如代碼打錯），應拋出ValueError而非靜默回傳空結果"""
        import requests

        def fake_get(self, url, params=None, timeout=None):
            return _FakeResponse({"stat": "查無此資料", "data": []})

        monkeypatch.setattr(requests.Session, "get", fake_get)

        fetcher = TWSEDataFetcher()
        with pytest.raises(ValueError, match="查無股票代碼"):
            fetcher.fetch_daily_ohlcv(
                "9999",
                start_date=pd.Timestamp("2024-06-01").date(),
                end_date=pd.Timestamp("2024-06-30").date(),
            )


class _FakeResponse:
    """模擬 requests.Response，僅提供測試會用到的最小介面"""

    def __init__(self, json_body: dict, status_code: int = 200):
        self._json_body = json_body
        self.status_code = status_code

    def raise_for_status(self):
        pass

    def json(self):
        return self._json_body


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
