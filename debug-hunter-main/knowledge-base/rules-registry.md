---
file_id: rules-registry
kind: registry
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 180
owner: knowledge-writer-agent
external_refs: []
---

# 靜態掃描規則登錄

> 檔案路徑：knowledge-base/rules-registry.md
> 用途：將知識庫中的 Bug 模式轉化為可執行的靜態掃描規則
> 更新時機：每次事後檢視後，由 `agents/knowledge-writer.md` 自動追加
> 工具對應：SpotBugs 自訂規則 / SonarQube Custom Rules / PR Review Checklist

---

## 規則分類

```
RULE-FIN-XXX  → 金融計算相關
RULE-CON-XXX  → 並發與一致性相關
RULE-SCH-XXX  → 排程任務相關
RULE-BIZ-XXX  → 業務邏輯相關
RULE-MON-XXX  → 監控告警相關
RULE-SEC-1xx  → 財務安全 / 舞弊相關（taint source→sink，v2.0 新增）
```

---

## 規則清單

### RULE-FIN-003：金融欄位禁止使用 double/float

**來源模式**：PAT-FIN-002
**嚴重等級**：CRITICAL

**違規特徵**：
```
欄位名稱符合 /amount|price|fee|profit|balance|rate|value/ (忽略大小寫)
且欄位型別為 double 或 float 或 Double 或 Float
```

**PR Review 檢查點**：
```
☑ 所有金融相關欄位（金額、比率、餘額、手續費）使用 BigDecimal
☑ 沒有 .doubleValue() 轉換後再計算的代碼
```

---

### RULE-FIN-004：BigDecimal 比較必須使用 compareTo()

**來源模式**：PAT-FIN-003
**嚴重等級**：MAJOR

**違規特徵**：
```
BigDecimal 型別的變數
呼叫 .equals() 方法
```

**SonarQube 已有對應規則**：`java:S2244`（確認已啟用）

---

### RULE-CON-001：Kafka 消費者必須有冪等保護

**來源模式**：PAT-CON-001
**嚴重等級**：CRITICAL

**違規特徵**：
```
類別有 @KafkaListener 或 @RabbitListener 等訊息監聽器標注
且
方法體內沒有 setIfAbsent / idempotent / duplicate 相關呼叫
且
方法名稱或呼叫的方法名稱包含 settle / credit / debit / transfer / charge
```

**PR Review 檢查點**：
```
☑ 所有涉及資金操作的 MQ 消費者有 Redis setIfAbsent 防重
☑ 有 DB 狀態機作為第二層保護
☑ 業務失敗時 Redis key 會被清除，允許重試
```

---

### RULE-CON-002：@Transactional 禁止加在 private 方法

**來源模式**：PAT-CON-002
**嚴重等級**：MAJOR

**違規特徵**：
```
方法修飾符為 private
且有 @Transactional 標注
```

**SonarQube 已有對應規則**：`java:S2229`（確認已啟用）

---

### RULE-CON-003：@Transactional 必須指定 rollbackFor

**來源模式**：PAT-CON-002
**嚴重等級**：MAJOR

**違規特徵**：
```
@Transactional 標注
且 rollbackFor 屬性未設定
且方法宣告有 throws Exception 或非 RuntimeException
```

**修復範例**：
```java
// ✅ 正確
@Transactional(rollbackFor = Exception.class)
public void settle(Long orderId) throws SettlementException { ... }
```

---

### RULE-BIZ-001：結算結果必須通過業務合理性校驗

**來源模式**：PAT-BIZ-002
**嚴重等級**：CRITICAL

**違規特徵**：
```
方法名稱包含 'settle' 或 'settlement'
且
包含對 walletService.credit() 或 walletService.debit() 的呼叫
且
呼叫前沒有 settlementGuard.validate() 或等效的合理性校驗
```

**PR Review 檢查點**：
```
☑ 所有結算流程在入帳前都通過 SettlementGuard.validate()
☑ 最大收益率設定已在 Nacos 配置，且有預設安全值
☑ 單筆賠付上限已設定
```

---

---

### RULE-CON-004：批量讀取錢包後的更新必須有行鎖或樂觀鎖保護

**來源模式**：PAT-CON-004
**嚴重等級**：CRITICAL

**違規特徵**：
```
呼叫 batchFindWallets 或等效的批量錢包讀取方法
且
後續有 batchUpWallets 或等效的批量覆蓋更新
且
中間沒有 FOR UPDATE / version 欄位比對 / SELECT FOR UPDATE
且
上游有 flatMap / parallel 等並發操作（並發度 > 1）
```

**SonarQube 自訂規則描述**：
```
Rule: Wallet batch read followed by bulk overwrite without concurrency control
When: batchFindWallets() is called in a reactive/parallel context
      AND followed by batchUpWallets() or updateWallet()
      AND no version field or FOR UPDATE found in the call chain
Severity: BLOCKER
Tag: financial-safety, concurrency
```

**PR Review 檢查點**：
```
☑ batchFindWallets 對應的 SQL 有 FOR UPDATE（悲觀鎖）
  或 updateWallet/batchUpWallets 的 SQL 有 WHERE version=? AND id=?（樂觀鎖）
☑ 若使用樂觀鎖，更新 0 筆時有加入 retryIds 重試機制
☑ 並發度（flatMap 第二參數）已知曉且有對應的鎖策略
```

---

### RULE-BIZ-002：結算依賴的外部 API 失敗必須拋出例外，禁止靜默返回預設值

**來源模式**：PAT-BIZ-003
**嚴重等級**：CRITICAL

**違規特徵**：
```
方法名稱包含 fetch / get / query / retrieve 等查詢動詞
且 呼叫外部 API（非本服務）取得價格、比率、行情等計算依賴數據
且 API 回傳非成功狀態時，返回 BigDecimal.ZERO / 0 / null / 空物件
且 返回值後續直接參與結算計算（而非只用於展示）
```

**修復範例**：
```java
// ✅ 正確：外部 API 失敗必須拋出例外
if (resp.getCode() != 1) {
    throw new ExternalApiException(
        "行情 API 失敗，禁止以預設值繼續結算: " + resp);
}
// 額外校驗返回值的合理性
if (price == null || price.compareTo(BigDecimal.ZERO) <= 0) {
    throw new InvalidPriceException("行情價格異常（≤0）: " + price);
}
```

**PR Review 檢查點**：
```
☑ 所有取得行情價格的方法，失敗時拋出例外（不靜默返回 ZERO）
☑ 所有取得收益率/匯率的方法，有對返回值做正數校驗
☑ 上層的 onErrorResume 不會吞掉這些例外（需讓結算流程停止）
```

---

### RULE-CON-005：有重試機制的流程，失敗時的狀態修改必須是冪等的

**來源模式**：PAT-CON-005
**嚴重等級**：MAJOR

**違規特徵**：
```
方法名稱含 changeType / toggle / flip / switch 等切換語意
且 在 catch 區塊或 onErrorResume 中被呼叫
且 上游或同層有 retryWhen / Retry.backoff / @Retryable 重試設定
```

**修復範例**：
```java
// ✅ 正確：單向冪等標記，無論呼叫幾次結果相同
public void markError() {
    this.resultType.set(1); // set 不是 toggle
}

// 使用方：
} catch (Exception e) {
    countDto.markError();   // 冪等，重試 N 次都是 set(1)
    throw e;
}
```

**PR Review 檢查點**：
```
☑ 有 retryWhen / Retry 的流程，catch 區塊內的狀態修改是單向設定（非切換）
☑ onErrorResume（最終失敗處理）有傳入 ex 物件到 log.error()
```

---

### RULE-CON-006：批次 Kafka Listener 使用 hasError 不 ACK 時，每筆訊息必須有獨立冪等鍵

**來源模式**：PAT-CON-001 變體 B
**嚴重等級**：CRITICAL

**違規特徵**：
```
@KafkaListener containerFactory 為 BATCH 型（批次消費）
且 使用 AtomicBoolean hasError 控制整批 ack / not-ack
且 單筆訊息（runner / order）的處理沒有 Redis setIfAbsent 或等效防重
且 業務操作涉及金額入帳或餘額修改
```

**修復範例**：
```java
// ✅ 每筆 Runner 處理前加獨立冪等鍵
String idempotentKey = "settle:runner:" + runner.getId();
Boolean isFirst = redisTemplate.opsForValue()
    .setIfAbsent(idempotentKey, "processing", Duration.ofHours(24));
if (Boolean.FALSE.equals(isFirst)) {
    return Mono.empty(); // 此 Runner 已在處理中或已完成，跳過
}
```

**PR Review 檢查點**：
```
☑ 批次 Listener 中，每筆業務單元（Runner / Order）有獨立的 Redis 冪等鍵
☑ 成功後將 Redis key 改為 "settled" 且延長 TTL（7 天）
☑ 失敗後清除 Redis key，允許 Kafka 重送時再次進入
```

---

### RULE-CON-007：金流狀態躍遷必須用 CAS / 樂觀鎖

**來源模式**：PAT-WF-001（workflow-state-machine-catalog.md）
**嚴重等級**：CRITICAL · **引擎**：CodeQL / 人工

**違規特徵**：
```
對訂單/提款/退款等金流實體呼叫 setStatus / 狀態寫入
且 更新無 WHERE status=<expected>（CAS）或 version 樂觀鎖
且 存在並發或重送可達路徑
```

**修復範例**：
```java
int updated = orderMapper.casStatus(orderId, PENDING, SETTLING); // WHERE status='PENDING'
if (updated == 0) throw new InvalidStatusException(); // 已被他人躍遷，拒絕
```

**對應不變量**：INV-ST-05（狀態單調）、INV-T-02（冪等）

---

## 財務安全/舞弊規則（v2.0 · taint source→sink 驅動）

> 對應 `financial-security-patterns.md` 的 PAT-SEC-1xx。引擎以 CodeQL / Semgrep 的 **taint tracking** 為主：
> 定義 source（請求 / MQ / 外部 API）、sink（資金操作 / 動態 SQL）、sanitizer（歸屬 / 數值域 / 授權 / 簽章 / 原子性），
> 任一 source→sink 路徑缺對應 sanitizer 即報。

### RULE-FIN-006：多資產精度禁止硬編碼 scale
**來源模式**：PAT-FIN-005 · **嚴重等級**：CRITICAL · **引擎**：CodeQL
```
setScale(<常數>, ...) 出現在金額計算路徑
且 scale 非來自資產中繼資料（assetMeta.getScale / coinConfig）
```
**對應不變量**：INV-TXN-02

### RULE-FIN-007：分配/拆分後必須校驗總和守恆
**來源模式**：PAT-FIN-006 · **嚴重等級**：CRITICAL · **引擎**：人工 + 不變量
```
迴圈內對 total 依比例分配並逐項 setScale 入帳
且 迴圈後無「Σ各方 == total」斷言或殘差歸位
```
**對應不變量**：INV-TXN-05 / INV-ST-03

### RULE-FIN-008：時間戳單位與時區一致性
**來源模式**：PAT-FIN-007 · **嚴重等級**：MAJOR · **引擎**：Semgrep
```
裸 long 時間戳跨方法傳遞（ms/s 不明）
或 用 LocalDate.now() / 系統預設時區計算結算日
```

### RULE-FIN-009：long 金額溢位防護
**來源模式**：PAT-FIN-008 · **嚴重等級**：MAJOR · **引擎**：Semgrep
```
long 型金額欄位直接用 * 或 += 聚合
且 未用 Math.multiplyExact / Math.addExact / BigInteger / BigDecimal
```

### RULE-SEC-101～114（taint 規則一覽）

| 規則 | 對應 Pattern | 規則重點 | 引擎 | 信心 |
|------|-------------|---------|------|------|
| RULE-SEC-101 | PAT-SEC-101 | 資金 sink 的 id 參數缺帳戶歸屬校驗（IDOR） | CodeQL taint | 中 |
| RULE-SEC-102 | PAT-SEC-102 | 金額參數缺 signum>0 / 上限 / scale 校驗 | Semgrep | 中 |
| RULE-SEC-103 | PAT-SEC-103 | 餘額 check-then-act 跨非原子邊界（TOCTOU） | CodeQL | 中 |
| RULE-SEC-104 | PAT-SEC-104 | 回調入帳缺簽章驗證 / 我方金額比對 | Semgrep | 中 |
| RULE-SEC-105 | PAT-SEC-105 | 價格來源缺多源 / 時效 / 偏離校驗 | 人工 + 不變量 | 低 |
| RULE-SEC-106 | PAT-SEC-106 | 請求直接綁定持久化實體（mass assignment） | CodeQL | 中 |
| RULE-SEC-107 | PAT-SEC-107 | 敏感操作缺 nonce / 時間窗（重放） | Semgrep | 中 |
| RULE-SEC-108 | PAT-SEC-108 | 高權限調帳缺 maker-checker 雙人覆核 | 人工 | 低 |
| RULE-SEC-109 | PAT-SEC-109 | 動態 SQL 注入（${} / 字串拼接 SQL） | CodeQL taint | 高 |
| RULE-SEC-110 | PAT-SEC-110 | 資金變動缺 append-only 審計 | 人工 + 不變量 | 低 |
| RULE-SEC-111 | PAT-SEC-111 | 敏感欄位（卡號 / CVV / 餘額）寫入日誌 / 回應 | Semgrep | 中 |
| RULE-SEC-112 | PAT-SEC-112 | 金流端點缺速率 / velocity 限制 | 人工 | 低 |
| RULE-SEC-113 | PAT-SEC-113 | 優惠疊加缺互斥 / 上限 / 一次性 / 退款連動 | 人工 | 低 |
| RULE-SEC-114 | PAT-SEC-114 | 冪等鍵低熵 / 可預測 | Semgrep | 中 |

> 註：原 RULE-SEC-001～008（見 `oss-debug-security-loop.md`）是「工具能力」對應；此處 RULE-SEC-101～114 是「金融舞弊模式」對應，兩者不衝突。

---

## 偵測效能度量（Detection Metrics）

> 併入自 detection-metrics（依三模型建議，不獨立成檔）。量化驅動 RECYCLE：沒有度量就無法知道進化是否真的有效。

| 指標 | 定義 | 目標 | 來源 |
|------|------|------|------|
| **Precision（精確率）** | confirmed 真陽 / 所有報出的 finding | ≥ 0.8 | finding-evidence-standard 的 confirmed vs suppressed |
| **Recall（召回率）** | 抓到的真漏洞 / 實際存在（以注入漏洞/事後回填估） | 持續上升 | attack-regression-corpus + 事後檢視 |
| **False-Positive Rate** | suppressed / 所有 finding | ≤ 0.2 | ai-scan-false-positive-patterns 累計 |
| **MTTD** | 漏洞引入 → 偵測的時間 | 越短越好 | git blame vs detect 時間 |
| **Escaped-Defect Rate** | 上線後才發現 / 總漏洞 | 趨近 0 | 事後檢視 |
| **規則命中與攔截** | 每條 RULE 觸發次數 / 攔截真 bug 數 | 見下表 | 健康度追蹤表 |
| **回歸覆蓋** | attack-regression-corpus 條目數 / confirmed 漏洞數 | = 1.0 | corpus |

**RECYCLE 量化準則**：每輪進化後比較 Precision/Recall/FP-Rate 趨勢；若新規則使 FP-Rate 上升而 Recall 未升 → 規則需調校或降為 candidate。

**ARO 供給**：本表的「端點呼叫量級 / 規則命中頻率」供 [[severity-loss-model]] 計算期望資損的 ARO 因子。

---

## 規則健康度追蹤

| 規則代碼 | 規則摘要 | 最後觸發 | 觸發次數 | 攔截 Bug | 狀態 |
|---------|---------|---------|---------|---------|------|
| RULE-FIN-003 | 金融欄位禁止 double/float | — | 0 | 0 | 🟢 就緒 |
| RULE-FIN-004 | BigDecimal 比較用 compareTo | — | 0 | 0 | 🟢 就緒 |
| RULE-CON-001 | Kafka 消費者必須有冪等保護 | SettlementFlow.java | 1 | 1 | 🟢 就緒 |
| RULE-CON-002 | @Transactional 禁止加在 private 方法 | — | 0 | 0 | 🟢 就緒 |
| RULE-CON-003 | @Transactional 必須指定 rollbackFor | — | 0 | 0 | 🟢 就緒 |
| RULE-CON-004 | 批量讀錢包後更新需行鎖或樂觀鎖 | SettlementFlow.java | 1 | 1 | 🆕 就緒 |
| RULE-CON-005 | Retry 場景狀態修改必須冪等 | SettlementFlow.java | 1 | 1 | 🆕 就緒 |
| RULE-CON-006 | 批次 Listener 每筆需獨立冪等鍵 | SettlementFlow.java | 1 | 1 | 🆕 就緒 |
| RULE-CON-007 | 金流狀態躍遷必須用 CAS/樂觀鎖 | — | 0 | 0 | 🆕 就緒 |
| RULE-BIZ-001 | 結算前必須通過業務合理性校驗 | — | 0 | 0 | 🟢 就緒 |
| RULE-BIZ-002 | 外部 API 失敗禁止靜默返回預設值 | SettlementFlow.java | 1 | 1 | 🆕 就緒 |
| RULE-FIN-006 | 多資產精度禁止硬編碼 scale | — | 0 | 0 | 🆕 就緒 |
| RULE-FIN-007 | 分配後總和守恆校驗 | — | 0 | 0 | 🆕 就緒 |
| RULE-FIN-008 | 時間戳單位 / 時區一致性 | — | 0 | 0 | 🆕 就緒 |
| RULE-FIN-009 | long 金額溢位防護 | — | 0 | 0 | 🆕 就緒 |
| RULE-SEC-101 | 資金操作帳戶歸屬校驗（IDOR） | — | 0 | 0 | 🆕 就緒 |
| RULE-SEC-102 | 金額參數正負 / 上限 / scale 校驗 | — | 0 | 0 | 🆕 就緒 |
| RULE-SEC-103 | 餘額 check-then-act 原子性（TOCTOU） | — | 0 | 0 | 🆕 就緒 |
| RULE-SEC-104 | 回調簽章 + 我方金額比對 | — | 0 | 0 | 🆕 就緒 |
| RULE-SEC-105 | 價格多源 / 時效 / 偏離校驗 | — | 0 | 0 | 🆕 就緒 |
| RULE-SEC-106 | 禁止 mass assignment 綁定金額/狀態 | — | 0 | 0 | 🆕 就緒 |
| RULE-SEC-107 | 敏感操作 nonce / 時間窗防重放 | — | 0 | 0 | 🆕 就緒 |
| RULE-SEC-108 | 高權限調帳 maker-checker | — | 0 | 0 | 🆕 就緒 |
| RULE-SEC-109 | 動態 SQL 注入防護 | — | 0 | 0 | 🆕 就緒 |
| RULE-SEC-110 | 資金變動 append-only 審計 | — | 0 | 0 | 🆕 就緒 |
| RULE-SEC-111 | 敏感欄位禁入日誌 / 回應 | — | 0 | 0 | 🆕 就緒 |
| RULE-SEC-112 | 金流端點速率 / velocity 限制 | — | 0 | 0 | 🆕 就緒 |
| RULE-SEC-113 | 優惠互斥 / 上限 / 一次性 | — | 0 | 0 | 🆕 就緒 |
| RULE-SEC-114 | 冪等鍵高熵不可預測 | — | 0 | 0 | 🆕 就緒 |

> 最後更新：v2.0 財務安全進化（2026-06）· 新增 RULE-FIN-006~009 + RULE-SEC-101~114（共 18 條）· 累計攔截 Bug：5 個
> 規則分類擴充：新增 `RULE-SEC-1xx`（財務舞弊 taint 規則），與 `financial-security-patterns.md`、`financial-invariants.md` 三位一體。
