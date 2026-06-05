---
file_id: workflow-state-machine-catalog
kind: inventory
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 90
owner: threat-modeler-agent
external_refs: ["CWE-841", "OWASP API Top 10 2023#API6", "ASVS 4.0.3#V11"]
---

# 金流狀態機目錄（Workflow State-Machine Catalog）

> 用途：提供 detector 判定「狀態躍遷是否合法」的 ground-truth。
> 為何關鍵：金融邏輯漏洞（CWE-841 Workflow Enforcement）的核心是**非法狀態躍遷**——跳步、回退、亂序、重放、並發競態、失敗恢復後重入。純特徵掃描看不出「這個 setStatus 在這個情境是否合法」，必須有合法躍遷圖當判據。
> 連動：[[financial-invariants]]（INV-ST-05 狀態單調）、[[financial-security-patterns]]（PAT-SEC-103/107）、[[persistence-consistency-controls]]（樂觀鎖落地）

---

## 1. 通用攻擊角度（對每個狀態機都問）

| 攻擊 | 提問 | 對應 |
|------|------|------|
| 跳步 | 能否略過中間態直達終態（未付款→已出貨）？ | CWE-841 |
| 回退 | 終態能否被改回前態（已結算→待結算→再結算）？ | INV-ST-05 / 重複入帳 |
| 亂序 | 並發請求造成躍遷亂序？ | PAT-SEC-103 |
| 重放 | 重送同一躍遷請求是否再次生效？ | PAT-SEC-107 / INV-T-04 |
| 並發 | 兩請求同時觸發同一躍遷（雙花/雙退）？ | PAT-CON-004 |
| 失敗恢復 | retry/補償後是否重入已完成態？ | PAT-CON-001/005 |

---

## 2. 核心金流狀態機（依實際系統補實際狀態名）

### 提款 Withdraw
```
合法： REQUESTED → RISK_CHECK → APPROVED → PROCESSING → COMPLETED
                              ↘ REJECTED        ↘ FAILED → (退回凍結)
非法： *→COMPLETED 跳過 PROCESSING；COMPLETED→任何；PROCESSING 並發二次扣款
守衛： available→frozen 原子凍結(INV-ST-06)；扣款用原子條件(PAT-SEC-103)；狀態用樂觀鎖
```

### 訂單/結算 Settlement
```
合法： PENDING → SETTLING → SETTLED → (歸檔/刪除)
非法： SETTLED→PENDING（回退重結算，重複打錢）；SETTLING 並發兩次入帳
守衛： CAS 更新 WHERE status='PENDING'（PAT-CON-001）；單筆冪等鍵；查詢 WHERE status IN(...) 排除已完成
```

### 退款/沖正 Refund/Reversal
```
合法： CAPTURED → REFUND_REQUESTED → REFUND_APPROVED(maker-checker) → REFUNDED
非法： 重複退款（REFUNDED→REFUND_REQUESTED）；退款額 > 已捕獲額 − 已退額；
       退款不撤回已發紅利（連動 PAT-SEC-113）
守衛： Σ退款 ≤ capturedAmount（INV）；maker-checker（PAT-SEC-108）；冪等鍵
```

### 充值/入金 Deposit（外部回調驅動）
```
合法： INIT → PAID(回調驗簽) → CREDITED
非法： 偽造回調直達 PAID（PAT-SEC-104）；同一 tradeNo 重複 CREDITED（INV-T-02）
守衛： 回調驗簽 + 我方金額比對 + tradeNo 冪等
```

---

## 3. 偵測條目（schema 化）

```yaml
id: PAT-WF-001
title: 非法狀態躍遷（跳步/回退/重入）
status: active
confidence: medium
severity_base: P0
applies_to: [withdraw, settlement, refund, deposit]
cwe: [CWE-841]
flows: [MF-01, MF-03, MF-04]
invariants: [INV-ST-05, INV-T-02]
sinks: ["order.setStatus(...)", "withdraw.setStatus(...)", "coupon.markUsed()"]
required_sanitizers:
  - "躍遷前校驗 current ∈ 合法前驅集合（依第 2 節躍遷圖）"
  - "CAS / 樂觀鎖：UPDATE ... WHERE status = <expected>"
detect:
  static_queries:
    - "找所有 setStatus/狀態寫入點，比對是否有 WHERE status=舊態 的 CAS 保護"
  db_evidence:
    - "狀態欄位是否有樂觀鎖 version？躍遷是否走 CAS？"
false_positive_checks:
  - "FP-003 查詢端 WHERE status IN(...) 是否已排除已完成態（提供冪等）？"
confirm_when:
  - "狀態寫入無前驅校驗且無 CAS/樂觀鎖，且存在並發/重放可達路徑"
reproduce:
  - "並發兩次觸發同一躍遷；或對終態送躍遷請求觀察是否生效"
oracle: ["INV-ST-05 違反（狀態回退）或同筆產生兩次資金效果"]
rule_ref: RULE-CON-007
created: 2026-06-01
reproduced_count: 0
```

---

## 4. 維護規則
1. 每個有「狀態欄位」且涉及金流的實體 → 在此登錄合法躍遷圖
2. 每個 setStatus 寫入點 → 對照躍遷圖 + 檢查 CAS/樂觀鎖
3. 新增躍遷 → 同步更新圖與 PAT-WF 條目
