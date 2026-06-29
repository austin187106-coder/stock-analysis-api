"""
API 請求／回應的資料結構定義（Pydantic Models）
"""
from datetime import date
from typing import Optional

from pydantic import BaseModel, Field


class StockQueryRequest(BaseModel):
    """股票查詢請求"""

    stock_code: str = Field(..., description="股票代碼，例如 2330")
    start_date: Optional[date] = Field(None, description="起始日期")
    end_date: Optional[date] = Field(None, description="結束日期")


class FilterLayerResult(BaseModel):
    """單一層濾網的判斷結果"""

    passed: bool = Field(..., description="是否通過該層濾網")
    trend: str = Field(..., description="趨勢方向：多方／空方／盤整")
    detail: str = Field(..., description="判斷依據說明")


class TripleScreenResult(BaseModel):
    """三層濾網綜合判斷結果"""

    stock_code: str
    analysis_date: date
    monthly_layer: FilterLayerResult
    weekly_layer: FilterLayerResult
    daily_layer: FilterLayerResult
    is_buy_signal: bool = Field(..., description="是否符合高勝率波段買進條件")
    summary: str = Field(..., description="綜合結論")


class IndicatorSnapshot(BaseModel):
    """單一交易日的技術指標快照（保留供未來擴充使用）"""

    date: date
    close: float
    ma: Optional[float] = None
    macd: Optional[float] = None
    macd_signal: Optional[float] = None
    macd_hist: Optional[float] = None
    bb_upper: Optional[float] = None
    bb_mid: Optional[float] = None
    bb_lower: Optional[float] = None
