"""
應用程式全域設定
"""
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """集中管理服務的各項參數，方便日後調整"""

    app_name: str = "台股波段分析 API"
    app_version: str = "0.1.0"

    # 資料來源設定："twse"（台灣證交所官方資料，建議）或 "yfinance"
    data_source: str = "twse"

    # 三層濾網共用的指標參數
    ma_period: int = 20
    macd_fast: int = 12
    macd_slow: int = 26
    macd_signal: int = 9
    bollinger_period: int = 20
    bollinger_std: float = 2.0

    class Config:
        env_file = ".env"


settings = Settings()
