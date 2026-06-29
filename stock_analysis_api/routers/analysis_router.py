"""
股票分析 API 路由
串接 Data、Indicators、Logic 三個模組，提供對外的 API 端點
"""
from datetime import date
from typing import Optional

from fastapi import APIRouter, HTTPException

from config import settings
from modules.data_module import StockDataService
from modules.indicators_module import TechnicalIndicatorService
from modules.logic_module import TripleScreenLogic
from schemas.response_schemas import FilterLayerResult, TripleScreenResult

router = APIRouter(prefix="/api/v1/analysis", tags=["波段分析"])

data_service = StockDataService()
indicator_service = TechnicalIndicatorService(
    ma_period=settings.ma_period,
    macd_fast=settings.macd_fast,
    macd_slow=settings.macd_slow,
    macd_signal=settings.macd_signal,
    bb_period=settings.bollinger_period,
    bb_std=settings.bollinger_std,
)
logic_service = TripleScreenLogic(ma_period=settings.ma_period)


@router.get("/triple-screen/{stock_code}", response_model=TripleScreenResult)
def analyze_triple_screen(
    stock_code: str,
    start_date: Optional[date] = None,
    end_date: Optional[date] = None,
) -> TripleScreenResult:
    """
    對指定股票代碼執行三層濾網分析

    流程：
    1. Data 模組：抓取日線資料，並轉換為週線、月線
    2. Indicators 模組：分別在三種週期計算技術指標
    3. Logic 模組：依三層濾網原則綜合判斷買進訊號
    """
    try:
        timeframes = data_service.get_multi_timeframe_data(
            stock_code, start_date, end_date
        )
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    monthly_df = indicator_service.calculate_all(timeframes["monthly"])
    weekly_df = indicator_service.calculate_all(timeframes["weekly"])
    daily_df = indicator_service.calculate_all(timeframes["daily"])

    result = logic_service.evaluate(
        monthly_df=monthly_df, weekly_df=weekly_df, daily_df=daily_df
    )

    return TripleScreenResult(
        stock_code=stock_code,
        analysis_date=date.today(),
        monthly_layer=FilterLayerResult(**result.monthly.__dict__),
        weekly_layer=FilterLayerResult(**result.weekly.__dict__),
        daily_layer=FilterLayerResult(**result.daily.__dict__),
        is_buy_signal=result.is_buy_signal,
        summary=result.summary,
    )


@router.get("/raw-data/{stock_code}")
def get_raw_data(stock_code: str, timeframe: str = "daily") -> list:
    """
    取得指定股票、指定週期的原始歷史資料（除錯與檢視用）
    timeframe 可選：daily、weekly、monthly
    """
    try:
        all_timeframes = data_service.get_multi_timeframe_data(stock_code)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    if timeframe not in all_timeframes:
        raise HTTPException(status_code=400, detail="timeframe 參數錯誤")

    df = all_timeframes[timeframe]
    return df.reset_index().to_dict(orient="records")
