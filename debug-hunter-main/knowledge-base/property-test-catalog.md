---
file_id: property-test-catalog
kind: pattern-catalog
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 180
owner: knowledge-writer-agent
---

# 基於屬性的測試目錄（Property-based Testing Catalog）

> 地位：**動態驗證基線**。用於指導 `reproducer` 生成基於屬性 (Invariant-based) 的測試用例，而不僅僅是固定輸入。

---

## 1. 核心金融不變量屬性 (Core Properties)

### PBT-FIN-01: 餘額守恆 (Conservation of Balance)
- **定義**: 對於任何轉帳操作，$\text{Balance}_{from}(t_0) + \text{Balance}_{to}(t_0) = \text{Balance}_{from}(t_1) + \text{Balance}_{to}(t_1)$。
- **測試生成**: 隨機生成 1000 筆併發轉帳，檢查匯總餘額。
- **失效場景**: 併發更新未加鎖、浮點數精度損失、單邊帳。

### PBT-FIN-02: 餘額非負 (Non-negative Balance)
- **定義**: 除授信帳戶外，$\forall t, \text{Balance}(t) \ge 0$。
- **測試生成**: 大量請求金額 > 當前餘額的取款，檢查是否出現負值。
- **失效場景**: 提款前未檢查餘額、Race Condition、大額整數溢出。

### PBT-FIN-03: 冪等一致性 (Idempotent Consistency)
- **定義**: $f(request) = f(f(request))$。
- **測試生成**: 重放同一個 `request_id` 的請求（成功、失敗、超時狀態下）。
- **失效場景**: 僅在成功時記錄冪等鍵、DB 唯一索引失效、緩存擊穿。

---

## 2. 邊界測試集 (Edge Case Generators)

- **金額極端值**: `0.01`, `0.00000001` (精度), `2^63 - 1` (大數), `-1` (非法輸入)。
- **時間窗口**: Cut-off 點前後 1 毫秒的併發請求。
- **狀態競爭**: 在訂單從 `PENDING` 轉為 `FAILED` 的瞬間發起 `SETTLE`。

---

## 3. 指導 Reproducer
當檢測到涉及 `INV-ST-01` (餘額非負) 的漏洞時，AI 應自動在 `reproduce-scenarios` 中加入 PBT 模板：
```java
@Property
void withdrawalShouldNeverExceedBalance(@ForAll @Positive BigDecimal amount) {
    // 隨機化的併發提款測試
}
```
