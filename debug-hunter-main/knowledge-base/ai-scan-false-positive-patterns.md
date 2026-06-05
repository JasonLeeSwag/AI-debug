---
file_id: ai-scan-false-positive-patterns
kind: pattern-catalog
status: active
schema_version: 1.0
last_reviewed: 2026-05-18
stale_after_days: 180
owner: knowledge-writer-agent
external_refs: []
---

# AI 安全掃描誤報模式知識庫

> 檔案路徑：knowledge-base/ai-scan-false-positive-patterns.md
> 用途：記錄 AI 自動化掃描中實際發生的誤報案例，作為下次掃描前的驗證 checklist
> 更新時機：每次人工 review 發現誤報後追加
> 最後更新：2026-05-18（settlement-flow-sample 掃描後驗證）

---

## 誤報模式索引

| 代碼 | 名稱 | 誤報根因 | 發現來源 |
|------|------|---------|---------|
| FP-001 | 間接呼叫鏈追蹤失敗 | 只搜尋直接呼叫，忽略 enum lambda / Strategy pattern | settlement-flow-sample HIGH-6 |
| FP-002 | 已歸檔程式碼與現行程式碼混淆 | 搜尋到的 commented-out 程式碼誤判為現行缺陷 | settlement-flow-sample HIGH-7 |
| FP-003 | 業務影響誇大 — 未驗證 DB 層冪等機制 | 直接斷言重複寫入風險，未追蹤 status filter 是否已保護 | settlement-flow-sample HIGH-5 |

---

## FP-001：間接呼叫鏈追蹤失敗

**案例**：settlement-flow-sample 掃描報告 HIGH-6
> 「`SettlementGuard.validate()` 從未被呼叫，異常賠付金額保護形同虛設」

**實際情況**：
```
呼叫路徑：
SettlementFlow.java:339
  → SettleStrategy.SETTLE.getCategory()       // 取出 OrderType enum
    → ((OrderType) category).getFunction()        // 取出 BiFunction
      → .apply(order, countDto)                   // 執行 lambda
        → OrderType.java:43                       // lambda 內部呼叫
          → SettlementGuard.validate(order)       ✅ 確實被呼叫
```

**誤報根因**：
AI 用 `grep "SettlementGuard"` 只找到 `SettlementGuard.java`、測試檔、`OrderType.java`，
卻沒有進一步追蹤「`OrderType` 的 function 是否在結算主路徑上被 apply」。
Strategy Pattern / Enum-as-function 的間接呼叫對 grep-based 掃描形成盲點。

**誤報風險場景**：
- Enum 內含 lambda / BiFunction 的 Strategy Pattern
- Interface 的多型實作（透過 `getCategory().getFunction().apply()`）
- Spring Bean 注入後的 delegate 呼叫（`service.process()` 內部才呼叫目標方法）

**驗證 SOP（發現「方法從未被呼叫」時的必做步驟）**：
```
1. 確認方法是否為 public static — 若是，優先懷疑間接呼叫
2. 搜尋方法所在類別名稱是否被其他 enum/interface 引用
3. 若在 enum 內，追蹤該 enum 的所有使用點（getCategory、getFunction、apply）
4. 確認 lambda 或 BiFunction 是否在主執行路徑的 .apply() / .accept() 中被觸發
5. 只有完成以上步驟後，才能標記為「dead code」
```

---

## FP-002：已歸檔程式碼與現行程式碼混淆

**案例**：settlement-flow-sample 掃描報告 HIGH-7
> 「`batchInsert` 被 comment 掉，訂單刪除前未歸檔，歷史紀錄永久遺失」

**實際情況**：
```java
// OrderService.java — deleteSuccessOrder()
// ✅ batchInsert 存在且正常執行
do {
    orderMapper.batchInsert(runnerId, lastDeletedId, limit);   // 歸檔
    orderMapper.deleteBatchByRunnerAndStatus(...);              // 刪除
} while (deletedCount > 0);
```

掃描器看到的是另一個地方（`OrderService.java:27`）的 commented-out `batchInsert`：
```java
// orderService.batchInsert(runnerId);   ← 這行被 comment，但不是歸檔主路徑
orderService.deleteSuccessOrder(runnerId);  // deleteSuccessOrder 內部有 batchInsert
```

**誤報根因**：
找到「有呼叫但被 comment 掉的 `batchInsert`」就直接報缺陷，
未追蹤 `deleteSuccessOrder()` 的實作是否本身已包含歸檔邏輯。
方法名稱語義（`deleteSuccessOrder` = move + delete）未被正確解讀。

**誤報風險場景**：
- 將多個相似程式碼片段誤認為同一個，其中一個被 comment 就判定「功能缺失」
- 方法名稱語義豐富（move、transfer、archive）但只看呼叫端而非實作
- 重構後有新舊兩個版本，舊版被 comment 但新版已上線

**驗證 SOP（發現「關鍵操作被 comment 掉」時的必做步驟）**：
```
1. 確認 comment 的是直接呼叫，還是被包裝在另一個方法內
2. 展開被呼叫方法的完整實作，確認其中是否已包含相同語義的操作
3. 比對 comment 的位置與現行執行路徑是否重疊，避免新舊版本混淆
4. 只有確認執行路徑中完全缺失該操作，才能標記為缺陷
```

---

## FP-003：業務影響誇大 — 未驗證 DB 層冪等機制

**案例**：settlement-flow-sample 掃描報告 HIGH-5
> 「重送的這批裡，有些 runner 其實已經結算成功了 → 重複結算 = 重複打錢」

**實際情況**：
```sql
-- getOrderByRunnerIdStream 的 SQL：
SELECT * FROM order_tbl WHERE runner_id = ? AND status IN ('PENDING', 'SETTLING')
```
```java
// batchSettleOrders 結算完成後：
order.setStatus(OrderStatus.SETTLED);  // status → SETTLED
orderMapper.batchDeleteByIds(ids);                // 從 order_tbl 刪除
```

Kafka 重送時：
- 已結算訂單 status=SETTLED，且已從 `order_tbl` 刪除
- `status IN ('PENDING', 'SETTLING')` 查不到 → 不會被重複結算 ✅

**技術問題仍存在**（降級為 Medium）：
`.subscribe()` 違反 `MANUAL_IMMEDIATE` 的 ack 合約，可能在特定 Spring Kafka 版本或 rebalance 時序下造成 offset 管理異常，但業務層的重複打錢風險已由 DB status filter 保護。

**誤報根因**：
發現 `.subscribe()` 的技術問題後，直接推論業務影響（重複打錢），
未追蹤「重送後系統實際如何查詢訂單」及「訂單結算後的狀態轉換是否提供冪等保護」。

**誤報風險場景**：
- Kafka 重送場景下直接斷言重複寫入，未驗證業務層冪等機制（status filter、唯一索引、UPSERT）
- 技術合約違反（如 ack 時機）被誇大為等同「資料一定重複寫入」
- 只看觸發端（producer / consumer），未追蹤執行端的防護邏輯

**驗證 SOP（發現「Kafka 重送可能導致重複處理」時的必做步驟）**：
```
1. 追蹤重送後的資料查詢 SQL — 是否有 status / processed_at / unique index 過濾
2. 確認業務操作的目標狀態 — 成功後 status 是否更新，且查詢 WHERE 條件會排除已完成的
3. 確認物理位置 — 成功後資料是否被移走（move to history table、soft delete）
4. 以上有任一保護機制，才能判定業務影響等級，不可直接等同「重複寫入」
5. 技術合約違反與業務風險要分開陳述，嚴重程度獨立評估
```

---

## 通用驗證 Checklist（每次 AI 掃描後的人工複核）

在正式出具報告前，對所有 HIGH 以上的問題執行：

```
□ FP-001 檢查：「方法從未被呼叫」→ 是否有 enum lambda / Strategy / delegate 間接路徑？
□ FP-002 檢查：「關鍵程式碼被 comment」→ 是否只是舊版，新版在其他方法內？
□ FP-003 檢查：「重複處理 = 重複寫入」→ DB 層是否有 status filter / unique index / move 保護？
□ 呼叫鏈完整性：所有「從未被呼叫」的斷言，都要展開 3 層以上的呼叫鏈驗證
□ 業務影響分層：技術合約違反 vs 實際資金風險，必須分開評估嚴重程度
```
