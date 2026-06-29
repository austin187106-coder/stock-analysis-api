"""
Logic 模組單元測試

測試重點：
1. 邏輯覆蓋 -- 三種情境下的買進訊號判斷是否如預期
   (a) 完全符合買進條件
   (b) 週線向上但日線未突破
   (c) 布林通道未開口（緊縮）
2. 邊界條件 -- 指標為 NaN 或欄位缺失時，是否安全降級為「不通過」而非拋出例外
"""
import pytest

from modules.logic_module import TripleScreenLogic


@pytest.fixture
def logic():
    return TripleScreenLogic(ma_period=20)


class TestLogicCoverage:
    """三層濾網的邏輯覆蓋測試"""

    def test_scenario_full_buy_signal(self, logic, make_layer_snapshot):
        """情境一：月線、週線、日線皆符合多方條件，應觸發買進訊號"""
        monthly_df = make_layer_snapshot([
            {"close": 100.0, "ma20": 95.0, "macd_hist": 0.5},
        ])
        weekly_df = make_layer_snapshot([
            {"close": 105.0, "ma20": 100.0, "bb_mid": 100.0},
        ])
        daily_df = make_layer_snapshot([
            {"close": 103.0, "bb_mid": 100.0, "bb_upper": 110.0},  # 前一日
            {"close": 106.0, "bb_mid": 101.0, "bb_upper": 111.0},  # 當日
        ])

        result = logic.evaluate(monthly_df, weekly_df, daily_df)

        assert result.monthly.passed is True
        assert result.weekly.passed is True
        assert result.daily.passed is True
        assert result.is_buy_signal is True

    def test_scenario_weekly_up_but_daily_not_breakout(self, logic, make_layer_snapshot):
        """情境二：週線向上，但日線當天回落、未站上布林中軌，不應觸發買進訊號"""
        monthly_df = make_layer_snapshot([
            {"close": 100.0, "ma20": 95.0, "macd_hist": 0.5},
        ])
        weekly_df = make_layer_snapshot([
            {"close": 105.0, "ma20": 100.0, "bb_mid": 100.0},  # 週線站上均線，趨勢向上
        ])
        daily_df = make_layer_snapshot([
            {"close": 103.0, "bb_mid": 101.0, "bb_upper": 110.0},  # 前一日
            {"close": 99.0, "bb_mid": 101.0, "bb_upper": 110.0},   # 當日回落，跌破中軌
        ])

        result = logic.evaluate(monthly_df, weekly_df, daily_df)

        assert result.weekly.passed is True
        assert result.weekly.trend == "多方"
        assert result.daily.passed is False
        assert result.is_buy_signal is False
        assert "日線" in result.summary

    def test_scenario_bollinger_bands_not_expanded(self, logic, make_layer_snapshot):
        """
        情境三：布林通道緊縮未開口（低波動盤整期）

        本測試刻意建構通道寬度極窄（小於中軌價格的2%）、僅有微幅價格波動的場景，
        用以驗證目前架構在此情境下的「實際行為」。
        ⚠️ 測試結果顯示此為已知架構限制，詳細風險說明請見測試報告。
        """
        monthly_df = make_layer_snapshot([
            {"close": 100.0, "ma20": 95.0, "macd_hist": 0.5},
        ])
        weekly_df = make_layer_snapshot([
            {"close": 105.0, "ma20": 100.0, "bb_mid": 100.0},
        ])

        bb_mid, bb_upper, bb_lower = 100.0, 100.5, 99.5
        bandwidth_pct = (bb_upper - bb_lower) / bb_mid
        assert bandwidth_pct < 0.02, "測試情境設計應為通道寬度低於2%的緊縮狀態"

        daily_df = make_layer_snapshot([
            {"close": 100.1, "bb_mid": bb_mid, "bb_upper": bb_upper},
            {"close": 100.3, "bb_mid": bb_mid, "bb_upper": bb_upper},
        ])

        result = logic.evaluate(monthly_df, weekly_df, daily_df)

        # 目前 Logic 模組未檢查布林通道寬度（頻寬），
        # 在通道緊縮、僅有微幅價格波動時，第三層仍會判定為通過。
        # 此處斷言反映「目前實際行為」，建議事項請見測試報告。
        assert result.daily.passed is True
        assert result.is_buy_signal is True


class TestBoundaryConditions:
    """指標數值缺失（NaN）或欄位不存在時的邊界處理"""

    def test_nan_ma_in_monthly_layer_fails_safely(self, logic, make_layer_snapshot):
        """月線20MA為NaN（例如資料不足）時，不應拋出例外，應安全判定為不通過"""
        monthly_df = make_layer_snapshot([
            {"close": 100.0, "ma20": float("nan"), "macd_hist": 0.5},
        ])
        weekly_df = make_layer_snapshot([
            {"close": 105.0, "ma20": 100.0, "bb_mid": 100.0},
        ])
        daily_df = make_layer_snapshot([
            {"close": 103.0, "bb_mid": 100.0, "bb_upper": 110.0},
            {"close": 106.0, "bb_mid": 101.0, "bb_upper": 111.0},
        ])

        result = logic.evaluate(monthly_df, weekly_df, daily_df)

        assert result.monthly.passed is False
        assert result.is_buy_signal is False

    def test_nan_bollinger_in_daily_layer_fails_safely(self, logic, make_layer_snapshot):
        """日線布林中軌／上緣為NaN時，不應拋出例外，應安全判定為不通過"""
        monthly_df = make_layer_snapshot([
            {"close": 100.0, "ma20": 95.0, "macd_hist": 0.5},
        ])
        weekly_df = make_layer_snapshot([
            {"close": 105.0, "ma20": 100.0, "bb_mid": 100.0},
        ])
        daily_df = make_layer_snapshot([
            {"close": 103.0, "bb_mid": float("nan"), "bb_upper": float("nan")},
            {"close": 106.0, "bb_mid": float("nan"), "bb_upper": float("nan")},
        ])

        result = logic.evaluate(monthly_df, weekly_df, daily_df)

        assert result.daily.passed is False
        assert result.is_buy_signal is False

    def test_missing_indicator_columns_use_safe_default(self, logic, make_layer_snapshot):
        """完全沒有指標欄位時（例如尚未呼叫Indicators模組），應安全判定不通過而非拋出例外"""
        monthly_df = make_layer_snapshot([{"close": 100.0}])
        weekly_df = make_layer_snapshot([{"close": 105.0}])
        daily_df = make_layer_snapshot([
            {"close": 103.0},
            {"close": 106.0},
        ])

        result = logic.evaluate(monthly_df, weekly_df, daily_df)

        assert result.is_buy_signal is False
