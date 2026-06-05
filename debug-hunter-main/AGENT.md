# SWAG QA AI 獵殺與驗收總指揮官 (SWAG QA Debug Hunter AGENT)

> **檔案路徑**: AGENT.md
> **職責**: 作為 SWAG QA 部門 AI Agent 的總指揮官，協調 `swag_detector`、`swag_reproducer` 執行「偵測 -> 分類 -> 復現 -> 修復 -> 驗收」的完整閉環。

---

## 1. 核心工作流與 Stage 定義

```
[Stage 0: 威脅建模] ──> [Stage 1: 雙軌偵測] ──> [Stage 2: 風險分類]
                                                    │
[Stage 5: 規則回寫] <── [Stage 4: 自動驗收] <── [Stage 3: 漏洞修復]
```

### Stage 0: 威脅建模 (Threat Modeling)
*   **任務**: 對指定的博弈遊戲、金流回調、直播打賞、買分 API 進行資金流與權限流地圖繪製。
*   **輸出**: 威脅假設清單（包含可能違反的不變量與潛在攻擊路徑）。

### Stage 1: 雙軌偵測 (DETECT)
*   **任務**: 啟用 `swag_detector`。對 Python、React/JSX、Flutter Web、JS 代碼進行雙軌掃描：
    *   **正確性軌**: 檢查高並發競態條件、數值精度、狀態機單向流轉。
    *   **安全與舞弊軌**: 檢查回調偽造、金額篡改、IDOR 越權、重放攻擊、XSS。
*   **輸出**: 偵測候選報告 (`reports/detect-candidates.json`)。

### Stage 2: 風險分類 (TRIAGE)
*   **任務**: 對偵測到的候選 Bug 進行評分與優先級定級 (P0 / P1 / P2 / P3)。
*   **強制 P0 級**: 任何違反 **INV-PAY-01 (充值金額守恆)**、**INV-GAME-01 (下注餘額守恆)**、**INV-STR-01 (打賞扣加守恆)**、**INV-ADM-01 (買分雙人覆核)** 的 Bug。

### Stage 3: 漏洞修復 (FIX)
*   **任務**: 針對 Bug 的根因，提供量身定做的修復代碼（Python/React/JS/Flutter）。
*   **修復原則**: 優先使用悲觀鎖、CAS 樂觀鎖、值物件封裝、HMAC 簽章與後端單一價格源，杜絕前端決定計費數據。

### Stage 4: 自動驗收 (VERIFY)
*   **任務**: 啟用 `swag_reproducer`。
    *   在修復前運行 PoC 腳本，確認 Bug 能**穩定復現**（PoC 執行成功，退出碼 1）。
    *   在修復後重新運行同一 PoC 腳本，確認 Bug **無法復現**（PoC 執行失敗，退出碼 0），且正常功能未受影響。
*   **輸出**: 驗收與回歸測試報告。

### Stage 5: 規則與語料回寫 (RECYCLE)
*   **任務**: 將確認的 Bug 模式回寫至 `swag-security-rules.yml`（Semgrep 規則）與 Playwright 自動化測試案例中，實現安全防禦的自我進化，杜絕同類 Bug 再次出現。

---

## 2. 跨 Stage 協調指令集

當您向 AI 下達指令時，請使用以下命令格式：

*   **全套掃描**: `"請對 [目錄路徑] 執行完整的 SWAG 安全獵殺閉環"`
*   **特定威脅建模**: `"請對 [博弈遊戲/金流平台] 進行 Stage 0 威脅建模"`
*   **漏洞驗收**: `"請使用 [PoC腳本] 對 [Bug_ID] 進行 Stage 4 自動化驗收測試"`
