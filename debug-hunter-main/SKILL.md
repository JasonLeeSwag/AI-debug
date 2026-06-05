---
name: swag-qa-debug-hunter
description: SWAG QA 部門專屬系統 Bug 偵測、漏洞挖掘與自動化修復驗收技能。適用於博弈遊戲（龍虎鬥、百家樂）、直播平台、第三方金流（綠界、91app、支付寶、微信支付）、API 買分後台。支持 Python、React/JSX、JS、RobotFramework、Playwright、Appium、Flutter。
---

# SWAG QA 系統 Bug 偵測與修復技能 (SWAG QA Debug Hunter Skill)

本技能專為 **SWAG 台灣成人直播平台** QA 部門量身定做。它將原有的 Java 財務審計框架全面重構並升級為適用於 SWAG 核心業務（博弈、直播、金流、B2B 後台）與主流技術棧（Python, React/JSX, JS, RobotFramework, Playwright, Appium, Flutter）的自動化 Bug 偵測、漏洞復現、安全修復與自動化驗收體系。

---

## 1. 核心業務不變量導航 (Invariants Map)

在進行任何測試或代碼審查時，必須強制對齊以下核心不變量：

*   **金流不變量 (`payment-invariants`)**: 
    *   `INV-PAY-01`: 充值金額守恆（實付金額 * 比例 == 鑽石增加數）
    *   `INV-PAY-03`: 回調冪等性（重複通知僅處理一次）
    *   `INV-PAY-05`: 簽章防篡改（CheckMacValue / Signature 驗證）
*   **博弈不變量 (`gaming-invariants`)**:
    *   `INV-GAME-01`: 下注餘額守恆（餘額不允許扣成負數）
    *   `INV-GAME-03`: 下注時效守衛（開牌後嚴禁追加投注，防範延遲投注）
*   **直播與後台不變量 (`streaming-invariants`)**:
    *   `INV-STR-01`: 打賞扣加守恆（用戶扣減鑽石 == 主播增加鑽石 + 平台抽成）
    *   `INV-ADM-01`: 買分雙人覆核（大額調帳必須 Maker-Checker 審批）
*   **前端與移動端不變量 (`frontend-app-defenses`)**:
    *   `INV-FE-02`: 輸入邊界校驗（投注、充值輸入框過濾負數與特殊字符）
    *   `INV-MOB-01`: SSL Pinning 安全性（防範 Charles/Fiddler 抓包篡改）

---

## 2. 技能包目錄結構 (Directory Layout)

本技能包包含以下關鍵模組與資源：

```
swag-qa-debug-hunter/
├── SKILL.md (本文件 - 核心指南與導航)
├── AGENT.md (AI 獵殺與驗收總指揮官配置)
├── references/
│   ├── payment_invariants.md (金流與支付防禦知識庫)
│   ├── gaming_invariants.md (博弈遊戲不變量與防禦知識庫)
│   ├── streaming_invariants.md (直播平台與 API 買分後台知識庫)
│   └── frontend_app_invariants.md (前端與 App 交互防禦知識庫)
├── agents/
│   ├── swag_detector.md (Bug 偵測與威脅建模代理人)
│   └── swag_reproducer.md (自動化復現與驗收代理人)
├── rules/
│   ├── semgrep/
│   │   └── swag-security-rules.yml (Python/React 專屬靜態安全掃描規則)
│   └── playwright/
│       └── swag-playwright-specs.js (前端網頁安全自動化測試基線)
├── scripts/
│   └── swag_run_tests.py (自動化測試與漏洞掃描啟動器)
└── examples/ (包含各類博弈、金流的脆弱代碼與 PoC 演示案例)
```

---

## 3. QA 部門快速上手指南 (Quick Start)

### A. 執行本地或 CI/CD 代碼靜態安全掃描
QA 工程師或開發人員可以使用啟動器腳本，快速調用 Semgrep 對目標代碼庫進行 SWAG 專屬安全規則掃描：
```bash
python /home/ubuntu/skills/swag-qa-debug-hunter/scripts/swag_run_tests.py scan --target /path/to/your/code
```

### B. 運行自動化漏洞復現 PoC
要驗證某個漏洞是否在當前環境中存在，或者在修復後進行回歸驗收：
```bash
python /home/ubuntu/skills/swag-qa-debug-hunter/scripts/swag_run_tests.py poc --name poc_late_betting.py
```

### C. 執行 Playwright 前端防禦自動化測試
將 `swag-playwright-specs.js` 引入您的 E2E 測試框架中，運行：
```bash
npx playwright test /home/ubuntu/skills/swag-qa-debug-hunter/rules/playwright/swag-playwright-specs.js
```

---

## 4. 知識庫與規則更新機制 (Governance)

1.  **Bug 回溯與復盤**: 每次 Staging 或 Production 出現 P0/P1 級 Bug 後，必須提煉出其**違反的核心不變量**。
2.  **規則提煉**: 
    *   如果是語法或污染流特徵，將其編寫為 `swag-security-rules.yml` 中的 **Semgrep 規則**。
    *   如果是前端交互或邊界漏洞，編寫為 `swag-playwright-specs.js` 中的 **Playwright 測試案例**。
3.  **自動化回歸**: 確保每次 CI/CD 流程中都會自動執行上述掃描與測試，實現**「修復一個 Bug，就永遠不再回來」**的研發安全閉環。
