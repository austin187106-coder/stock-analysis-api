"""
測試共用的 fixtures 與資料工廠函式
"""
import sys
from pathlib import Path

# 確保專案根目錄在 sys.path 中，讓 modules / schemas / routers 可以被正確匯入
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

import pandas as pd
import pytest


def _make_ohlcv(rows: dict, freq: str = "D", start: str = "2025-01-01") -> pd.DataFrame:
    """
    依據給定的欄位字典建立測試用 OHLCV DataFrame
    範例：{"close": [10, 11, 12], "volume": [100, 100, 100]}
    缺少的 open/high/low 欄位會自動以 close 補上；缺少 volume 則預設為 1000

    start 預設為 2025-01-01（星期三）；若測試需要與週線（週五結算）邊界對齊，
    可傳入星期一的日期，確保連續N個交易日落在同一週期內
    """
    length = len(next(iter(rows.values())))
    df = pd.DataFrame(rows)
    for col in ("open", "high", "low"):
        if col not in df.columns:
            df[col] = df["close"] if "close" in df.columns else 0.0
    if "volume" not in df.columns:
        df["volume"] = 1000
    df.index = pd.date_range(start, periods=length, freq=freq)
    df.index.name = "date"
    return df[["open", "high", "low", "close", "volume"]]


def _make_layer_snapshot(rows: list) -> pd.DataFrame:
    """
    建立 Logic 模組測試用的「已含指標」資料列
    rows 為字典列表，每個字典代表一個交易週期的收盤價與指標數值
    """
    df = pd.DataFrame(rows)
    df.index = pd.date_range("2025-01-01", periods=len(df), freq="D")
    df.index.name = "date"
    return df


@pytest.fixture
def make_ohlcv():
    """回傳一個可建立測試用 OHLCV DataFrame 的工廠函式"""
    return _make_ohlcv


@pytest.fixture
def make_layer_snapshot():
    """回傳一個可建立 Logic 模組測試用資料列的工廠函式"""
    return _make_layer_snapshot
