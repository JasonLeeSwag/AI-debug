---
name: swag-qa-debug-hunter
description: SWAG QA 部門專屬系統 Bug 偵測、漏洞挖掘、Design QA 自動化驗收技能。適用於博弈遊戲（龍虎鬥/百家樂）、直播平台（Moor/Web/Ramen）、第三方金流（ECPay/AFTEE/支付寶/微信）、API 買分後台。支援 Python、React/JSX、JS、RobotFramework、Playwright、Appium、Flutter。
---

# SWAG QA Debug Hunter — 技能總覽

本技能專為 **SWAG 台灣成人直播平台 QA 部門**量身定做，涵蓋五大核心能力：
Bug 偵測 / 安全掃描 / Design QA / 環境脈絡收集 / FullTest 自動化驗收。

---

## 1. 核心業務不變量（QA 底線，任何情況都不能違反）

### 金流不變量
| ID | 規則 |
|----|------|
| `INV-PAY-01` | 充值金額守恆：實付金額 × 比例 == 鑽石增加數 |
| `INV-PAY-03` | 回調冪等性：重複通知僅處理一次 |
| `INV-PAY-05` | 簽章防篡改：CheckMacValue / Signature 必須驗證 |

### 博弈不變量
| ID | 規則 |
|----|------|
| `INV-GAME-01` | 下注餘額守恆：餘額不允許扣成負數 |
| `INV-GAME-03` | 下注時效守衛：開牌後嚴禁追加投注 |

### 直播業務不變量
| ID | 規則 |
|----|------|
| `INV-STR-01` | 打賞扣加守恆：用戶扣減鑽石 == 主播增加鑽石 + 平台抽成 |
| `INV-LIVE-MOO-001` | 主播接受任一邀請後，其餘所有邀請必須自動拒絕 |
| `INV-LIVE-MOO-002` | 一對一預扣時間內，切換模式必須被阻擋 |
| `INV-LIVE-MOO-003` | 主播主動退出一對一，用戶必須拿回全額 |
| `INV-LIVE-MOO-004` | Show 進行中，關播/切換模式/發挑逗表演必須被阻擋 |
| `INV-WEB-001` | 鑽石增減必須有對應 Log 可查 |
| `INV-WEB-002` | 限時動態解鎖後永久保存，不受 48 小時限制 |

### 前端與 App 不變量
| ID | 規則 |
|----|------|
| `INV-FE-02` | 輸入邊界校驗：投注/充值輸入框過濾負數與特殊字元 |
| `INV-MOB-01` | SSL Pinning 安全性：防範 Charles/Fiddler 抓包篡改 |

---

## 2. 五大技能說明

### 技能一：Bug 偵測與安全掃描（`/bug-scan`）

對程式碼執行 SWAG 業務邏輯 Bug + 安全漏洞掃描。

**觸發方式：**
```
/bug-scan [模組名稱或程式碼描述]
→ 貼上程式碼後開始掃描
```

**輸出：** P0/P1/P2 問題清單 + 違反的不變量 ID + 修復建議

---

### 技能二：Design QA 自動化驗查（`/design-qa`）

上傳 SPEC + Figma → 5 大 UI 檢查 → 自動產出並執行 Playwright 測試。

**觸發方式：**
```
/design-qa [功能名稱]
→ 提供 SPEC 文字 + Figma 連結（或截圖）+ 實際畫面截圖
```

**5 大檢查項目：**
1. 視覺一致性（Figma vs 實作：色碼/字型/間距）
2. SPEC 需求符合性（逐條對照）
3. SWAG 業務邏輯 UI 驗查（博弈/打賞/支付/買分）
4. 可及性稽核（WCAG 2.1 AA）
5. 響應式斷點（375 / 768 / 1440px）

**自動執行流程（Claude Code CLI）：**
```
分析 → 產出測試腳本 → 寫入 tests/design-qa/ → 執行 npx playwright test → 回傳結果
```

**前置準備（一次性）：**
```bash
npm install && npx playwright install
export SWAG_TEST_URL=https://v3-277.app.swag.live
```

---

### 技能三：環境脈絡收集（`/env-check`）

任何測試前必須先執行，確認 OS / 裝置 / 網路 / VPN / 地理位置。

**觸發方式：**
```
/env-check
```

**自動警告：**
- VPN 啟用 → 支付測試會被 IP 白名單阻擋，警告並阻止
- 境外 IP → 提示部分功能受地理封鎖影響

---

### 技能四：FullTest 驗收清單（`/fulltest`）

依版本範圍產出 FullTest Checkbox 清單，含帳號準備需求。

**觸發方式：**
```
/fulltest [版本號或功能名稱]
```

**輸出：** 分層 Checkbox 清單（直播/影片/金流/帳號/Ramen）+ 帳號需求 + P0 必過項目標注

---

### 技能五：Bug Report 產生器（`/new-bug`）

自動收集環境資訊 + 產出標準 Bug Report 草稿，並比對業務邏輯判斷是否為 Known Issue。

**觸發方式：**
```
/new-bug [問題簡短描述]
```

**輸出：** 標準 Bug Report 草稿（含環境脈絡 + 業務不變量比對 + 建議嚴重度）

---

## 3. 知識庫導覽（載入優先順序）

| 知識庫 | 用途 | 何時讀取 |
|--------|------|---------|
| `knowledge-base/swag-product-map.md` | 7 款產品、環境/分支對照、Ramen 加密 | 確認測試對象時 |
| `knowledge-base/swag-business-logic.md` | Moor/Web 業務規則、業務不變量 | 判斷是 Bug 還是設計 |
| `knowledge-base/swag-test-process.md` | 發版節奏、Bug 報告格式、FullTest | 測試流程依據 |
| `knowledge-base/swag-test-accounts.md` | 帳號類型、jbot 指令、鑽石管理 | 準備測試帳號 |
| `knowledge-base/gambling-game-patterns.md` | 博弈 Bug 模式 | 審查博弈 PR |
| `knowledge-base/payment-gateway-patterns.md` | 金流 Bug 模式 | 審查支付 PR |
| `knowledge-base/streaming-platform-patterns.md` | 直播 Bug 模式 | 審查直播 PR |
| `knowledge-base/design-qa-patterns.md` | UI 問題模式、SWAG 色碼 Token | Design QA |
| `knowledge-base/environment-context-patterns.md` | 環境對測試影響模式 | 分析環境相關 Bug |

---

## 4. 產品清單（SWAG 七款產品）

| 產品 | 技術類型 | 測試重點 |
|------|---------|---------|
| **Moor** | iOS/Android App | 直播模式切換、一對一計費、Show 機制 |
| **Flutter Web** | Flutter Web | OBS 開播、主播介面 |
| **Sushi** | Hybrid（Web+Flutter） | Web↔Native 切換順暢度 |
| **Ramen** | Android Web View | 中國市場；API 加密；載入 < 10 秒 |
| **Ramen-MDM** | iOS Web View | 同 Ramen 但 iOS |
| **Web** | Chrome/Safari | 主要測試環境，PC 為主 |
| **PWA** | 瀏覽器快捷 | 安裝後行為是否與 Web 一致 |

> ⚠️ **後端無獨立測試環境**，BE 發版即上正式。週二測試 / 週四上線。

---

## 5. 金流測試範圍（FullTest）

| 支付方式 | 是否測試 |
|---------|---------|
| **信用卡** | ✅ 必測 |
| **AFTEE 先享後付** | ✅ 必測 |
| 支付寶 / 轉帳 / 虛擬幣 | ❌ FullTest 不測 |

> 在 Live 環境測試未公開金流商時，必須使用 **Beta Tag 帳號**，測完記得退發票。

---

## 6. 目錄結構

```
debug-hunter-main/
├── SKILL.md                    ← 本文件（claude.ai Project Skill 定義）
├── AGENT.md                    ← 主代理人指令（完整 QA 流程）
├── playwright.config.js        ← Playwright 設定（SWAG_TEST_URL 環境變數）
├── package.json                ← npm 依賴（@playwright/test）
├── .claude/
│   └── commands/               ← Claude Code CLI Slash Commands
│       ├── design-qa.md        → /design-qa
│       ├── bug-scan.md         → /bug-scan
│       ├── env-check.md        → /env-check
│       ├── fulltest.md         → /fulltest
│       └── new-bug.md          → /new-bug
├── agents/
│   ├── design-qa.md            ← Design QA 代理人（含自動執行流程）
│   └── ...
├── knowledge-base/
│   ├── swag-product-map.md     ← 7 款產品 / 環境對照
│   ├── swag-business-logic.md  ← Moor/Web 業務規則
│   ├── swag-test-process.md    ← 測試流程 / Bug 報告標準
│   ├── swag-test-accounts.md   ← 帳號管理 / jbot 指令
│   ├── gambling-game-patterns.md
│   ├── payment-gateway-patterns.md
│   ├── streaming-platform-patterns.md
│   ├── design-qa-patterns.md
│   ├── environment-context-patterns.md
│   └── KB-INDEX.md             ← 知識庫總索引
├── scripts/
│   └── env_context.py          ← 環境脈絡收集器
└── tests/
    └── design-qa/              ← Design QA 產出的 Playwright 測試存放處
```

---

## 7. 在 claude.ai Project 中使用本技能

### 放入方式
1. 進入 claude.ai → 左側 **Projects** → SWAG QA Debug Hunter
2. 點右上角齒輪 → **Project instructions**
3. 將本文件（`SKILL.md`）的內容貼入，儲存

### 使用方式
進入 Project 後直接描述任務即可，無需輸入指令：
```
請幫我審查這段支付程式碼（貼程式碼）
請幫我對「支付儲值頁面」執行 Design QA（貼 SPEC + Figma）
請幫我產出這次版本的 FullTest 清單
```

> **Slash commands（`/design-qa` 等）僅在 Claude Code CLI 中有效。**
> claude.ai Project 版本請用自然語言描述任務。
