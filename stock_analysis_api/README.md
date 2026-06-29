# 台股波段分析 API

基於 FastAPI 打造的台股技術分析服務，依照「三層濾網」原則
（月線趨勢 → 週線趨勢 → 日線型態確認）判斷個股是否符合高勝率波段買進條件。

## 專案結構

```
stock_analysis_api/
├── main.py                      # FastAPI 進入點（同時提供 API 與 PWA 靜態網頁）
├── config.py                    # 全域設定
├── requirements.txt             # 套件相依清單
├── Dockerfile                   # 容器化部署設定
├── DEPLOY.md                    # 如何讓手機真正安裝這個App（部署教學）
├── schemas/
│   └── response_schemas.py      # API 請求／回應資料結構
├── modules/
│   ├── data_module.py           # Data 模組：抓取與轉換歷史資料
│   ├── indicators_module.py     # Indicators 模組：技術指標計算
│   └── logic_module.py          # Logic 模組：三層濾網判斷邏輯
├── routers/
│   └── analysis_router.py       # API 路由，串接以上三個模組
├── webapp/                      # 手機可安裝的 PWA 前端（與 API 同服務、同網域）
│   ├── index.html / styles.css / app.js
│   ├── manifest.webmanifest     # PWA 安裝資訊
│   ├── service-worker.js        # 離線快取／可安裝性
│   └── icons/                   # App 圖示
└── tests/                       # 單元測試（見 tests/TEST_REPORT.md）
```

## 手機安裝（PWA）

`webapp/` 是一個手機可安裝的 PWA，與 API 一起由 `main.py` 提供，部署到任何支援 HTTPS 的主機後，用手機瀏覽器打開即可「加入主畫面」安裝，使用體驗如同原生 App。完整部署步驟見 **`DEPLOY.md`**。

## 三層濾網設計理念

1. **第一層／月線趨勢**：確認長期大趨勢方向，只在多方格局下尋找買點
2. **第二層／週線趨勢**：在月線方向一致下，確認中期動能是否轉強
3. **第三層／日線型態確認**：以日線型態尋找最終進場時機

三層全數通過，才視為高勝率波段買進訊號；任何一層未通過，即不成立。

## 安裝方式

```bash
pip install -r requirements.txt
```

## 啟動服務

```bash
uvicorn main:app --reload
```

啟動後：
- 開啟 http://127.0.0.1:8000 可看到手機 PWA 前端介面
- 開啟 http://127.0.0.1:8000/docs 查看互動式 API 文件並直接測試

## 主要端點

- `GET /api/v1/analysis/triple-screen/{stock_code}`
  對指定股票代碼執行三層濾網分析，回傳月／週／日各層的判斷結果與最終買進訊號
- `GET /api/v1/analysis/raw-data/{stock_code}?timeframe=daily`
  取得指定股票、指定週期（daily／weekly／monthly）的原始歷史資料，方便除錯與檢視
- `GET /healthz`
  系統健康檢查

## 注意事項

- 預設資料來源為 `yfinance`：上市股票代碼後綴為 `.TW`，
  上櫃股票請將 `YFinanceDataFetcher` 的 `market_suffix` 參數改為 `.TWO`
- `logic_module.py` 中各層的判斷條件目前僅為範例邏輯，
  建議依個人交易策略調整門檻數值與條件組合
- 本服務僅供技術分析架構參考，不構成任何投資建議
