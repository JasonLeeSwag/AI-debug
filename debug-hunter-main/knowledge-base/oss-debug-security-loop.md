---
file_id: oss-debug-security-loop
kind: reference
status: active
schema_version: 2.0
last_reviewed: 2026-06-05
stale_after_days: 180
owner: swag-qa-team
external_refs: ["bandit", "semgrep", "eslint-security", "safety", "pip-audit", "npm-audit",
                "gitleaks", "trivy", "zaproxy", "nuclei", "hypothesis", "robocop", "pytest-cov"]
---

# SWAG QA 開源工具整合清單（Python / JavaScript 技術堆疊）

> 適用：Python（FastAPI/Django）+ JavaScript/React（JSX）+ Flutter Web + Robot Framework + Playwright + Appium
> 目的：為 SWAG 平台（swag.live）QA 部門建立完整的 DevSecOps 掃描閉環，從博弈計算到支付回調，覆蓋所有核心業務路徑。
> 更新日期：2026-06-05

---

## 一、何時讀取（觸發情境）

當任務符合以下任一情境時，除了既有業務模式知識庫，必須同步讀取本檔：

| 情境 | 說明 |
|------|------|
| 全專案漏洞盤點 | 不只是看單一程式碼片段，需要跑整個 repo 掃描 |
| 建立 CI/CD 掃描閉環 | PR / nightly / release 的自動化安全掃描設定 |
| 新功能上線前安全驗收 | 支付功能、博弈新遊戲、直播新功能上線前 |
| 依賴漏洞排查 | requirements.txt 或 package.json 有高危漏洞告警 |
| Secrets 洩漏懷疑 | 懷疑 API Key、支付平台 Secret 被提交進 Git |
| QA 腳本品質審查 | Robot Framework / Playwright 測試腳本品質改善 |
| 博弈或支付模組重構 | 高風險業務邏輯重寫後的全面驗收 |

---

## 二、建議納入的工具（針對 Python/JS 技術堆疊）

| 工具 | 主要能力 | 適合掛在哪個 Stage | 為什麼適合 SWAG | 安裝指令 |
|------|---------|-----------------|----------------|---------|
| **Bandit** | Python SAST | DETECT | 偵測 Python 安全問題：crypto 弱點（B311 random 模組）、SQL injection（B608）、OS 命令注入（B602）、硬編碼密碼（B105/B106） | `pip install bandit` |
| **Semgrep** | 多語言 SAST，規則可自訂 | DETECT / RECYCLE | 快速落地 SWAG 業務規則：博弈 RNG 濫用、float 計算點數、支付回調驗簽缺失、IDOR 漏洞；規則直接從 rules-registry.md 轉換 | `pip install semgrep` |
| **ESLint + eslint-plugin-security** | JavaScript/JSX SAST | DETECT | React/JSX 前端安全：detect-non-literal-regexp、detect-eval-with-expression、no-unused-vars；適合掃描前端支付表單和 WebSocket 打賞代碼 | `npm install --save-dev eslint eslint-plugin-security` |
| **Safety / pip-audit** | Python 依賴漏洞掃描 | DETECT / VERIFY | 掃描 requirements.txt 中的已知 CVE；pip-audit 整合 OSV 資料庫，更新更快；適合每次 PR 和 release 前執行 | `pip install safety pip-audit` |
| **npm audit / Snyk** | JavaScript 依賴漏洞掃描 | DETECT / VERIFY | 掃描 package.json 中的前端依賴漏洞；Snyk 提供更詳細的修復建議和 PR 自動修復 | `npm audit` / `snyk test` |
| **Gitleaks** | Git 歷史與工作目錄 Secrets 掃描 | DETECT | 掃描 Git 歷史中是否有 ECPay HashKey/HashIV、支付寶 AppSecret、微信支付 API Key、JWT Secret 等被意外提交 | `brew install gitleaks` |
| **Trivy** | 容器/IaC 掃描 | VERIFY | 掃描 Docker image 的 OS 漏洞和依賴漏洞；掃描 Kubernetes YAML 和 Terraform 設定錯誤；適合 release gate | `brew install trivy` |
| **Playwright + OWASP ZAP** | Web DAST（動態應用安全測試） | VERIFY | 動態掃描 swag.live API：認證繞過、IDOR、XSS、未驗證的支付回調端點；Playwright 驅動 ZAP 的 Spider 模式掃描需登入的頁面 | ZAP: `brew install zaproxy` |
| **Nuclei** | 模板式弱點驗證 | VERIFY | 使用社群模板驗證已知 CVE 和常見設定錯誤；適合驗證支付回調端點是否有 SSRF、支付頁面是否有 XSS 等已知弱點 | `go install github.com/projectdiscovery/nuclei/v3/cmd/nuclei@latest` |
| **Hypothesis** | Python 屬性測試（Property-Based Testing） | VERIFY | 自動生成邊界輸入測試博弈計算（賠率邊界）、點數計算（精度邊界）、支付金額（分/元換算）等；比人工邊界測試更全面 | `pip install hypothesis` |
| **Robocop** | Robot Framework 程式碼 Linter | DETECT | 掃描 Robot Framework 測試腳本品質：禁止 Sleep 等待（W0501）、缺少 Teardown（W0601）、關鍵字命名規範 | `pip install robotframework-robocop` |
| **pytest-cov** | Python 測試覆蓋率 | VERIFY | 確保支付回調、點數計算、博弈結算等關鍵路徑有足夠的單元測試覆蓋；目標覆蓋率：核心業務路徑 > 90% | `pip install pytest-cov` |

---

## 三、導入原則（SWAG 特定）

### 3.1 金融/點數系統優先

SWAG 的核心商業模式建立在點數流通之上，金融安全是最高優先：

1. **Bandit + Semgrep**：抓 Python 程式語意與 SWAG 業務規則違反
   - 重點：random 模組在博弈中的濫用（RULE-GAM-001）
   - 重點：float 計算點數（RULE-CRED-001）
2. **Gitleaks**：先擋支付平台憑證外洩
   - 高優先：ECPay HashKey/HashIV、支付寶 AppSecret、微信支付 APIKey
3. **ESLint Security**：前端年齡驗證不能只在前端（RULE-LIVE-003）
4. **Safety / pip-audit + npm audit**：處理依賴漏洞
5. **ZAP + Playwright**：驗證 API 暴露面
6. **Hypothesis**：壓測博弈計算和點數計算邊界條件

### 3.2 支付回調簽章驗證是最高優先

支付回調驗簽缺失（RULE-PAY-001）是 CRITICAL 等級，列為 CI block 條件：

```yaml
# .semgrep/payment-callback-rules.yaml
rules:
  - id: swag-ecpay-callback-no-verify
    severity: ERROR
    # ... 詳細規則見 rules-registry.md RULE-PAY-001
  - id: swag-alipay-callback-no-verify
    severity: ERROR
  - id: swag-wxpay-callback-no-verify
    severity: ERROR
```

### 3.3 結果必須回寫知識庫

每次掃描發現必須回寫，否則只是工具數量增加，不是真正的閉環：

- 新的 `PAT-*` 模式 → 對應的 `*-patterns.md`
- 新的 `RULE-*` 規則 → `rules-registry.md`
- 新的回歸測試案例 → `attack-regression-corpus.md`
- 新的誤報抑制條件 → `ai-scan-false-positive-patterns.md`

---

## 四、建議的全方位閉環

### Stage 1 DETECT（靜態掃描）

| 類型 | 推薦工具 | SWAG 重點掃描目標 |
|------|---------|-----------------|
| Python SAST | Bandit | `random` 在博弈模組（B311）、SQL f-string 拼接（B608）、硬編碼憑證（B105） |
| 多語言 SAST | Semgrep + SWAG 自訂規則 | 支付回調驗簽、float 計算點數、IDOR 漏洞、年齡驗證缺失 |
| JS/JSX SAST | ESLint + eslint-plugin-security | 前端年齡驗證、WebSocket 消息處理、eval 使用 |
| Secrets 掃描 | Gitleaks | ECPay/支付寶/微信支付 API Key、JWT Secret、資料庫連線字串 |
| Python 依賴 | Safety / pip-audit | requirements.txt 高危漏洞（特別是 web framework、crypto 相關套件） |
| JS 依賴 | npm audit | package.json 高危漏洞（特別是支付 SDK、認證套件） |
| Robot 品質 | Robocop | Sleep 等待（W0501）、Teardown 缺失（W0601）、命名規範 |

### Stage 2 TRIAGE（風險矩陣）

把 DETECT 的結果按以下優先順序收斂：

| 等級 | 條件 | 處理方式 |
|------|------|---------|
| P0（立即封 PR） | 支付回調驗簽缺失；IDOR 漏洞；Gitleaks 發現有效憑證 | 立即封 PR，修復後才能合併 |
| P1（24 小時內修復） | float 計算點數/賠率；年齡驗證只在前端；SQL 注入 | 當 Sprint 內修復 |
| P2（72 小時內修復） | 冪等保護缺失；分潤計算不守恆；依賴漏洞（Medium） | 下個 Sprint 優先排入 |
| P3（排期修復） | Robocop 警告；測試覆蓋率不足；低危依賴漏洞 | 技術債排期處理 |

- Gitleaks 發現有效憑證：視同緊急事件，立即輪替所有相關憑證
- Bandit HIGH / Semgrep ERROR：至少 P1
- 涉及充值入帳、扣款、博弈賠付：直接 P0

### Stage 3 FIX（修復 + 補規則）

修復時同步做兩件事：

1. **修程式碼**：按 rules-registry.md 中的修復範例
2. **補規則**：防止同類問題再次漏網
   - Semgrep：轉化為 `.semgrep/swag-*.yaml` 規則文件
   - Robocop：自訂規則或配置 `robocop.cfg`
   - ESLint：自訂規則或調整 `.eslintrc`

### Stage 4 VERIFY（動態驗證）

| 驗收類型 | 推薦工具 | SWAG 重點驗收場景 |
|---------|---------|----------------|
| API DAST | Playwright + ZAP | 支付回調端點（未登入能否觸發充值）、打賞 API（IDOR 驗證）、年齡驗證繞過 |
| 已知模板驗證 | Nuclei | HTTP 安全 Header 缺失、開放重定向、常見 CVE |
| 屬性測試 | Hypothesis | 博弈賠率計算邊界（0、負數、極大值）、點數分潤守恆性、微信分/元換算 |
| 覆蓋率確認 | pytest-cov | 支付回調處理 > 95%、點數計算 > 90%、博弈結算 > 90% |
| Release 前 | Trivy | Docker image 漏洞、Kubernetes YAML 設定錯誤 |

### Stage 5 GUARD（CI 守門 + 知識回寫）

**GUARD（CI 配置）**：
```yaml
# .github/workflows/security-scan.yml（示意）
jobs:
  detect:
    steps:
      - name: Bandit Python SAST
        run: bandit -r app/ -ll -ii   # -ll: medium+, -ii: medium+ confidence
      - name: Semgrep SWAG Rules
        run: semgrep --config .semgrep/ --error
      - name: Gitleaks Secrets
        run: gitleaks detect --source . --exit-code 1
      - name: pip-audit
        run: pip-audit --requirement requirements.txt
      - name: npm audit
        run: npm audit --audit-level moderate
      - name: Robocop
        run: robocop --configure LineTooLong:line_limit:120 tests/
```

**RECYCLE（知識回寫）**：
1. Semgrep 命中的真實案例 → 寫回對應的 `*-patterns.md`
2. 誤報條件 → 寫回 `ai-scan-false-positive-patterns.md`
3. ZAP 弱點 → 轉成 `reproduce-scenarios.md` 回歸案例
4. Hypothesis 發現的崩潰輸入 → 固化為單元測試或回歸語料

---

## 五、最小整合方案

### 基礎版（第一週內可完成）

適合剛開始導入的團隊，聚焦最高風險：

```bash
# 安裝
pip install bandit semgrep safety pip-audit robotframework-robocop pytest-cov
npm install --save-dev eslint eslint-plugin-security
brew install gitleaks

# 基礎掃描（加入 Makefile 或 pre-commit hooks）
make security-scan:
    bandit -r app/ -ll -ii -f json -o reports/bandit.json
    semgrep --config .semgrep/ --json > reports/semgrep.json
    gitleaks detect --source . --report-path reports/gitleaks.json
    pip-audit --requirement requirements.txt
    robocop tests/robot/
```

**覆蓋的 RULE**：RULE-GAM-001、RULE-PAY-001（部分）、RULE-CRED-001、RULE-SEC-002（部分）、RULE-SEC-003、RULE-QA-001、RULE-QA-003

### 進階版（第一個月）

補強動態掃描和屬性測試：

```bash
# 新增安裝
pip install hypothesis
pip install zapv2              # ZAP Python Client

# 新增到 CI
hypothesis-based-tests:
    pytest tests/property/ --hypothesis-seed=0 -v

zap-api-scan:
    docker run -t owasp/zap2docker-stable zap-api-scan.py \
        -t http://staging.swag.live/openapi.json \
        -f openapi -r zap-report.html
```

**新增覆蓋的 RULE**：RULE-GAM-002（Hypothesis 精度測試）、RULE-PAY-002（ZAP 金額比對）、RULE-LIVE-003（ZAP 年齡驗證繞過）

### 守門版（全面整合）

全面覆蓋，加入 Release Gate：

```bash
# 新增安裝
brew install trivy nuclei

# Release Gate
trivy image --exit-code 1 --severity HIGH,CRITICAL swag-api:latest
nuclei -target https://staging.swag.live -t nuclei-templates/
pytest --cov=app --cov-fail-under=85   # 核心路徑覆蓋率要求
```

**新增覆蓋**：容器安全、已知 CVE 驗證、測試覆蓋率守門

---

## 六、對 SWAG 最重要的補強點

目前 SWAG QA 知識庫在業務規則方面已很完整：

- 博弈遊戲 RNG、賠率、並發結算
- 點數/分精度計算（Decimal）
- 支付回調驗簽（各平台）
- 冪等保護策略

相對需要補強的面向：

### 優先補強（P0）

1. **Gitleaks**：支付平台 Secret 外洩風險
   - ECPay HashKey/HashIV、支付寶 AppSecret、微信支付 API Key 是高價值目標
   - 建議：加入 pre-commit hook，每次 commit 前掃描

2. **Semgrep 自訂規則落地**
   - rules-registry.md 已有 21 條規則定義，但需要轉成實際可執行的 `.yaml` 規則文件
   - 優先落地：RULE-PAY-001（回調驗簽）、RULE-SEC-001（IDOR）

3. **Hypothesis 屬性測試**
   - 博弈賠率計算（Decimal 精度邊界）
   - 點數分潤守恆性（任意金額的最大餘額法）
   - 微信支付分/元換算（邊界值如 0.01 元 = 1 分）

### 次要補強（P1）

4. **ESLint Security Plugin**
   - 前端 React/JSX 的安全掃描
   - 重點：年齡驗證不在前端強制（配合 RULE-LIVE-003）

5. **pytest-cov 覆蓋率守門**
   - 目前缺乏明確的覆蓋率要求
   - 建議目標：支付回調路徑 > 95%、點數計算 > 90%

6. **Robocop 品質掃描**
   - Robot Framework 測試腳本品質目前依賴人工審查
   - Robocop 可自動化 Sleep 等待和 Teardown 缺失的偵測

### 長期規劃（P2）

7. **ZAP + Playwright 整合**：成人內容的年齡驗證繞過測試
8. **Trivy**：Docker image 和 Kubernetes 設定安全審查
9. **Nuclei**：已知 CVE 的自動化驗證

---

## 七、偵測指標與有效性衡量

| 指標名稱 | 定義 | SWAG 目標值 | 備註 |
|---------|------|-----------|------|
| **MTTD（平均偵測時間）** | 代碼提交到 Finding 發現的平均時間 | < 5 分鐘 | CI 掃描速度要求 |
| **MTTR（平均修復時間）** | Finding 確認到修復合併的時間 | P0: < 4 小時 / P1: < 24 小時 | 依嚴重等級分級 |
| **Precision（精確率）** | 確認為漏洞的 Finding / 總 Finding 數 | > 85% | 防止告警疲勞 |
| **Recall（召回率）** | 發現的已知 Bug / 總已知 Bug 數 | > 95% | 關鍵安全問題不能漏 |
| **FP Rate（誤報率）** | 誤報數 / 總 Finding 數 | < 15% | 誤報過高影響開發效率 |
| **支付回調覆蓋率** | 有驗簽的回調端點 / 全部回調端點 | 100% | CRITICAL：不允許有缺口 |
| **核心業務測試覆蓋率** | 支付/點數/博弈模組的測試覆蓋率 | > 90% | pytest-cov 量測 |
| **Secrets 洩漏率** | Gitleaks 在 main branch 發現的有效 secret 數 | 0 | 零容忍 |
| **規則命中與攔截** | 每條 RULE-* 觸發次數 / 攔截真 Bug 數 | 持續追蹤 | 見 rules-registry.md 健康度表 |
| **回歸覆蓋** | attack-regression-corpus 條目數 / confirmed 漏洞數 | = 1.0 | 每個確認漏洞都有回歸測試 |

**持續改進循環**：
1. 每次 Sprint 結束：分析 Semgrep/Bandit 誤報，更新 `ai-scan-false-positive-patterns.md`
2. 每月：更新 `swag-bug-patterns.md` 和各 `*-patterns.md`，納入新發現的業務場景
3. 每季：重新評估工具有效性，調整覆蓋率目標
4. 每次事故：24 小時內完成事後檢視，產出至少一條新 RULE-* 規則

---

## 八、工具來源與版本參考

| 工具 | GitHub / 官網 | 建議版本 |
|------|-------------|---------|
| Bandit | https://github.com/PyCQA/bandit | >= 1.7.x |
| Semgrep | https://github.com/semgrep/semgrep | >= 1.x |
| ESLint + security plugin | https://github.com/eslint-community/eslint-plugin-security | ESLint >= 8.x |
| Safety | https://github.com/pyupio/safety | >= 3.x |
| pip-audit | https://github.com/pypa/pip-audit | >= 2.x |
| Gitleaks | https://github.com/gitleaks/gitleaks | >= 8.x |
| Trivy | https://github.com/aquasecurity/trivy | >= 0.50.x |
| OWASP ZAP | https://github.com/zaproxy/zaproxy | >= 2.14.x |
| Nuclei | https://github.com/projectdiscovery/nuclei | >= 3.x |
| Hypothesis | https://github.com/HypothesisWorks/hypothesis | >= 6.x |
| Robocop | https://github.com/MarketSquare/robotframework-robocop | >= 5.x |
| pytest-cov | https://github.com/pytest-dev/pytest-cov | >= 4.x |
