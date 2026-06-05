---
file_id: settlement-checklist
kind: reference
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 180
owner: knowledge-writer-agent
external_refs: []
---

# 結算系統專屬檢查清單

> 適用服務：settlement-service
> 每次結算相關 PR 必須通過此清單，才能進入 Code Review

---

## 一、BigDecimal 計算

```
[ ] 1. 除法操作：所有 .divide() 是否指定 scale 和 RoundingMode？
        → 範例：.divide(divisor, 8, RoundingMode.HALF_DOWN)

[ ] 2. 最終金額：結果是否 setScale(8, RoundingMode.HALF_DOWN)？
        → 高精度金融計算通常 8 位小數

[ ] 3. 中間計算：中間結果是否保留足夠精度（建議 16 位）後再截斷？
```

---

## 二、事務邊界

```
[ ] 4. 結算核心方法：是否有 @Transactional(rollbackFor = Exception.class)？

[ ] 5. 事務方法是否為 public（非 private）？

[ ] 6. 事務方法內是否有 try-catch 吃掉異常？
        → 禁止！吃掉異常 = 事務不回滾 = 資料半寫入

[ ] 7. 訂單狀態更新、錢包入帳、流水記錄：是否在同一個事務內？
```

---

## 三、並發安全

```
[ ] 8. 訂單讀取：是否使用 SELECT ... FOR UPDATE（悲觀鎖）？
        → 防止並發結算同一筆訂單

[ ] 9. 狀態更新：是否用 CAS（UPDATE ... WHERE status = 'PENDING'）？
        → 確保只有 PENDING 狀態的訂單能被結算

[ ] 10. 分散式鎖：如果有跨服務呼叫，是否有分散式鎖保護？
```

---

## 四、冪等性

```
[ ] 11. Kafka 消費：是否有 Redis setIfAbsent 防重？

[ ] 12. 失敗補償：消費失敗時，Redis 防重鍵是否會被清除？

[ ] 13. PowerJob 排程：是否有分片隔離，防止多 Worker 重複處理？
```

---

## 五、業務合理性守衛

```
[ ] 14. 結算前校驗：是否呼叫 SettlementGuard.validate(order, profit)？

[ ] 15. 最大收益率：是否從 Nacos 讀取，有預設安全值（如 2.0 = 200%）？

[ ] 16. 單筆賠付上限：是否有設定，並在告警後才拋出異常？

[ ] 17. 異常情況：拋出異常前是否先打告警日誌？
```

---

## 六、日誌與可觀測性

```
[ ] 18. 結算成功：是否記錄 orderId、amount、profit、rate、耗時？

[ ] 19. 結算失敗：是否記錄完整的錯誤鏈（cause）？

[ ] 20. 關鍵步驟：訂單讀取、狀態更新、錢包入帳，是否各有 INFO 日誌？

[ ] 21. 流水號：結算流水是否有全域唯一識別碼，方便對帳追蹤？
```

---

## 通過標準

- 第 1~3 項（金融計算）：必須 **全部通過**，否則 Block PR
- 第 4~10 項（事務邊界與並發安全）：必須 **全部通過**，否則 Block PR
- 第 11~13 項（冪等性）：若有 Kafka 相關代碼則必須通過
- 第 14~17 項（守衛）：必須 **全部通過**，否則 Block PR
- 第 18~21 項（日誌）：建議通過，不通過需說明原因

---

## 七、正面安全編碼基線（Secure-Coding Baseline）

> 併入自 secure-coding-baseline（依三模型建議，不獨立成檔）。前六節是「該檢查什麼」，本節是「正確該怎麼寫」的權威範本，供 FIX 階段直接參照、降低修復引入新漏洞。

### 金額與精度
```java
private BigDecimal amount;                                   // 不用 double/float
int scale = assetMeta.getScale(coinId);                     // 不硬編碼 scale
BigDecimal r = a.multiply(b).setScale(scale, assetMeta.getRounding(coinId));
if (a.compareTo(b) == 0) { }                                // 不用 equals
```

### 授權與歸屬（連 authorization-ownership-matrix）
```java
Long me = securityContext.getUserId();                      // 錨定認證主體
Account acc = accountMapper.selectByIdAndUserId(accountId, me); // DB 層強制歸屬
if (acc == null) throw new AccessDeniedException();
```

### 數值域（連 value-authority-sanitizer-registry）
```java
if (amount == null || amount.signum() <= 0) throw new ValidationException();
if (amount.compareTo(asset.getMaxSingleTxn()) > 0) throw new ValidationException();
BigDecimal payable = pricingService.recompute(order);       // 金額後端重算，不信前端
```

### 原子性 / 冪等 / 狀態
```java
int n = walletMapper.debitIfEnough(accountId, amount);      // 原子扣款，非 check-then-act
int u = orderMapper.casStatus(id, PENDING, SETTLING);       // CAS 狀態躍遷
redis.opsForValue().setIfAbsent("idem:"+userId+":"+reqId, "1", TTL); // 高熵冪等鍵
```

### 外部資料與回調
```java
if (!signatureVerifier.verify(rawBody, sig)) throw new SecurityException(); // 回調驗簽
if (resp.getCode() != 1) throw new PriceApiException();     // 外部失敗拋例外，不靜默預設值
```

### 不可記錄 / 不可回傳
```java
log.info("pay card={}", mask(card));                        // 遮罩；CVV 永不記
return toDto(account);                                       // 回 DTO 白名單，不回 entity
```

> **基線即規則**：本節每條都對應一條 RULE-*；違反基線 = 觸發規則。修復後務必讓對應 RULE 由「可觸發」轉「不可觸發」。
