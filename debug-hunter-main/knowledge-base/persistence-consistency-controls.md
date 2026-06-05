---
file_id: persistence-consistency-controls
kind: inventory
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 90
owner: knowledge-writer-agent
external_refs: ["CWE-362", "CWE-841"]
---

# 持久化一致性控制（Persistence Consistency Controls）

> 用途：登錄 DB 層的一致性防護（唯一索引、CHECK、鎖、隔離級別、outbox、冪等鍵 scope），作為 detector 把「可能重複/可能越權」**升級為 confirmed 的 DB 證據來源**。
> 為何關鍵：FP-003 的教訓——「Kafka 重送 → 重複入帳」常是誤報，因為 DB 層的唯一索引/狀態過濾已提供保護。**不查 DB 證據就斷言資損，是 debug-hunter 最大的誤報來源。** 本檔把 DB 防護攤開成可查表。
> 連動：[[finding-evidence-standard]]（db_evidence 必查）、[[ai-scan-false-positive-patterns]]（FP-003）、[[financial-invariants]]（INV-ST-01/02、INV-T-02）

---

## 1. DB 層防護登錄表（依實際 schema 補）

| 表 | 防護類型 | 具體約束 | 保護的不變量 | 抵銷的誤報 |
|----|---------|---------|-------------|-----------|
| wallet | CHECK | `balance >= 0`（非授信帳） | INV-ST-01 | 「餘額會變負」 |
| wallet | 樂觀鎖 | `version` 欄位 + `WHERE version=?` | INV-ST-02 | PAT-CON-004 並發覆蓋 |
| wallet | 原子扣款 | `UPDATE...SET balance=balance-? WHERE balance>=?` | INV-ST-01 | PAT-SEC-103 TOCTOU |
| ledger | append-only | 無 UPDATE/DELETE 權限 | INV-T-01 | — |
| settle_record | 唯一索引 | `UNIQUE(business_key)` | INV-T-02 | 「重複結算」 |
| deposit | 唯一索引 | `UNIQUE(gateway_trade_no)` | INV-T-02 | 「回調重複入帳」 |
| order | 狀態過濾 | 查詢 `WHERE status IN('PENDING','SETTLING')` + CAS | INV-ST-05 | FP-003 重送重複 |
| idempotent | 冪等鍵 | Redis `setIfAbsent` + DB 唯一鍵雙層 | INV-T-02 | PAT-CON-001 |

---

## 2. 冪等鍵 Scope 檢查（最易出錯）

```
[ ] 冪等鍵粒度正確？（runner 級 vs 整批級——整批級會漏單筆，PAT-CON-001 變體 B）
[ ] 鍵的 scope 含區分維度？（userId + businessId + 操作類型）
[ ] 鍵高熵不可預測？（PAT-SEC-114）
[ ] 失敗時是否清鍵允許重試、成功時是否延長 TTL 永久防重？
[ ] Redis 與 DB 唯一鍵雙層（Redis 失效時 DB 兜底）？
```

---

## 3. 事務與隔離檢查

```
[ ] 結算核心 @Transactional(rollbackFor=Exception.class)、public、不吞異常（PAT-CON-002）
[ ] 跨表更新（訂單+錢包+流水）在同一事務？
[ ] 隔離級別足夠防併發異常？（read-committed 下的丟失更新需鎖/版本）
[ ] 跨服務操作有 outbox / saga 補償，避免雙寫不一致？
```

---

## 4. 偵測條目（schema 化）— 「升級為 confirmed」的 DB 證據規則

```yaml
id: PAT-PERSIST-001
title: 重複/並發/越權 finding 缺 DB 證據即不得定 HIGH
status: active
confidence: high
severity_base: P0
applies_to: [settlement, deposit, withdraw, wallet-update]
cwe: [CWE-362]
invariants: [INV-ST-01, INV-ST-02, INV-T-02]
detect:
  db_evidence:                      # ★ 本檔的核心：這些一定要查
    - "目標表是否有 UNIQUE(business_key) / UNIQUE(trade_no)？"
    - "扣款是否原子 SQL（WHERE balance>=?）或 SELECT FOR UPDATE？"
    - "更新是否有樂觀鎖 version？"
    - "查詢 WHERE 是否已用 status 過濾排除已完成態？"
    - "ledger/audit 是否 append-only？"
false_positive_checks:
  - "FP-003：DB 唯一索引/狀態過濾已存在 → 重複類 finding 降為 suppressed 或技術債"
confirm_when:
  - "DB 層查無對應防護（唯一索引/原子/版本/狀態過濾）且存在並發或重送可達路徑"
oracle: ["INV-ST-01/02 或 INV-T-02 在並發/重送 PoC 下被違反"]
created: 2026-06-01
reproduced_count: 0
```

> 鐵律（呼應 knowledge-schema 硬規則 3）：**凡涉及重複/越權/競態的 finding，未查本表 DB 證據前，最高只能標 candidate，不得標 HIGH。**

---

## 5. 維護規則
1. 每張涉及金流的表 → 在第 1 節登錄其 DB 防護
2. detector 偵測重複/並發類問題 → 必先查本表，否則 finding 留 candidate
3. 新增唯一索引/CHECK/version → 更新本表，並回頭抑制相關誤報
