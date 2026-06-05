---
file_id: value-authority-sanitizer-registry
kind: registry
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 90
owner: security-fraud-detector-agent
external_refs: ["OWASP API Top 10 2023#API3", "OWASP API Top 10 2023#API6", "CWE-639"]
---

# 數值決定權與清洗閘登錄（Value-Authority & Sanitizer Registry）

> 用途：強化 [[money-flow-map]] 與 PAT-SEC 的 taint 偵測——**對每個敏感值，明確「誰有權決定它」與「從 source 到 sink 必經哪些 sanitizer，落在哪個 class/method/SQL/DB constraint」**。
> 為何關鍵：降誤報的關鍵在於「sanitizer 到底有沒有、在哪」。把 sanitizer 的**實際位置**登錄成表，detector 才能準確判斷「缺防護」vs「有防護只是在別層」（直接打擊 FP-001/FP-003）。
> 連動：[[financial-security-patterns]]、[[finding-evidence-standard]]（db_evidence）、[[persistence-consistency-controls]]

---

## 1. 數值決定權（Value Authority）

| 敏感值 | 正確決定權 | 危險來源 | 規則 |
|--------|-----------|---------|------|
| 交易金額 amount | 使用者輸入但**後端校驗域** | 直接信任 | signum>0 / scale / 上限（PAT-SEC-102） |
| 應付/折後金額 | **後端權威重算** | 前端傳「算好的」 | 一律後端重算，前端值僅顯示 |
| 手續費 fee | **後端依費率重算** | 請求帶 fee | fee=重算值 ∧ 0≤fee≤principal（INV-TXN-03） |
| 匯率/行情 price | **多源中位數+時效** | 單源/陳舊/請求帶 | PAT-SEC-105 |
| 餘額 balance | **僅系統依分錄推導** | 請求 body 含 balance | 禁 mass assignment（PAT-SEC-106） |
| 收款人 toAccount | 使用者指定但需確認 | — | 重放/竄改防護（PAT-SEC-107/114） |
| 狀態 status | **僅狀態機** | 請求 body 含 status | 禁 mass assignment + CAS |
| 折扣/紅利 | **後端規則引擎** | 疊加無上限 | 互斥/上限/一次性（PAT-SEC-113） |

> 通則：**凡會影響入帳金額或權限的值，使用者輸入只能當「請求」，最終值一律由後端權威資料重算或校驗。**

---

## 2. Sanitizer 五閘與落點登錄

| 閘 | 應出現的位置（範例，依實際補） | 缺失對應 |
|----|------------------------------|---------|
| 歸屬 | `OwnershipChecker.assertOwner(resourceId, currentUser)` / mapper WHERE user_id | PAT-SEC-101 |
| 數值域 | `AmountValidator.validate(amount, asset)` 於 Service 入口 | PAT-SEC-102 |
| 授權 | `@PreAuthorize` + `MakerCheckerService` | PAT-SEC-108 |
| 完整性 | `SignatureVerifier.verify()` / `NonceGuard.consume()` | PAT-SEC-104/107 |
| 原子性 | mapper `debitIfEnough` 原子 SQL / 分散式鎖 / 樂觀鎖 version | PAT-SEC-103 / PAT-CON-004 |

> 登錄原則：每個 sanitizer 要記 **實際 class.method 或 mapper id**。detector 反查時：sink 的 taint path 上若**找不到登錄表中對應的 sanitizer 呼叫**，才是真 Finding；若找到但在間接路徑（enum/delegate/mapper WHERE）→ 走 false_positive_checks 確認。

---

## 3. 偵測條目（schema 化）

```yaml
id: PAT-SEC-VAL-001
title: 敏感值缺權威校驗/清洗閘
status: active
confidence: high
severity_base: P0
applies_to: [withdraw, transfer, settlement, payment, promo]
cwe: [CWE-639, CWE-20]
owasp_api: [API3, API6]
flows: [MF-01, MF-02, MF-04, MF-06]
sources: ["HTTP amount|fee|balance|status|price|discount"]
sinks: ["money sink（credit/debit/settle）", "entity persist"]
required_sanitizers:
  - "依第 1 節：該值的決定權；後端重算或域校驗"
  - "依第 2 節：對應五閘的實際 class.method 出現在 path 上"
detect:
  static_queries:
    - "對每個敏感值 source，反查到 sink 的 path 是否經過登錄表中的對應 sanitizer"
  db_evidence:
    - "金額/狀態是否由 DB CHECK / 約束 / mapper WHERE 強制？"
false_positive_checks:
  - "FP-001 sanitizer 是否在 Service delegate / enum lambda 內？"
  - "校驗是否由共用 AOP / 攔截器統一施加（非每個 controller 各寫）？"
confirm_when:
  - "敏感值 source 抵達 sink，path 與 DB 層皆無登錄表對應 sanitizer"
oracle: ["造出非法值（負額/超精度/前端竄改金額/夾帶 balance）後造成錯誤入帳或越權"]
created: 2026-06-01
reproduced_count: 0
```

---

## 4. 維護規則
1. 新增敏感值 → 第 1 節登錄決定權
2. 新增/搬移 sanitizer → 第 2 節更新實際落點（class.method / mapper id）
3. detector 每次掃描以本表為「sanitizer 是否存在」的權威判據，降低 FP
