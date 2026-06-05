---
file_id: time-window-cutoff-calendar-rules
kind: reference
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 365
owner: knowledge-writer-agent
---

# 時間窗口、轧帳與日曆規則（Time-Window & Cut-off Rules）

> 地位：**時序正確性基線**。定義金融系統如何處理「時間」這一維度的不變量。

---

## 1. 轧帳規則 (Cut-off Rules)
- **定義**: 每日 `23:59:59` 或特定時間（如銀行 T+1 換日）的狀態凍結。
- **不變量**:
  - 在 T 日 Cut-off 之後進入的訂單，其會計日期（Accounting Date）必須標記為 T+1。
- **風險模式**:
  - **時鐘漂移**: 集群節點間時間不一致，導致跨日對帳失敗。
  - **邊界競態**: 在 23:59:59.999 併發提交，部分進入 T 日流水，部分進入 T+1。

---

## 2. 交易過期 (Transaction Expiry)
- **不變量**: 超過 `timeout` 未支付的訂單必須轉為 `EXPIRED` 且不得再觸發 `SETTLE`。
- **偵測點**: 檢查 `pay()` 方法中是否重新驗證了 `order.createdAt + timeout > current_time`。

---

## 3. 週期性任務 (Batch/Job Rules)
- **清算任務**: 必須在前一週期的所有流水都標記為 `FINALIZED` 後才能啟動。
- **檢查點**: 批量任務是否具備防重入鎖（Distributed Lock）。

---

## 4. 測試策略
- 使用 `TimeCop` 或 Mock 時鐘模擬換日時刻。
- 測試閏年、冬令時/夏令時切換對利息計算的影響。
