# 如何讓手機「真正」安裝這個 App

這個專案現在同時是：
- 一個 JSON API（`/api/v1/analysis/...`）
- 一個手機可安裝的 PWA 前端（網址根目錄 `/`），兩者由同一個 FastAPI 服務一起提供

**重點提醒**：PWA 要能在手機上「安裝」，瀏覽器要求網站必須跑在 **HTTPS**（或 `localhost`）底下，單純用區域網路 IP（例如 `http://192.168.1.5:8000`）開啟雖然網頁能看，但 Service Worker 不會註冊，無法真正「安裝」。所以你需要先把這個服務放到一個有 HTTPS 的地方。

## 方法一：部署到雲端（建議，長期使用）

專案已附上 `Dockerfile`，大部分平台都能直接用它部署，以下以 Render 為例（其他如 Railway、Fly.io 流程也類似）：

1. 把這個專案推到一個 GitHub repo
2. 到 [render.com](https://render.com) 建立帳號 → New → Web Service → 選擇剛剛的 repo
3. Render 偵測到 `Dockerfile` 後會自動用它建置，不需要額外設定（免費方案即可）
4. 部署完成後會拿到一個 `https://xxx.onrender.com` 的網址 — 這就是你的 App 網址

> 免費方案通常會在閒置一段時間後休眠，第一次連線會比較慢，這是正常現象。

## 方法二：先在自己電腦上快速試用（不必部署，幾分鐘搞定）

如果只是想先在手機上看看效果，不用真的部署，可以在你自己電腦上跑起來，再用一個免費的 HTTPS 通道工具暫時把它「借」一個 HTTPS 網址：

```bash
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000
```

然後另開一個終端機，用 [ngrok](https://ngrok.com)（或 Cloudflare Tunnel）：

```bash
ngrok http 8000
```

ngrok 會給你一個類似 `https://xxxx.ngrok-free.app` 的網址，這個網址有 HTTPS，可以直接在手機上打開測試安裝（缺點是免費版網址每次重啟都會換，僅適合測試用）。

## 把它「安裝」到手機

用手機瀏覽器打開上面拿到的 HTTPS 網址後：

- **Android（Chrome）**：畫面下方會自動跳出「加入主畫面」的提示，點一下即可；或從瀏覽器選單選「安裝應用程式」
- **iPhone（Safari）**：點底部分享圖示 → 往下找「加入主畫面」

安裝後手機桌面會出現「台股波段濾網」的圖示，點開會以全螢幕App的方式啟動，不會看到瀏覽器網址列。

## 前後端分開部署的情況

如果你之後想把前端（webapp/ 目錄）和後端（API）分開部署在不同網域，打開 App 後點右上角齒輪圖示，在「API 位址」填入後端的網址即可，設定會存在手機瀏覽器的 localStorage，重開 App 仍會記得。同網域部署（本文件介紹的方式）則完全不用設定。
