---
file_id: MAP
kind: meta
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 90
owner: knowledge-writer-agent
external_refs: []
---

> 本檔為**概念地圖與工作流**；逐檔清單、對應 Stage 與一致性 lint 見 [[KB-INDEX]]。兩者互補。

# 知識庫全局地圖與導航（Knowledge Map & Navigation）

> **Debug-Hunter 核心大腦**。定義了所有知識檔之間的語義連接與偵測工作流。

---

## 1. 知識層級架構 (Knowledge Hierarchy)

### 層級 0：元治理 (Meta-Governance)
- [[knowledge-schema]]: 定義所有檔案的 YAML 格式與入庫門檻。
- [[finding-evidence-standard]]: 定義什麼才算「證據」，如何從候選轉為確認。

### 層級 1：業務基石 (Business Ground-Truth)
- [[money-flow-map]]: 全系統資金匯點 (Sink) 與流向圖。
- [[workflow-state-machine-catalog]]: 訂單、清結算狀態機變更規則。
- [[authorization-ownership-matrix]]: 數據分類與資源歸屬權矩陣。
- [[domain-glossary]]: 金融術語統一標準。

### 層級 2：模式與模型 (Patterns & Models)
- [[financial-invariants]]: 核心守恆定律與不變量。
- [[financial-bug-patterns]]: 業務邏輯類 Bug 模式。
- [[financial-security-patterns]]: 資金安全、IDOR、注入類模式。
- [[severity-loss-model]]: 風險定級與損失量化公式。
- [[threat-catalog]]: 系統威脅模型。

### 層級 3：執行與驗證 (Execution & Verification)
- [[reproduce-scenarios]]: 復現路徑與環境準備模板。
- [[property-test-catalog]]: 基於屬性的測試 (PBT) 生成規則。
- [[attack-regression-corpus]]: 歷史漏洞 PoC 語料庫。
- [[rules-registry]]: 靜態掃描 (Semgrep) 與動態監測規則索引。
- [[settlement-checklist]]: 針對清結算場景的專項核對清單。

---

## 2. 閉環 Debug 工作流 (The Closed-Loop Workflow)

1. **偵測階段 (Detect)**:
   - 調用 `financial-security-patterns` + `rules-registry` 掃描代碼。
   - 參考 `money-flow-map` 定位高風險 Sink。
2. **定性階段 (Triage)**:
   - 使用 `authorization-ownership-matrix` 判定是否越權。
   - 使用 `financial-invariants` 判定是否違反守恆律。
   - 依據 `severity-loss-model` 評定等級。
3. **復現階段 (Reproduce)**:
   - 根據 `reproduce-scenarios` 搭建測試環境。
   - 從 `attack-regression-corpus` 獲取類似 PoC 樣板。
   - 運用 `property-test-catalog` 生成併發/邊界測試。
4. **驗收階段 (Verify)**:
   - 通過 `finding-evidence-standard` 要求的證據鏈。
   - 檢查 `settlement-checklist` 確保無次生風險。
5. **入庫階段 (Persist/RECYCLE)**:
   - 依據 `knowledge-schema` 將新發現的 Pattern 回寫。

---

## 3. 引用完整性矩陣 (Traceability Matrix)

| Pattern 類型 | 必須引用的上游 (Parent) | 必須引用的下游 (Verification) |
| :--- | :--- | :--- |
| **PAT-SEC (安全)** | `INV-*` (不變量) + `MF-*` (金流) | `CORP-*` (PoC) |
| **PAT-BUG (業務)** | `WSM-*` (狀態機) | `PBT-*` (屬性測試) |
| **RULE (規則)** | `PAT-*` (模式) | `finding-evidence-standard` |

---
