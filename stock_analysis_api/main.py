"""
台股波段分析 API
進入點：建立並啟動 FastAPI 應用程式

本服務同時提供兩個角色：
1. JSON API（/api/v1/analysis/...），供前端或第三方系統呼叫
2. 手機可安裝的 PWA 前端（webapp/ 目錄），與 API 同網域、同一個服務一起部署，
   部署到任何支援 HTTPS 的主機後，手機瀏覽器開啟即可「加入主畫面」安裝
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from config import settings
from routers.analysis_router import router as analysis_router

WEBAPP_DIR = Path(__file__).resolve().parent / "webapp"

app = FastAPI(
    title=settings.app_name,
    version=settings.app_version,
    description="基於三層濾網原則（月線 → 週線 → 日線）的台股波段分析 API",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# API 路由必須在靜態網頁掛載之前註冊，確保 /api/v1/... 不會被靜態檔案攔截
app.include_router(analysis_router)


@app.get("/healthz", tags=["系統"])
def health_check() -> dict:
    """系統健康檢查"""
    return {"status": "ok", "service": settings.app_name}


# 掛載 PWA 靜態網頁：訪問網域根目錄會自動提供 webapp/index.html
# html=True 讓 StaticFiles 在路徑無對應檔案時自動回退到 index.html（單頁應用常見作法）
if WEBAPP_DIR.exists():
    app.mount("/", StaticFiles(directory=WEBAPP_DIR, html=True), name="webapp")
