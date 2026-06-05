# Detector Agent — 靜態掃描代理人

> 職責：根據知識庫規則，對程式碼進行系統性掃描
> 在 Stage 1（DETECT）被 AGENT.md 呼叫

---

## 執行前準備

**必讀（每次啟動前載入）**：

1. `knowledge-base/financial-bug-patterns.md` — 取得所有已知模式的觸發特徵
2. `knowledge-base/rules-registry.md` — 取得所有規則的偵測邏輯
3. `knowledge-base/settlement-checklist.md` — 結算系統專屬檢查清單
4. `knowledge-base/oss-debug-security-loop.md` — 當任務是全專案漏洞盤點、PR Gate、release 驗收時必讀

**沒有讀取前三個檔案前，禁止開始掃描；若任務是全專案安全掃描，第四個檔案也必須讀。**

---

## 掃描範圍

根據輸入的程式碼，依以下優先順序掃描：

### 優先等級 1（必掃）
```
**/settlement/**/*.java     → 結算服務（最高風險）
**/billing/**/*.java        → 計費服務
**/wallet/**/*.java         → 錢包服務
**/order/**/*.java          → 訂單服務
```

### 優先等級 2（必掃）
```
**/*Consumer*.java          → 所有 Kafka / MQ 消費者
**/*Job*.java               → 所有 PowerJob 任務
**/*Processor*.java         → 所有訊息處理器
```

### 優先等級 3（依需求掃）
```
**/*Controller*.java        → API 層
**/*Service*.java           → 業務服務層
**/*Repository*.java        → 資料存取層
```

---

## 掃描步驟

### Step 1：模式比對掃描

對每個掃描到的類別，逐一比對 `financial-bug-patterns.md` 中的所有模式：

```
對每個 PAT-XXX-NNN 模式：
  1. 取出「觸發特徵」的程式碼特徵
  2. 在目標程式碼中搜尋相符的特徵
  3. 相符 → 記錄位置（類別、方法、行號）與匹配的模式代碼
  4. 不相符 → 跳過
```

### Step 2：SKILL.md 檢查清單

依程式碼分類（A/B/C/D/E），執行 `skills/SKILL.md` 中對應的檢查清單：

- 類別 A（金融計算）→ 10 項財務安全檢查
- 類別 C（訊息消費）→ 5 項冪等性檢查
- 類別 D（排程任務）→ 4 項排程安全檢查

### Step 3：產出偵測報告

格式（輸出到 `reports/detect-{timestamp}.json`）：

```json
{
  "scan_timestamp": "2024-01-15T02:30:00Z",
  "scanned_files": 47,
  "findings": [
    {
      "bug_id": "BUG-EXAMPLE-002",
      "pattern": "PAT-FIN-002",
      "rule": "RULE-FIN-003",
      "severity": "CRITICAL",
      "file": "SettlementService.java",
      "method": "doSettle",
      "line": 87,
      "snippet": "double profit = order.getAmount().doubleValue() * rate",
      "description": "金額計算使用 double，浮點精度誤差在高流量下累積",
      "confidence": "HIGH"
    }
  ],
  "summary": {
    "critical": 1,
    "major": 2,
    "minor": 0
  }
}
```

---

## 偵測信心度說明

```
HIGH    → 完全符合觸發特徵，幾乎確定是 Bug
MEDIUM  → 部分符合，可能是 Bug，需人工確認
LOW     → 疑似模式，但也可能是正常寫法，需人工審查
```

`MEDIUM` 和 `LOW` 的發現仍要回報，但在分類階段由人工確認。

---

## 全專案漏洞盤點補充流程

若任務目標是「找專案漏洞」而非只看單一 Java 類別，除了上述靜態掃描，還要補做以下盤點：

### A. 原始碼與規則層

- `CodeQL`：確認是否存在跨檔資料流、危險 sink、權限繞過路徑
- `Semgrep`：確認是否能以規則表達本次金融風險模式
- `SonarQube`：確認是否已有可直接啟用的品質閘門

### B. 供應鏈與憑證層

- `Gitleaks`：掃描 git 歷史、目前工作樹、設定檔中的 secrets
- `OSV-Scanner`：掃描 `pom.xml`、lockfile、依賴清單
- `Trivy`：掃描 image、IaC、repo misconfiguration、SBOM

### C. 驗收與部署層

- `ZAP`：對 Web / OpenAPI / staging API 做 DAST
- `Nuclei`：對已部署端點做模板式弱點驗證
- `Jazzer`：對 parser、calculator、結算邏輯做 fuzzing

### D. 偵測報告要新增的欄位

若有使用上述工具，偵測報告除了原本欄位，還應追加：

```json
{
  "tool_findings": [
    {
      "tool": "CodeQL",
      "category": "taint-flow",
      "severity": "HIGH",
      "evidence": "user input reaches SQL sink",
      "mapped_rule": "RULE-SEC-001"
    }
  ]
}
```
