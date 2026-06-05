---
file_id: oss-debug-security-loop
kind: reference
status: active
schema_version: 1.0
last_reviewed: 2026-05-18
stale_after_days: 180
owner: knowledge-writer-agent
external_refs: ["Trivy", "Semgrep", "CodeQL", "OSV-Scanner", "Gitleaks", "ZAP", "Nuclei", "Jazzer"]
---

# GitHub 高星 Debug / 漏洞閉環整合清單

> 適用：Java / SpringBoot / 金融交易系統
> 目的：補強目前以金融規則與靜態知識庫為主的模組，加入高覆蓋率的開源 DevSecOps 掃描閉環
> 星數與描述查核日期：2026-05-18

---

## 何時讀取這份清單

當任務符合以下任一情境時，除了既有三份知識庫，必須同步讀取本檔：

- 要做「全專案」漏洞盤點，而不是只看單一程式碼片段
- 要建立 PR / nightly / release 的自動化掃描閉環
- 要補入 GitHub 高星專案，擴大 DETECT 與 VERIFY 的覆蓋面
- 要交叉比對 SAST、SCA、Secrets、DAST、Fuzzing、供應鏈風險

---

## 建議納入的高星專案

| 專案  | 主要能力 | 適合掛在哪個 Stage | 為什麼適合本模組 |
|------|------------|----------|---------------------|------------------|
| `aquasecurity/trivy` | 容器、依賴、設定錯誤、Secrets、SBOM | DETECT / VERIFY | 一支工具覆蓋 repo、image、IaC，適合 release gate |
| `projectdiscovery/nuclei` | Template-based 漏洞探測、HTTP/API/infra 驗證 | VERIFY / GUARD | 適合對 staging / shadow 環境做弱點驗證 |
| `gitleaks/gitleaks` | Git 歷史與工作目錄 secrets 掃描 | DETECT | 補齊目前模組未覆蓋的憑證外洩風險 |
| `zaproxy/zaproxy` | Web / API DAST 掃描 | VERIFY | 適合驗證登入、權限、輸入驗證、常見 Web 弱點 |
| `semgrep/semgrep`  | 規則式 SAST、易於自訂規則 | DETECT / RECYCLE | 很適合把金融知識庫規則快速落成 repo 規則 |
| `github/codeql`  | 語意型資料流 / taint SAST | DETECT / RECYCLE | 適合抓跨檔、跨層資料流與高風險 sink |
| `google/osv-scanner`  | 開源依賴漏洞掃描與修補建議 | DETECT / VERIFY | 對 Maven / Java 依賴很直接，適合 release 前檢查 |
| `ossf/scorecard`  | 開源專案供應鏈安全健康分數 | TRIAGE / GUARD | 適合評估第三方依賴與外部套件引入風險 |
| `CodeIntelligenceTesting/jazzer`  | JVM coverage-guided fuzzing | VERIFY / RECYCLE | 雖然星數較低，但對 Java 高價值邏輯的異常輸入覆蓋很強 |

---

## 導入原則

### 1. 不追求單一神兵

沒有任何一個專案能同時完整覆蓋：

- 程式語意 Bug
- 依賴漏洞
- Secrets 外洩
- API / Web 弱點
- 執行期輸入邊界
- 供應鏈風險

因此本模組應使用「分層交叉掃描」，而不是只新增一個工具名稱。

### 2. 金融系統優先順序

對金融結算系統，優先順序應為：

1. `CodeQL` / `Semgrep` / `SpotBugs`：抓程式語意與規則違反
2. `Gitleaks`：先擋憑證、私鑰、內部 token 外洩
3. `OSV-Scanner` / `Trivy`：處理依賴與部署層漏洞
4. `ZAP` / `Nuclei`：驗證 API / Web 暴露面
5. `Jazzer`：壓測高風險 parser / calculator / settlement edge cases

### 3. 先把結果收斂成可回寫的規則

每次掃描發現都要回寫成：

- 新的 `PAT-*` 模式
- 新的 `RULE-*` 規則
- 新的驗收案例
- 新的 false positive 抑制條件

否則只是把工具數量變多，不算閉環。

---

## 建議的全方位閉環

### Stage 1 — DETECT

至少跑四類掃描：

| 類型 | 推薦工具 | 目標 |
|------|----------|------|
| 程式語意 / 資料流 | `CodeQL` | SQL Injection、路徑穿越、不安全反序列化、taint flow |
| 規則式 SAST | `Semgrep` + `semgrep-rules` | 快速把金融規則、冪等規則、自訂模式轉成可執行掃描 |
| Secrets | `Gitleaks` | API key、私鑰、JWT secret、內部 token |
| 依賴 / 映像 / 設定 | `OSV-Scanner` + `Trivy` | Maven 漏洞、容器弱點、IaC misconfig |

### Stage 2 — TRIAGE

把 DETECT 的結果收斂成同一份風險矩陣：

- `CodeQL HIGH` 或 `ZAP High` 直接至少 P1
- 涉及入帳、扣款、權限繞過、任意金額操作者直接 P0
- `Gitleaks` 發現有效憑證視同緊急事件處理
- `Scorecard` 用於第三方套件或外部專案導入前評估，不直接當漏洞結論

### Stage 3 — FIX

修復時要同步做兩件事：

- 寫程式修正
- 補工具規則，避免同類問題再次漏網

建議對應：

- `Semgrep`：金融規則、BigDecimal、冪等鍵、危險 API pattern
- `CodeQL`：跨方法、跨檔案資料流規則
- `SonarQube`：PR quality gate 與維護性問題

### Stage 4 — VERIFY

驗收不要只跑單元測試，還要跑外部驗證：

| 驗收類型 | 推薦工具 | 範例 |
|----------|----------|------|
| API / Web 動態掃描 | `ZAP` | 登入繞過、XSS、CSRF、弱 header、OpenAPI 掃描 |
| 已知模板驗證 | `Nuclei` | HTTP misconfig、已知 CVE、暴露端點 |
| 高風險輸入邊界 | `Jazzer` | 金額 parser、匯率 parser、JSON/XML parser、結算計算器 |
| 發版前再掃 | `Trivy` / `OSV-Scanner` | image / pom.xml / lockfile 二次確認 |

### Stage 5 — GUARD + RECYCLE

RECYCLE 階段新增四種回寫：

1. 把 `Semgrep` / `CodeQL` 命中的真實案例寫回 `financial-bug-patterns.md`
2. 把 false positive 條件寫回 `rules-registry.md`
3. 把 `ZAP` / `Nuclei` 的弱點驗證案例轉成 regression checklist
4. 把 `Jazzer` 產生的 crash input 固化成單元測試或 regression corpus

---

## 與目前模組的最小整合方案

若你只想先補最有價值的一輪，優先加入以下閉環：

### 基礎版

- `CodeQL`：補跨檔資料流與安全 sink
- `Semgrep`：把金融規則快速落地
- `Gitleaks`：補 secrets
- `OSV-Scanner`：補 Java 依賴漏洞

### 進階版

- `Trivy`：補映像與部署設定
- `ZAP`：補 API / Web DAST
- `Jazzer`：補高風險 Java fuzzing

### 守門版

- `SonarQube`：PR Gate 與趨勢治理
- `Scorecard`：第三方依賴 / 外部專案採納前評估

---

## 對本專案最重要的補強點

目前模組已經很強在：

- 金融規則
- 冪等性與結算思維
- 知識庫回寫

但相對缺少：

- Secrets 掃描
- 第三方依賴與容器弱點
- API / Web 動態掃描
- JVM fuzzing
- 對外部開源專案的供應鏈健康評估

因此補強重點應放在：

1. `Semgrep + CodeQL` 補靜態語意廣度
2. `Gitleaks + OSV-Scanner + Trivy` 補供應鏈與部署面
3. `ZAP + Nuclei + Jazzer` 補驗收面與執行期弱點

---

## 來源

- `aquasecurity/trivy` — https://github.com/aquasecurity/trivy
- `projectdiscovery/nuclei` — https://github.com/projectdiscovery/nuclei
- `gitleaks/gitleaks` — https://github.com/gitleaks/gitleaks
- `zaproxy/zaproxy` — https://github.com/zaproxy/zaproxy
- `semgrep/semgrep` — https://github.com/semgrep/semgrep
- `SonarSource/sonarqube` — https://github.com/SonarSource/sonarqube
- `github/codeql` — https://github.com/github/codeql
- `google/osv-scanner` — https://github.com/google/osv-scanner
- `ossf/scorecard` — https://github.com/ossf/scorecard
- `CodeIntelligenceTesting/jazzer` — https://github.com/CodeIntelligenceTesting/jazzer

---

## 6. 偵測指標與有效性衡量 (Detection Metrics)

> 用於衡量整個 Debug-Hunter 框架的表現。

| 指標名稱 | 定義 | 目標值 |
| :--- | :--- | :--- |
| **MTTD (Mean Time to Detect)** | 從代碼提交到發現 Finding 的平均時間 | < 10 分鐘 |
| **MTTR (Mean Time to Reproduce)** | 從 Finding 發現到生成有效 PoC 的平均時間 | < 30 分鐘 |
| **Precision (精確率)** | 確認為漏洞的 Finding / 總 Finding 數 | > 85% |
| **Recall (召回率)** | 發現的已知 Bug 數 / 總已知 Bug 數 | > 95% |
| **FP Rate (誤報率)** | 誤報數 / 總 Finding 數 | < 15% |

**持續改進循環 (Feedback Loop)**:
1. 每日分析誤報 (False Positives)，將其提取為 `ai-scan-false-positive-patterns.md`。
2. 每月更新 `financial-bug-patterns.md`，納入新生業務場景。
