"use strict";

const STORAGE_KEY = "stockTripleScreen.apiBaseUrl";

const els = {
  form: document.getElementById("queryForm"),
  input: document.getElementById("stockCode"),
  submitBtn: document.getElementById("submitBtn"),
  resultArea: document.getElementById("resultArea"),
  settingsBtn: document.getElementById("settingsBtn"),
  settingsSheet: document.getElementById("settingsSheet"),
  settingsBackdrop: document.getElementById("settingsBackdrop"),
  apiBaseUrlInput: document.getElementById("apiBaseUrl"),
  saveSettings: document.getElementById("saveSettings"),
  closeSettings: document.getElementById("closeSettings"),
  installToast: document.getElementById("installToast"),
  installToastText: document.getElementById("installToastText"),
  installToastClose: document.getElementById("installToastClose"),
};

const EMPTY_STATE_HTML = els.resultArea.innerHTML;

/* ---------------- 設定：API 位址（預設留空＝使用同網域相對路徑） ---------------- */

function getApiBaseUrl() {
  return (localStorage.getItem(STORAGE_KEY) || "").trim().replace(/\/+$/, "");
}

function openSettings() {
  els.apiBaseUrlInput.value = getApiBaseUrl();
  els.settingsBackdrop.hidden = false;
  els.settingsSheet.setAttribute("aria-hidden", "false");
  requestAnimationFrame(() => {
    els.settingsBackdrop.classList.add("show");
    els.settingsSheet.classList.add("show");
  });
}

function closeSettings() {
  els.settingsBackdrop.classList.remove("show");
  els.settingsSheet.classList.remove("show");
  els.settingsSheet.setAttribute("aria-hidden", "true");
  setTimeout(() => { els.settingsBackdrop.hidden = true; }, 220);
}

els.settingsBtn.addEventListener("click", openSettings);
els.closeSettings.addEventListener("click", closeSettings);
els.settingsBackdrop.addEventListener("click", closeSettings);
els.saveSettings.addEventListener("click", () => {
  const value = els.apiBaseUrlInput.value.trim();
  if (value) {
    localStorage.setItem(STORAGE_KEY, value);
  } else {
    localStorage.removeItem(STORAGE_KEY);
  }
  closeSettings();
});

/* ---------------- 三層濾網結果渲染 ---------------- */

const TREND_POSITION = { 空方: 16, 盤整: 50, 多方: 84 };
const TREND_CLASS = { 空方: "bear", 盤整: "flat", 多方: "bull" };

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, (c) => ({
    "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;",
  }[c]));
}

function renderGaugeRow(periodLabel, layer) {
  const pos = TREND_POSITION[layer.trend] ?? 50;
  const trendClass = TREND_CLASS[layer.trend] ?? "flat";
  const rowState = layer.passed ? "passed" : "failed";

  return `
    <div class="gauge-row ${rowState}">
      <div class="gauge-head">
        <span class="gauge-period">${periodLabel}</span>
        <span class="gauge-trend ${trendClass}">${escapeHtml(layer.trend)}</span>
      </div>
      <div class="gauge-track">
        <div class="gauge-dot" style="left:${pos}%"></div>
      </div>
      <div class="gauge-zone-labels">
        <span>空方</span><span>盤整</span><span>多方</span>
      </div>
      <p class="gauge-detail">${escapeHtml(layer.detail)}</p>
    </div>
  `;
}

function renderResult(data) {
  const verdictClass = data.is_buy_signal ? "is-buy" : "is-no";
  const verdictTitle = data.is_buy_signal ? "符合波段買進條件" : "尚未符合買進條件";

  els.resultArea.innerHTML = `
    <div class="meta-row">
      <span class="code">${escapeHtml(data.stock_code)}</span>
      <span>${escapeHtml(data.analysis_date)}</span>
    </div>

    <div class="verdict ${verdictClass}">
      <span class="verdict-icon"></span>
      <div>
        <p class="verdict-title">${verdictTitle}</p>
        <p class="verdict-sub">${escapeHtml(data.summary)}</p>
      </div>
    </div>

    <div class="gauge-stack">
      ${renderGaugeRow("月線", data.monthly_layer)}
      ${renderGaugeRow("週線", data.weekly_layer)}
      ${renderGaugeRow("日線", data.daily_layer)}
    </div>
  `;
}

function renderLoading() {
  els.resultArea.innerHTML = `
    <div class="skeleton-row"></div>
    <div class="skeleton-row"></div>
    <div class="skeleton-row"></div>
  `;
}

function renderError(message) {
  els.resultArea.innerHTML = `
    <div class="error-state">
      <strong>查詢失敗：</strong>${escapeHtml(message)}
    </div>
  `;
}

function renderEmpty() {
  els.resultArea.innerHTML = EMPTY_STATE_HTML;
}

/* ---------------- 表單送出 ---------------- */

els.form.addEventListener("submit", async (event) => {
  event.preventDefault();
  const code = els.input.value.trim();
  if (!code) return;

  els.submitBtn.disabled = true;
  els.submitBtn.textContent = "分析中…";
  renderLoading();

  try {
    const base = getApiBaseUrl();
    const url = `${base}/api/v1/analysis/triple-screen/${encodeURIComponent(code)}`;
    const resp = await fetch(url, { headers: { Accept: "application/json" } });

    if (resp.status === 404) {
      const body = await resp.json().catch(() => ({}));
      renderError(body.detail || `查無股票代碼 ${code} 的歷史資料`);
      return;
    }
    if (!resp.ok) {
      renderError(`伺服器回應異常（HTTP ${resp.status}），請稍後再試`);
      return;
    }

    const data = await resp.json();
    renderResult(data);
  } catch (err) {
    renderError("無法連線到分析伺服器，請確認網路連線，或至設定確認 API 位址是否正確");
  } finally {
    els.submitBtn.disabled = false;
    els.submitBtn.textContent = "分析";
  }
});

els.input.addEventListener("input", () => {
  if (!els.input.value && els.resultArea.innerHTML !== EMPTY_STATE_HTML) {
    // 保留結果，不在使用者打字時清空，避免閃爍
  }
});

/* ---------------- 安裝提示 ---------------- */

function showInstallToast(message) {
  els.installToastText.textContent = message;
  els.installToast.classList.add("show");
}
els.installToastClose.addEventListener("click", () => { els.installToast.classList.remove("show"); });

let deferredInstallEvent = null;
window.addEventListener("beforeinstallprompt", (event) => {
  event.preventDefault();
  deferredInstallEvent = event;
  showInstallToast("點此將「台股波段濾網」加入主畫面，下次可直接從桌面開啟");
  els.installToastText.style.cursor = "pointer";
  els.installToastText.addEventListener("click", () => {
    if (deferredInstallEvent) {
      deferredInstallEvent.prompt();
      deferredInstallEvent = null;
      els.installToast.classList.remove("show");
    }
  });
});

(function maybeShowIosInstallHint() {
  const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);
  const isStandalone = window.matchMedia("(display-mode: standalone)").matches || navigator.standalone;
  if (isIos && !isStandalone) {
    showInstallToast("點右上角分享圖示，選擇「加入主畫面」即可安裝此 App");
  }
})();

/* ---------------- Service Worker 註冊（PWA 可安裝性） ---------------- */

if ("serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("service-worker.js").catch(() => {
      /* 註冊失敗不影響主要功能，僅PWA安裝/離線快取會不可用 */
    });
  });
}
