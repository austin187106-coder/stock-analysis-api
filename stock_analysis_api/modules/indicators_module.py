"""
Indicators 模組
使用 pandas_ta 計算技術指標：20MA、MACD、布林通道
可套用在日線、週線、月線等任意週期的資料上
"""
from typing import Optional

import pandas as pd
import pandas_ta as ta


class TechnicalIndicatorService:
    """技術指標計算服務"""

    def __init__(
        self,
        ma_period: int = 20,
        macd_fast: int = 12,
        macd_slow: int = 26,
        macd_signal: int = 9,
        bb_period: int = 20,
        bb_std: float = 2.0,
    ):
        self.ma_period = ma_period
        self.macd_fast = macd_fast
        self.macd_slow = macd_slow
        self.macd_signal = macd_signal
        self.bb_period = bb_period
        self.bb_std = bb_std

    def add_moving_average(
        self, df: pd.DataFrame, period: Optional[int] = None
    ) -> pd.DataFrame:
        """
        計算移動平均線
        套用在週線資料時即為「週線20MA」，新增欄位名稱為 ma{period}

        若資料筆數不足以計算該週期（pandas_ta 會回傳 None），
        則該欄位以 NaN 填入，不中斷後續流程
        """
        period = period or self.ma_period
        result_df = df.copy()
        sma_series = ta.sma(result_df["close"], length=period)
        result_df[f"ma{period}"] = sma_series if sma_series is not None else float("nan")
        return result_df

    def add_macd(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        計算 MACD 指標
        新增欄位：macd（DIF）、macd_signal（訊號線）、macd_hist（柱狀體）

        若資料筆數不足（pandas_ta 回傳 None），三個欄位皆以 NaN 填入
        """
        result_df = df.copy()
        macd_df = ta.macd(
            result_df["close"],
            fast=self.macd_fast,
            slow=self.macd_slow,
            signal=self.macd_signal,
        )

        if macd_df is None:
            result_df["macd"] = float("nan")
            result_df["macd_hist"] = float("nan")
            result_df["macd_signal"] = float("nan")
            return result_df

        # pandas_ta 不同版本回傳的欄位順序可能不同，以欄位名稱關鍵字判斷較為穩健
        macd_col = next(c for c in macd_df.columns if c.startswith("MACD_"))
        hist_col = next(c for c in macd_df.columns if c.startswith("MACDh"))
        signal_col = next(c for c in macd_df.columns if c.startswith("MACDs"))

        result_df["macd"] = macd_df[macd_col]
        result_df["macd_hist"] = macd_df[hist_col]
        result_df["macd_signal"] = macd_df[signal_col]
        return result_df

    def add_bollinger_bands(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        計算布林通道
        新增欄位：bb_upper（上緣）、bb_mid（中軌）、bb_lower（下緣）

        若資料筆數不足（pandas_ta 回傳 None），三個欄位皆以 NaN 填入
        """
        result_df = df.copy()
        bb_df = ta.bbands(
            result_df["close"],
            length=self.bb_period,
            lower_std=self.bb_std,
            upper_std=self.bb_std,
        )

        if bb_df is None:
            result_df["bb_lower"] = float("nan")
            result_df["bb_mid"] = float("nan")
            result_df["bb_upper"] = float("nan")
            return result_df

        lower_col = next(c for c in bb_df.columns if c.startswith("BBL"))
        mid_col = next(c for c in bb_df.columns if c.startswith("BBM"))
        upper_col = next(c for c in bb_df.columns if c.startswith("BBU"))

        result_df["bb_lower"] = bb_df[lower_col]
        result_df["bb_mid"] = bb_df[mid_col]
        result_df["bb_upper"] = bb_df[upper_col]
        return result_df

    def calculate_all(self, df: pd.DataFrame) -> pd.DataFrame:
        """一次計算所有指標：20MA、MACD、布林通道"""
        result_df = self.add_moving_average(df)
        result_df = self.add_macd(result_df)
        result_df = self.add_bollinger_bands(result_df)
        return result_df
