---
file_id: KB-INDEX
kind: meta
status: active
schema_version: 2.0
last_reviewed: 2026-06-05
stale_after_days: 90
owner: swag-qa-team
external_refs: []
---

# SWAG QA 知識庫導覽索引（KB Index）

> 用途：全庫單一導覽入口，供 SWAG QA 工程師快速找到所需知識庫檔案。
> 適用範圍：博弈遊戲（龍虎鬥/百家樂）、成人直播平台（swag.live）、金流支付（ECPay/91app/支付寶/微信）、API 買分後台
> 技術堆疊：Python、FastAPI/Django、React/JSX、JavaScript、Flutter Web、Robot Framework、Playwright、Appium
> 維護規則：新增/刪除 KB 檔或新增 PAT/RULE 時同步更新本檔。

---

## 一、知識庫檔案清單

### 1.1 SWAG 核心業務模式庫（優先讀取）

| 檔案名稱 | 類型 | 主要內容 | 適用 Stage |
|---------|------|---------|-----------|
| **swag-bug-patterns.md** | 模式庫 | SWAG 主要 Bug 模式：點數系統、打賞、訂閱、安全、QA 自動化 | DETECT |
| **gambling-game-patterns.md** | 模式庫 | 博弈遊戲專用：RNG 安全、賠率計算、並發結算、龍虎鬥/百家樂 | DETECT |
| **payment-gateway-patterns.md** | 模式庫 | 金流支付整合：ECPay/91app/支付寶/微信驗簽、金額比對、冪等 | DETECT |
| **streaming-platform-patterns.md** | 模式庫 | 直播平台：打賞冪等、主播分潤、年齡驗證、訂閱系統 | DETECT |
| **qa-automation-patterns.md** | 模式庫 | QA 自動化：Robot Framework、Playwright、Appium 最佳實踐 | VERIFY |
| **environment-context-patterns.md** | 模式庫 | 環境脈絡：OS/裝置/網路/VPN/地理位置偵測，環境對測試結果影響模式 | 全域（強制前置） |
| **design-qa-patterns.md** | 模式庫 | Design QA：Figma vs 實作視覺比對、SPEC 符合性、WCAG 可及性、RWD 斷點 | VERIFY |

### 1.2 SWAG 產品與業務知識庫（Notion 同步）

| 檔案名稱 | 類型 | 主要內容 | 適用 Stage |
|---------|------|---------|-----------|
| **swag-product-map.md** | 產品地圖 | 7 款產品概覽（Moor/Flutter Web/Sushi/Ramen/MDM/Web/PWA）、環境對照、Ramen 加密機制、測試策略 | 全域（測試前必讀） |
| **swag-business-logic.md** | 業務邏輯 | Moor 直播模式、計費規則、邀請機制、Show 機制；Web 影片類型、VIP、封鎖；QA 業務不變量清單 | DETECT（判斷是 Bug 還是設計） |
| **swag-test-process.md** | 測試流程 | 版本節奏（週二測試/週四上線）、Bug 報告模板、FullTest 清單、China QA 城市撥測規範 | 全域（流程依據） |
| **swag-test-accounts.md** | 帳號管理 | 帳號類型（Mod View/Beta/Non-beta）、VIP 等級、jbot 指令（Tag/鑽石）、帳號準備 Checklist | REPRODUCE/VERIFY |

### 1.3 業務支援知識庫

| 檔案名稱 | 類型 | 主要內容 | 適用 Stage |
|---------|------|---------|-----------|
| **swag-domain-glossary.md** | 術語表 | SWAG 業務術語：點數/分、打賞、訂閱、房費、分潤、各支付平台術語對照 | 全域 |
| **financial-bug-patterns.md** | 模式庫 | 通用金融 Bug 模式（BigDecimal、並發、排程），Java 版本為主 | DETECT |
| **financial-security-patterns.md** | 模式庫 | 金融安全模式：IDOR、Mass Assignment、重放攻擊、審計日誌 | DETECT |
| **financial-invariants.md** | 不變量 | 金融系統不變量（守恆、單調、冪等、狀態機） | DETECT/VERIFY |

### 1.4 規則與清單

| 檔案名稱 | 類型 | 主要內容 | 適用 Stage |
|---------|------|---------|-----------|
| **rules-registry.md** | 規則登錄 | SWAG 靜態掃描規則：GAM/PAY/CRED/LIVE/SEC/QA 各類規則（21 條） | FIX/RECYCLE |
| **payment-checklist.md** | 檢查清單 | 支付/點數 PR 檢查清單（30 項）：精度、驗簽、冪等、業務守衛 | FIX |
| **settlement-checklist.md** | 檢查清單 | Java 結算系統 PR 檢查清單（BigDecimal、事務、並發、冪等） | FIX |

### 1.5 工具與自動化

| 檔案名稱 | 類型 | 主要內容 | 適用 Stage |
|---------|------|---------|-----------|
| **oss-debug-security-loop.md** | 工具整合 | Python/JS 技術堆疊工具整合：Bandit、Semgrep、ESLint、Gitleaks、ZAP | DETECT/VERIFY |
| **property-test-catalog.md** | 測試目錄 | 屬性測試（Property-Based Testing）模板，Hypothesis 等 | VERIFY |
| **reproduce-scenarios.md** | 重現場景 | Bug 重現腳本和場景（SCENE-*） | REPRODUCE |
| **attack-regression-corpus.md** | 語料庫 | 已確認漏洞的回歸測試語料（CORP-*） | VERIFY/RECYCLE |

### 1.6 系統設計與威脅模型

| 檔案名稱 | 類型 | 主要內容 | 適用 Stage |
|---------|------|---------|-----------|
| **money-flow-map.md** | 清單 | 金流路徑圖（MF-01..08）：充值/消費/分潤/出金路徑 | THREAT-MODEL |
| **threat-catalog.md** | 威脅目錄 | STRIDE 威脅模型 + 攻擊行為（AB-*） | THREAT-MODEL |
| **authorization-ownership-matrix.md** | 清單 | 歸屬鏈與授權矩陣，IDOR 防護基準 | DETECT |
| **workflow-state-machine-catalog.md** | 清單 | 訂單/支付/退款狀態機（PAT-WF-*） | DETECT |
| **value-authority-sanitizer-registry.md** | 登錄 | 數值域五閘（來源/上限/精度/原子/冪等） | DETECT |
| **persistence-consistency-controls.md** | 清單 | 資料庫一致性控制（PAT-PERSIST-*） | DETECT/VERIFY |

### 1.7 分析與輔助工具

| 檔案名稱 | 類型 | 主要內容 | 適用 Stage |
|---------|------|---------|-----------|
| **finding-evidence-standard.md** | 標準 | Finding 生命週期與反證義務 | TRIAGE |
| **ai-scan-false-positive-patterns.md** | 模式庫 | 誤報模式（FP-001..003） | TRIAGE |
| **severity-loss-model.md** | 模型 | 嚴重度與損失量化（ALE 公式） | TRIAGE |
| **compliance-mapping.md** | 登錄 | 合規對應（PCI DSS、ASVS、AML） | RECYCLE |
| **refund-reversal-compensation-patterns.md** | 模式庫 | 退款/沖正/補償模式（PAT-REF-*） | DETECT |
| **time-window-cutoff-calendar-rules.md** | 模式庫 | 時間視窗/截止/日曆規則（PAT-TIME-*） | DETECT |
| **version-compatibility-matrix.md** | 參考 | 版本相容性矩陣（Python/FastAPI/Django 風險） | DETECT |
| **knowledge-schema.md** | 元資料 | 知識庫模式定義與入庫狀態機 | RECYCLE |
| **MAP.md** | 地圖 | 知識庫視覺化關係圖 | 全域 |

---

## 二、依任務類型的讀取順序建議

### 2.1 審查博弈遊戲 PR

```
Step 1 快速定位
  → gambling-game-patterns.md（核心博弈 Bug 模式）
  → rules-registry.md（RULE-GAM-001 ~ 004）

Step 2 精度與安全
  → swag-bug-patterns.md（PAT-CRED-* 點數計算精度）
  → financial-invariants.md（守恆不變量）

Step 3 並發安全
  → persistence-consistency-controls.md（原子操作、行鎖）
  → workflow-state-machine-catalog.md（結算狀態機）

Step 4 核對清單
  → payment-checklist.md（第 12、13 項並發安全）

Step 5 測試覆蓋
  → property-test-catalog.md（博弈計算屬性測試）
  → qa-automation-patterns.md（Robot Framework 測試策略）
```

### 2.2 審查支付/金流 PR

```
Step 1 快速定位
  → payment-gateway-patterns.md（各平台支付 Bug 模式）
  → rules-registry.md（RULE-PAY-001 ~ 004）

Step 2 完整核對
  → payment-checklist.md（全部 30 項）

Step 3 安全加固
  → financial-security-patterns.md（PAT-SEC-104 回調驗簽）
  → authorization-ownership-matrix.md（歸屬校驗）

Step 4 合規檢查
  → compliance-mapping.md（PCI DSS 支付安全要求）

Step 5 測試驗收
  → reproduce-scenarios.md（支付回調重放場景）
  → attack-regression-corpus.md（已知支付漏洞回歸）
```

### 2.3 審查點數/打賞 PR

```
Step 1 快速定位
  → swag-bug-patterns.md（PAT-CRED-* 點數、PAT-LIVE-* 打賞）
  → rules-registry.md（RULE-CRED-001 ~ 004、RULE-LIVE-001 ~ 003）

Step 2 精度驗證
  → payment-checklist.md（第 1 ~ 4 項 Decimal 精度）
  → financial-invariants.md（守恆不變量 INV-TXN-05）

Step 3 冪等與並發
  → payment-checklist.md（第 11 ~ 15 項）
  → value-authority-sanitizer-registry.md（五閘檢核）

Step 4 安全審查
  → rules-registry.md（RULE-SEC-001 IDOR、RULE-SEC-002 日誌）
  → financial-security-patterns.md（PAT-SEC-111 敏感欄位）
```

### 2.4 全專案安全掃描

```
Step 1 工具設定
  → oss-debug-security-loop.md（選擇工具組合）

Step 2 威脅模型
  → money-flow-map.md（確認掃描範圍）
  → threat-catalog.md（STRIDE 攻擊面清單）

Step 3 掃描執行（按優先順序）
  → 1. Bandit + Semgrep（Python SAST）
  → 2. ESLint + security plugin（JS/JSX SAST）
  → 3. Gitleaks（Secrets 掃描）
  → 4. Safety / pip-audit + npm audit（依賴漏洞）
  → 5. Playwright + ZAP（API DAST）

Step 4 結果分類
  → finding-evidence-standard.md（candidate → confirmed 標準）
  → ai-scan-false-positive-patterns.md（誤報過濾）
  → severity-loss-model.md（嚴重度排序）

Step 5 回寫知識庫
  → rules-registry.md（新增 RULE-*）
  → 對應的 *-patterns.md（新增 PAT-*）
  → attack-regression-corpus.md（新增 CORP-*）
```

### 2.5 新 QA 工程師入門（建議讀取順序）

```
Week 1：業務理解
  Day 1: swag-domain-glossary.md（業務術語）
  Day 2: money-flow-map.md（金流路徑）
  Day 3: swag-bug-patterns.md（主要 Bug 模式，先讀概述和 P0/P1 等級）

Week 2：博弈與支付
  Day 1: gambling-game-patterns.md
  Day 2: payment-gateway-patterns.md
  Day 3: streaming-platform-patterns.md

Week 3：工具與流程
  Day 1: qa-automation-patterns.md（Robot Framework / Playwright 最佳實踐）
  Day 2: rules-registry.md（靜態掃描規則速覽）
  Day 3: payment-checklist.md（支付 PR 審查清單）

Week 4：進階防禦
  Day 1: oss-debug-security-loop.md（工具整合）
  Day 2: financial-security-patterns.md（安全威脅模式）
  Day 3: finding-evidence-standard.md（Finding 品質標準）
```

---

## 三、三層防線對照

| 防線層次 | 說明 | 主要知識庫檔案 |
|---------|------|--------------|
| 特徵比對（已知寫法） | 靜態規則掃描已知的錯誤模式 | swag-bug-patterns、gambling-game-patterns、payment-gateway-patterns、rules-registry |
| 業務語意（攻擊面分析） | 分析金流路徑、授權邊界、數值域 | money-flow-map、authorization-ownership-matrix、value-authority-sanitizer-registry |
| 不變量（未知後果的網） | 斷言系統在任何情況下都應成立的性質 | financial-invariants、property-test-catalog、persistence-consistency-controls |

---

## 四、一致性檢查

```
[ ] 每個 file_id 在本表唯一，且實體檔案存在
[ ] 每個檔案的 frontmatter file_id 與本表一致
[ ] 所有 RULE-* 引用 → rules-registry.md 存在對應規則
[ ] 所有 PAT-* 引用 → 對應的 *-patterns.md 存在對應模式
[ ] payment-checklist.md 中的每個檢查項對應至少一條 RULE-*
[ ] 新增的 *-patterns.md 已加入本索引
[ ] 已棄用的模式庫已從索引中移除或標記棄用
```

> 版本：2.0（SWAG QA 版）· 更新日期：2026-06-05
> 重大變更：新增 SWAG 特定業務知識庫（gambling/payment/streaming/qa-automation-patterns），
> 新增 payment-checklist（取代舊版 settlement-checklist 的 Python 場景），
> rules-registry 全面改為 SWAG 業務規則（GAM/PAY/CRED/LIVE/SEC/QA 分類）
