"""
Logic 模組
依據「三層濾網」原則（月線趨勢 → 週線趨勢 → 日線型態確認）
判斷個股是否符合高勝率波段買進條件
"""
from dataclasses import dataclass

import pandas as pd


@dataclass
class FilterResult:
    """單一層濾網的判斷結果"""

    passed: bool
    trend: str  # "多方" / "空方" / "盤整"
    detail: str


@dataclass
class TripleScreenResult:
    """三層濾網綜合判斷結果"""

    monthly: FilterResult
    weekly: FilterResult
    daily: FilterResult
    is_buy_signal: bool
    summary: str


class TripleScreenLogic:
    """
    三層濾網判斷邏輯

    第一層（月線，長期趨勢濾網）：
        判斷大趨勢方向，僅在多方趨勢中尋找買進機會

    第二層（週線，中期動能濾網）：
        在月線趨勢方向一致下，確認週線動能是否轉強

    第三層（日線，短期進場確認）：
        在前兩層皆成立後，以日線型態確認最終進場時機

    以下各層條件僅為範例邏輯，建議依個人交易策略調整門檻與組合方式
    """

    def __init__(self, ma_period: int = 20):
        self.ma_period = ma_period

    def check_monthly_layer(self, monthly_df: pd.DataFrame) -> FilterResult:
        """
        第一層：月線趨勢濾網
        範例條件：收盤價站上月線20MA，且MACD柱狀體為正（多方動能）
        """
        latest = monthly_df.iloc[-1]
        ma_col = f"ma{self.ma_period}"

        above_ma = bool(latest["close"] > latest.get(ma_col, float("inf")))
        macd_positive = bool(latest.get("macd_hist", 0) > 0)
        passed = above_ma and macd_positive
        trend = "多方" if passed else ("盤整" if (above_ma or macd_positive) else "空方")

        detail = (
            f"收盤價 {latest['close']:.2f}，月線{self.ma_period}MA "
            f"{latest.get(ma_col, float('nan')):.2f}，"
            f"MACD柱狀體 {latest.get('macd_hist', float('nan')):.3f}"
        )
        return FilterResult(passed=passed, trend=trend, detail=detail)

    def check_weekly_layer(self, weekly_df: pd.DataFrame) -> FilterResult:
        """
        第二層：週線動能濾網
        範例條件：價格站上週線20MA，且未跌破布林中軌，
                  作為「順勢找買點」的依據
        """
        latest = weekly_df.iloc[-1]
        ma_col = f"ma{self.ma_period}"

        above_ma = bool(latest["close"] >= latest.get(ma_col, float("inf")))
        above_bb_mid = bool(latest["close"] >= latest.get("bb_mid", float("inf")))
        passed = above_ma and above_bb_mid
        trend = "多方" if passed else ("盤整" if (above_ma or above_bb_mid) else "空方")

        detail = (
            f"收盤價 {latest['close']:.2f}，週線{self.ma_period}MA "
            f"{latest.get(ma_col, float('nan')):.2f}，"
            f"布林中軌 {latest.get('bb_mid', float('nan')):.2f}"
        )
        return FilterResult(passed=passed, trend=trend, detail=detail)

    def check_daily_layer(self, daily_df: pd.DataFrame) -> FilterResult:
        """
        第三層：日線型態確認濾網
        範例條件：
        1. 站上布林中軌，且未觸及上緣（避免過度追高進場）
        2. 當日收盤價高於前一交易日收盤價（短線轉強訊號）
        """
        latest = daily_df.iloc[-1]
        prev = daily_df.iloc[-2]

        above_bb_mid = bool(latest["close"] >= latest.get("bb_mid", float("inf")))
        below_bb_upper = bool(latest["close"] <= latest.get("bb_upper", float("inf")))
        turning_up = bool(latest["close"] > prev["close"])
        passed = above_bb_mid and below_bb_upper and turning_up
        trend = "多方" if passed else "盤整"

        detail = (
            f"收盤價 {latest['close']:.2f}，布林中軌 "
            f"{latest.get('bb_mid', float('nan')):.2f}，"
            f"布林上緣 {latest.get('bb_upper', float('nan')):.2f}，"
            f"前一交易日收盤 {prev['close']:.2f}"
        )
        return FilterResult(passed=passed, trend=trend, detail=detail)

    def evaluate(
        self,
        monthly_df: pd.DataFrame,
        weekly_df: pd.DataFrame,
        daily_df: pd.DataFrame,
    ) -> TripleScreenResult:
        """
        綜合三層濾網的判斷結果
        三層皆通過，才視為高勝率波段買進訊號
        """
        monthly_result = self.check_monthly_layer(monthly_df)
        weekly_result = self.check_weekly_layer(weekly_df)
        daily_result = self.check_daily_layer(daily_df)

        is_buy_signal = (
            monthly_result.passed and weekly_result.passed and daily_result.passed
        )

        if is_buy_signal:
            summary = "三層濾網均通過，符合高勝率波段買進條件"
        else:
            failed_layers = [
                name
                for name, result in (
                    ("月線", monthly_result),
                    ("週線", weekly_result),
                    ("日線", daily_result),
                )
                if not result.passed
            ]
            summary = f"未符合買進條件，未通過：{'、'.join(failed_layers)}濾網"

        return TripleScreenResult(
            monthly=monthly_result,
            weekly=weekly_result,
            daily=daily_result,
            is_buy_signal=is_buy_signal,
            summary=summary,
        )
