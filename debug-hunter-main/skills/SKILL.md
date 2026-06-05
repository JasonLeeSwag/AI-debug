# SKILL.md — 金融系統 Bug 偵測與修復技能

> 適用：金融交易結算系統（範例） · Java · SpringBoot
> 版本：v1.0 · 最後更新：2026-04-14

---

## 何時使用此技能

當你需要：
- 審查金融業務相關的 Java 程式碼
- 偵測結算、計費、入帳、扣款相關的潛在 Bug
- 分析高並發場景下的競態條件
- 設計冪等性保護機制
- 進行事後檢視（Post-mortem）

請在開始分析前，先讀取：
1. `knowledge-base/financial-bug-patterns.md`（已知模式）
2. `knowledge-base/rules-registry.md`（現行規則）
3. `knowledge-base/settlement-checklist.md`（結算清單）
4. `knowledge-base/oss-debug-security-loop.md`（高星開源 debug / 漏洞閉環清單；當任務涉及全專案掃描、GitHub 高星專案整合、漏洞盤點、PR / release gate 時必讀）

---

## 偵測流程（Detection Protocol）

### Step 1：識別程式碼分類

拿到程式碼後，先判斷屬於哪個風險類別：

```
類別 A：金融計算核心（最高風險）
  → 結算、收益計算、手續費、匯率換算
  → 必須執行完整的 10 項財務安全檢查

類別 B：資料存取層（高風險）
  → Repository、DAO、Mapper
  → 重點檢查：鎖定機制、樂觀鎖、狀態機

類別 C：訊息消費（高風險）
  → Kafka Consumer、MQ 監聽器
  → 重點檢查：冪等性、失敗補償、重試機制

類別 D：排程任務（中風險）
  → PowerJob、Spring Scheduler
  → 重點檢查：分散式鎖、分片隔離

類別 E：API 層（中風險）
  → Controller、DTO
  → 重點檢查：參數驗證、防重提交
```

---

### Step 2：執行對應的檢查清單

#### 【類別 A】金融計算 10 項安全檢查

```
[ ] 1. 金額型別：是否全程使用 BigDecimal？（禁止 double / float）
[ ] 2. 比率型別：百分比數值是否有統一的語義單位？（如 25 代表 25%）
[ ] 3. 除法運算：BigDecimal.divide() 是否指定 scale 和 RoundingMode？
[ ] 4. 比較運算：BigDecimal 是否用 compareTo() 而非 equals()？
[ ] 5. 結果邊界：計算結果是否有業務合理性上限校驗？
[ ] 6. null 防護：從資料庫取回的數值是否有 null 檢查？
[ ] 7. 精度損失：是否有隱性的型別轉換（如 int → double）？
[ ] 8. 四捨五入：RoundingMode 的選擇是否符合業務規則？
[ ] 9. 溢位風險：超大金額乘法是否有溢位風險？
[ ] 10. 單位一致：入參、計算、出參的單位（元/分）是否一致？
```

#### 【類別 C】冪等性 5 項檢查

```
[ ] 1. 唯一鍵識別：是否有明確的業務冪等鍵（訂單 ID / 流水號）？
[ ] 2. Redis 防重：是否用 setIfAbsent 做第一層快速攔截？
[ ] 3. DB 狀態機：是否用 CAS 更新（UPDATE ... WHERE status = 'PENDING'）？
[ ] 4. 失敗清理：執行失敗時是否清除 Redis 防重鍵，讓重試能進入？
[ ] 5. 告警機制：重複消費是否有 warn 日誌，便於排查？
```

#### 【類別 D】排程任務 4 項檢查

```
[ ] 1. 分散式鎖：多節點環境下是否有分散式鎖保護？
[ ] 2. 分片隔離：PowerJob 多 Worker 是否有分片鍵隔離資料範圍？
[ ] 3. 重入保護：任務重啟後是否會重複處理已完成的資料？
[ ] 4. 逾時設定：鎖的 TTL 是否大於任務最長執行時間？
```

### Step 2.5：啟用全方位漏洞交叉掃描

若任務範圍不是單一 bug，而是整個專案的 debug / 漏洞盤點，必須依 `knowledge-base/oss-debug-security-loop.md` 補做以下交叉驗證：

```
[ ] 1. CodeQL：是否需要做跨檔案資料流 / taint 分析？
[ ] 2. Semgrep：是否需要把本次發現轉成可重跑規則？
[ ] 3. Gitleaks：是否掃描 secrets / 金鑰 / token 外洩？
[ ] 4. OSV-Scanner：是否掃描 pom.xml / lockfile 的已知漏洞？
[ ] 5. Trivy：是否掃描容器映像、設定錯誤、SBOM？
[ ] 6. ZAP：是否對 staging / test API 做 DAST？
[ ] 7. Nuclei：是否對已部署端點做模板式弱點驗證？
[ ] 8. Jazzer：是否對 parser / calculator / settlement edge cases 做 fuzzing？
[ ] 9. SonarQube：是否需要作為 PR quality gate 或技術債看板？
[ ] 10. Scorecard：若引入外部套件 / 專案，是否檢查其供應鏈健康？
```

原則：

- 金融規則相關問題，不可只依賴通用工具，仍須回到本技能既有清單判讀
- 通用工具命中後，必須轉譯成金融語境的風險說明，而不是只貼工具原始輸出
- 任一外部工具確認為真陽性，最終都必須回寫成 `PAT-*` 或 `RULE-*`

---

### Step 3：輸出偵測報告

每個發現的問題，輸出以下格式：

```markdown
## 🔴 BUG-{序號}：{簡短標題}

**風險等級**：P0 / P1 / P2 / P3
**受影響服務**：{服務名稱}
**Bug 類別**：{數值精度 / 冪等性 / 競態條件 / 事務邊界 / ...}

### 問題描述
{說明 Bug 的具體行為，包含觸發條件}

### 問題程式碼
```java
// 標示出有問題的行
```

### 根因
{說明為什麼系統設計上允許這個 Bug 存在}

### 修復方案
```java
// 修復後的程式碼
```

### 測試案例
```java
// 覆蓋此 Bug 的測試
```

### 知識庫規則
**規則代碼**：RULE-{類別}-{序號}
**規則描述**：{可以被靜態掃描工具實作的規則描述}
```

---

## 修復策略選擇指南

根據根因類型，選擇對應的修復策略：

### 策略 1：值物件封裝（Value Object）
**適用**：數值有隱式語義（如「以最小單位儲存的金額」「放大 N 倍的定點數」）

```java
// 用值物件封裝，杜絕裸數字在計算層流通
Money amount = Money.ofMinorUnit(dbMinorValue);   // DB 以「分」儲存
BigDecimal major = amount.toMajorUnit();          // 轉為「元」再參與計算
```

### 策略 2：狀態機 + 樂觀鎖（CAS）
**適用**：並發修改導致的競態條件

```java
// 只更新符合預期狀態的資料列
int updated = repo.updateStatusIfPending(orderId, PENDING, SETTLING);
if (updated == 0) throw new InvalidStatusException();
```

### 策略 3：雙層冪等保護
**適用**：Kafka 重複消費、重試風暴

```java
// Redis 第一層 + DB 狀態機第二層
Boolean first = redis.setIfAbsent(key, "1", Duration.ofHours(24));
if (!first) return; // 攔截
// 再走 DB CAS 更新
```

### 策略 4：BigDecimal 精確計算
**適用**：金額、比率計算

```java
// 全程 BigDecimal，明確指定 scale 和 RoundingMode
BigDecimal result = a.multiply(b)
    .setScale(8, RoundingMode.HALF_DOWN);
```

### 策略 5：業務合理性守衛
**適用**：作為最後一道防線，即使計算邏輯有 Bug 也能攔截

```java
// 結算結果上限校驗
BigDecimal impliedRate = profit.divide(amount, 6, HALF_UP);
if (impliedRate.compareTo(MAX_PROFIT_RATE) > 0) {
    alertService.sendCriticalAlert(...);
    throw new SettlementValidationException("收益率超出上限");
}
```

### 策略 6：規則化回寫（Semgrep / CodeQL）
**適用**：同類問題曾重複出現，或已確認可被靜態特徵辨識

```java
// 修完 bug 後，不只補 code，也補規則
// 例：禁止裸用以最小單位儲存的金額直接參與顯示/計算
BigDecimal major = Money.ofMinorUnit(dbMinorValue).toMajorUnit();
```

要求：

- 可用語法型規則表達者，優先補 `Semgrep`
- 涉及跨方法 / 污染流者，補 `CodeQL`
- 規則名稱需能對應 `RULE-*` 編號

### 策略 7：多層驗收守門（OSV / Trivy / ZAP / Jazzer）
**適用**：修復涉及 release、API 暴露面、依賴升級、解析器或高風險輸入邊界

```java
// 驗收不只看單元測試 pass，還要確認：
// 1. 漏洞掃描無新增 critical/high
// 2. DAST 無新增高風險端點
// 3. fuzz corpus 不再打出 crash
```

要求：

- release 前至少做一次依賴 / image 二次掃描
- API 類修復需補動態驗證
- parser / calculator 類修復需評估是否補 fuzzing

---

## 事後檢視（Post-mortem）模板

每次 P0 / P1 Bug 修復後，必須填寫：

```markdown
# 事後檢視報告 — {Bug 標題}

**日期**：{YYYY-MM-DD}
**等級**：{P0 / P1}
**影響時間**：{開始} ~ {結束}（共 {N} 分鐘）
**影響範圍**：{受影響的使用者數 / 訂單數 / 金額}

## 事件時間軸
| 時間 | 事件 |
|------|------|
| HH:MM | 系統出現異常告警 |
| HH:MM | On-call 接收到告警 |
| HH:MM | 確認根因 |
| HH:MM | 開始部署修復 |
| HH:MM | 服務恢復正常 |

## 根本原因
{5-Why 分析}

## 修復措施
{本次採取的修復行動}

## 預防措施
{未來如何避免同類問題}

## 知識庫更新
- 新增規則：{RULE-XXX-NNN}
- 更新模式：{Pattern-XX}
```
