# SWAG QA Debug Hunter

> **SWAG 台灣成人直播平台 QA 部門專屬系統 Bug 偵測、漏洞挖掘與自動化修復驗收框架**

本框架基於原版 `debug-hunter` 架構全面重構，針對 SWAG 核心業務場景（博弈遊戲、成人直播、第三方金流、B2B 買分後台）量身定做，並將技術棧從 Java 全面升級為 **Python、React/JSX、JavaScript、RobotFramework、Playwright、Appium、Flutter Web**。

---

## 為什麼 SWAG QA 需要這套框架？

傳統 QA 工具對 SWAG 業務有三個致命盲點，而這正是本框架要補的：

| 痛點 | 一般工具 | SWAG QA Debug Hunter |
|------|---------|----------------------|
| **看不懂業務邏輯** | 只抓語法層漏洞（XSS、SQLi） | 內建金流地圖、博弈狀態機、授權歸屬矩陣，能抓**回調偽造無成本充值、延遲投注、並發負餘額、打賞競態免費送禮**這類「程式沒寫錯、但有人故意」的漏洞 |
| **自信地報錯（誤報）** | 一律高危，淹沒真問題 | **證據門檻**：一個發現在補齊「污染路徑 + DB 證據 + 反證檢查」前，只能是「疑似」，不准喊高危 |
| **只找不修** | 給一張清單就結束 | **閉環**：復現（攻擊 PoC）→ 修復 → 驗收（不變量恆成立）→ 把每個漏洞沉澱成永久規則與回歸語料，下次自動攔截 |

**一句話**：它不只問「程式會不會自己算錯」，更問「**攻擊者能不能讓它替他算**」——並用「金錢守恆」這類不變量當最後一張網，兜住所有未知手法。

---

## 核心業務覆蓋範圍

| 業務模組 | 覆蓋場景 | 主要威脅 |
| :--- | :--- | :--- |
| **博弈遊戲** | 龍虎鬥、百家樂、骰寶、轉盤 | 延遲投注、並發負餘額、重複結算、RNG 預測 |
| **成人直播平台** | swag.live 直播間、打賞、付費解鎖 | 打賞競態免費送、XSS 彈幕竊 Token、付費內容本地繞過 |
| **第三方金流** | 綠界 ECPay、91app、支付寶、微信支付 | 回調偽造、金額篡改、重放攻擊、0 元購 |
| **API 買分後台** | B2B 商戶管理、代理商調帳 | IDOR 越權調帳、API 重放、大額調帳缺審批 |
| **前端與 App** | React/JSX Web、Flutter Web/App | 負數輸入繞過、SSL Pinning 缺失、本地狀態篡改 |

---

## 目錄結構

```
debug-hunter-main/
├── SKILL.md                          ← 技能主入口（核心指南與導航）
├── AGENT.md                          ← AI 獵殺與驗收總指揮官
├── agents/
│   ├── swag_detector.md              ← Bug 偵測與威脅建模代理人
│   └── swag_reproducer.md            ← 自動化復現與驗收代理人
├── knowledge-base/
│   ├── payment_invariants.md         ← 金流與支付防禦知識庫（綠界/支付寶/微信/91app）
│   ├── gaming_invariants.md          ← 博弈遊戲不變量與防禦知識庫（龍虎鬥/百家樂）
│   ├── streaming_invariants.md       ← 直播平台與 API 買分後台知識庫
│   └── frontend_app_invariants.md   ← 前端與 App 交互防禦知識庫（React/Flutter/Appium）
├── rules/
│   ├── semgrep/
│   │   └── swag-security-rules.yml  ← Python/React 靜態安全掃描規則
│   └── playwright/
│       └── swag-playwright-specs.js ← 前端防禦 E2E 自動化測試基線
└── scripts/
    └── swag_run_tests.py             ← 一鍵啟動掃描與 PoC 驗收工具
```

---

## 快速開始

### 1. 執行靜態代碼安全掃描（CI/CD 可掛）
```bash
# 安裝 Semgrep
pip install semgrep

# 對你的代碼庫執行 SWAG 專屬安全規則掃描
semgrep --config rules/semgrep/swag-security-rules.yml /path/to/your/code
```

### 2. 執行 Playwright 前端防禦自動化測試
```bash
# 安裝 Playwright
npm install -D @playwright/test

# 執行 SWAG 前端安全測試基線
npx playwright test rules/playwright/swag-playwright-specs.js
```

### 3. 使用 Python 啟動器一鍵執行
```bash
# 靜態掃描
python scripts/swag_run_tests.py scan --target /path/to/your/code

# 漏洞復現 PoC 驗收
python scripts/swag_run_tests.py poc --name poc_ecpay_spoofing.py
```

### 4. 用 Claude Code 跑完整閉環（主要用法）
把 Claude Code 指向總指揮 `AGENT.md`，它會自動載入知識庫並依 5 個 Stage 執行：
```bash
claude --agent AGENT.md "掃描 payment/ 模組，找出所有高風險金流與安全漏洞"
```

---

## 五大閉環 Stage

```
Stage 0: 威脅建模  →  Stage 1: 雙軌偵測  →  Stage 2: 風險分類
                                                    ↓
Stage 5: 規則回寫  ←  Stage 4: 自動驗收  ←  Stage 3: 漏洞修復
```

---

## 技術棧支持

| 語言/框架 | 應用場景 |
| :--- | :--- |
| **Python** | 後端 API、金流回調、博弈遊戲核心邏輯、PoC 腳本 |
| **React / JSX** | 前端充值、投注、打賞界面安全審查 |
| **JavaScript / TypeScript** | Node.js API、WebSocket 遊戲服務器 |
| **RobotFramework** | API 接口自動化測試、金流回調安全測試 |
| **Playwright** | 前端 E2E 安全測試、XSS 防禦校驗、輸入邊界測試 |
| **Appium** | Android/iOS App 安全測試（SSL Pinning、本地存儲） |
| **Flutter Web** | Flutter Web 前端安全審查、本地狀態篡改防禦 |

---

© 2026 SWAG Live - QA Department DevSecOps Division.
