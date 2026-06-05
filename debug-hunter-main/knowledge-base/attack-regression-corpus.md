---
file_id: attack-regression-corpus
kind: reference
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 90
owner: knowledge-writer-agent
---

# 攻擊回歸語料庫（Attack Regression Corpus）

> 地位：**漏洞 PoC 樣本庫**。提供真實漏洞的請求/響應樣板，用於回歸測試與檢測模型校準。

---

## 1. 樣本：越權動帳 (IDOR on Funds)
- **ID**: CORP-001
- **類型**: IDOR
- **Payload**:
```http
POST /api/v1/withdraw
Content-Type: application/json
Authorization: Bearer <UserA_Token>

{
  "accountId": "USER_B_ACCOUNT_ID_001",
  "amount": 1000.00,
  "currency": "USD"
}
```
- **Expected Outcome**: `403 Forbidden` 或 `401 Unauthorized`。
- **Failed Case**: `200 OK` 且 User B 餘額減少。

---

## 2. 樣本：整數溢出繞過校驗 (Integer Overflow)
- **ID**: CORP-002
- **類型**: Numerical Overflow
- **Payload**:
```json
{
  "amount": 9223372036854775808, 
  "target": "attacker_wallet"
}
```
- **分析**: 超過 `Long.MAX_VALUE`，若後端轉型為 `long` 可能變為負數，繞過 `amount > 0` 校驗。

---

## 3. 樣本：競態條件 (Race Condition)
- **ID**: CORP-003
- **描述**: 在 100ms 內發送 50 個相同的提款請求。
- **驗收標準**: 僅有一筆交易成功，餘額扣減正確。

---

## 4. 如何使用
- **Detection**: AI 掃描代碼時，將代碼邏輯與此語料庫的攻擊向量比對。
- **Validation**: 修復後，執行此語料庫中的 PoC 確保無法觸發。
