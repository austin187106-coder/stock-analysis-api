"""
Indicators 模組單元測試

測試重點：
1. 參數正確性 -- 指標公式是否與標準定義
   （SMA20、MACD(12,26,9)、布林通道20期2倍標準差）完全吻合
2. 邊界條件 -- 資料筆數不足、close 含 NaN、volume 為 0、空 DataFrame
"""
import numpy as np
import pandas as pd
import pandas_ta as ta
import pytest

from modules.indicators_module import TechnicalIndicatorService


@pytest.fixture
def price_df(make_ohlcv):
    """60 筆模擬日線收盤價，足夠計算所有指標（含 MACD 慢線 26 期）"""
    np.random.seed(42)
    n = 60
    close = (100 + np.cumsum(np.random.randn(n))).tolist()
    return make_ohlcv({"close": close})


class TestParameterCorrectness:
    """參數正確性：確認指標計算公式與標準定義完全吻合"""

    def test_sma_matches_standard_definition(self, price_df):
        """20MA 應等於收盤價的 20 期簡單移動平均"""
        svc = TechnicalIndicatorService(ma_period=20)
        out = svc.add_moving_average(price_df)
        expected = price_df["close"].rolling(20).mean()
        assert np.allclose(out["ma20"].dropna(), expected.dropna(), atol=1e-9)

    def test_ma_period_parameter_takes_effect(self, price_df):
        """改變 ma_period 參數應實際改變視窗長度，10MA 不應等於 20MA"""
        out10 = TechnicalIndicatorService(ma_period=10).add_moving_average(price_df)
        out20 = TechnicalIndicatorService(ma_period=20).add_moving_average(price_df)
        assert "ma10" in out10.columns
        assert "ma20" in out20.columns
        assert not np.allclose(
            out10["ma10"].dropna().iloc[-10:],
            out20["ma20"].dropna().iloc[-10:],
        )

    def test_bollinger_bands_use_20_period_2_std(self, price_df):
        """
        布林通道應為：
        中軌 = 20期SMA；上下緣 = 中軌 +- 2倍20期標準差（樣本標準差 ddof=1）
        """
        svc = TechnicalIndicatorService(bb_period=20, bb_std=2.0)
        out = svc.add_bollinger_bands(price_df)

        sma20 = price_df["close"].rolling(20).mean()
        std20 = price_df["close"].rolling(20).std(ddof=1)

        assert np.allclose(out["bb_mid"].dropna(), sma20.dropna(), atol=1e-9)
        assert np.allclose(
            out["bb_upper"].dropna(), (sma20 + 2 * std20).dropna(), atol=1e-9
        )
        assert np.allclose(
            out["bb_lower"].dropna(), (sma20 - 2 * std20).dropna(), atol=1e-9
        )

    def test_bollinger_band_symmetry(self, price_df):
        """上緣到中軌、中軌到下緣的距離應完全對稱"""
        out = TechnicalIndicatorService().add_bollinger_bands(price_df)
        upper_gap = out["bb_upper"] - out["bb_mid"]
        lower_gap = out["bb_mid"] - out["bb_lower"]
        assert np.allclose(upper_gap.dropna(), lower_gap.dropna(), atol=1e-9)

    def test_bollinger_std_parameter_scales_bandwidth(self, price_df):
        """
        標準差倍數改變時，通道寬度應等比例縮放
        （此測試曾經抓出 bb_std 參數未實際生效的缺陷，詳見測試報告）
        """
        out1 = TechnicalIndicatorService(bb_std=1.0).add_bollinger_bands(price_df)
        out2 = TechnicalIndicatorService(bb_std=2.0).add_bollinger_bands(price_df)

        bandwidth1 = (out1["bb_upper"] - out1["bb_lower"]).dropna()
        bandwidth2 = (out2["bb_upper"] - out2["bb_lower"]).dropna()
        ratio = (bandwidth2 / bandwidth1).round(4)
        assert np.allclose(ratio, 2.0, atol=1e-3)

    def test_macd_equals_fast_ema_minus_slow_ema(self, price_df):
        """MACD 線應等於快線EMA(12) - 慢線EMA(26)（與函式庫自身的 ema() 交叉比對）"""
        out = TechnicalIndicatorService(
            macd_fast=12, macd_slow=26, macd_signal=9
        ).add_macd(price_df)

        ema_fast = ta.ema(price_df["close"], length=12)
        ema_slow = ta.ema(price_df["close"], length=26)
        expected_macd = ema_fast - ema_slow

        assert np.allclose(out["macd"].dropna(), expected_macd.dropna(), atol=1e-9)

    def test_macd_histogram_identity(self, price_df):
        """柱狀體必須恆等於 MACD線 - 訊號線（代數恆等式，與內部實作細節無關）"""
        out = TechnicalIndicatorService().add_macd(price_df)
        identity_diff = out["macd"] - out["macd_signal"] - out["macd_hist"]
        assert np.allclose(identity_diff.dropna(), 0.0, atol=1e-9)


class TestBoundaryConditions:
    """邊界條件：資料缺失（空值）、成交量為 0、資料筆數不足"""

    def test_missing_close_value_does_not_raise(self, price_df):
        """收盤價序列中間出現 NaN（資料缺失）不應造成例外"""
        df = price_df.copy()
        df.loc[df.index[20], "close"] = np.nan

        out = TechnicalIndicatorService().calculate_all(df)

        assert len(out) == len(df)
        # 缺值當天的指標應為 NaN，而不是沿用舊資料造成誤判
        assert pd.isna(out.loc[df.index[20], "ma20"])

    def test_zero_volume_does_not_affect_price_indicators(self, price_df):
        """成交量為 0 不應影響任何以收盤價為基礎的技術指標"""
        df_zero_volume = price_df.copy()
        df_zero_volume["volume"] = 0

        svc = TechnicalIndicatorService()
        out_with_volume = svc.calculate_all(price_df)
        out_zero_volume = svc.calculate_all(df_zero_volume)

        compare_cols = (
            "ma20", "macd", "macd_signal", "macd_hist",
            "bb_upper", "bb_mid", "bb_lower",
        )
        for col in compare_cols:
            assert np.allclose(
                out_with_volume[col].dropna(),
                out_zero_volume[col].dropna(),
                atol=1e-12,
            )

    def test_insufficient_rows_returns_nan_instead_of_crashing(self, make_ohlcv):
        """
        資料筆數不足以計算指標視窗時（例如只有 5 筆資料卻要算 20MA／MACD(12,26,9)），
        應安全回傳 NaN 欄位，而不是丟出例外
        """
        df = make_ohlcv({"close": [10.0, 11.0, 12.0, 13.0, 14.0]})
        out = TechnicalIndicatorService().calculate_all(df)

        assert len(out) == 5
        assert out["ma20"].isna().all()
        assert out["macd"].isna().all()
        assert out["macd_hist"].isna().all()
        assert out["bb_mid"].isna().all()

    def test_empty_dataframe_does_not_raise(self, make_ohlcv):
        """完全沒有資料時，應回傳空的 DataFrame 而不是拋出例外"""
        df = make_ohlcv({"close": []})
        out = TechnicalIndicatorService().calculate_all(df)
        assert out.empty
        assert "ma20" in out.columns
