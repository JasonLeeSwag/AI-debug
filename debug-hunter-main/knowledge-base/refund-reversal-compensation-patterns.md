---
file_id: refund-reversal-compensation-patterns
kind: pattern-catalog
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 180
owner: knowledge-writer-agent
---

# 退款、沖正與補償模式（Refund, Reversal & Compensation）

> 地位：**異常路徑地圖**。金融系統 80% 的 Bug 發生在「失敗處理」與「逆向流程」。

---

## 1. 沖正流程 (Reversal Patterns)
- **適用場景**: 支付發起但收單行響應超時，狀態不明。
- **安全不變量**:
  - `INV-REV-01`: 沖正請求必須與原始交易 ID 強綁定。
  - `INV-REV-02`: 已成功（Confirmed）的交易不允許沖正。
- **風險模式**:
  - **盲目沖正**: 未核實遠端狀態即解凍用戶資金，導致資損。

---

## 2. 退款防護 (Refund Protections)
- **PAT-REF-01: 原路退回原則**: 退款資金必須回到支付時的原帳戶，禁止修改退款目的地（防洗錢/套現）。
- **PAT-REF-02: 退款限額校驗**: $\sum \text{Refunds} \le \text{OriginalAmount}$。
- **偵測點**:
  - 檢查退款接口是否允許傳入 `targetAccountId`。
  - 檢查是否存在退款次數/總額的併發校驗。

---

## 3. 補償事務 (Compensating Transactions)
- **定義**: 在分散式系統中，若 A 服務扣款成功但 B 服務（如發券）失敗，發起的逆向回滾。
- **偵測風險**: 補償操作若不具備冪等性，會導致重複加錢。

---

## 4. 稽核清單
- [ ] 所有的逆向操作是否有對應的日誌與審計跟蹤？
- [ ] 沖正/退款是否檢查了原始訂單的狀態機（防範從 PENDING 直接跳轉到 REFUNDED）？
