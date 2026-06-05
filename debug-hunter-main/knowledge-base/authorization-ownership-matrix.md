---
file_id: authorization-ownership-matrix
kind: inventory
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 90
owner: threat-modeler-agent
external_refs: ["OWASP API Top 10 2023#API1", "OWASP API Top 10 2023#API5", "CWE-639", "CWE-863", "ASVS 4.0.3#V4"]
---

# 授權與帳戶歸屬矩陣（Authorization & Ownership Matrix）

> 用途：提供 detector / security-fraud-detector 判定「越權」的**業務 ground-truth**。
> 為何關鍵：IDOR / 越權動帳（PAT-SEC-101）是金融系統損失最直接、最高頻的漏洞，但純 taint 掃描無法判斷「這個 accountId 該不該被這個主體操作」——**必須有一張明確的歸屬與授權矩陣當判據**。
> 核心問題：對每個資金操作，回答「**誰（主體）** 能對 **哪些資源（歸屬）** 做 **什麼操作（動作）**，需要 **什麼授權（角色/覆核）**」。
> 連動：[[money-flow-map]]（每條 MF 的入口）、[[financial-security-patterns]]（PAT-SEC-101/108）、[[financial-invariants]]（INV-ST-01）

---

## 1. 主體（Principals）與信任來源

| 主體類型 | 身分來源（可信錨點） | 絕不可信的來源 |
|---------|---------------------|---------------|
| 一般使用者 | 已驗證 JWT/Session 的 `userId` | 請求參數中的 `userId/accountId` |
| 後台操作員 | 內部 SSO + 角色宣告 | 請求 body 的 `role/isAdmin` |
| 服務間呼叫 | mTLS / 服務 token + scope | `X-User-Id` 之類可偽造 header |
| 排程/系統 | 受信任的執行環境身分 | — |

> **鐵律**：歸屬與授權一律錨定於「**已驗證的主體**」，請求帶來的 id 只能用於「比對是否一致」，不能用於「決定操作對象」。

---

## 2. 歸屬鏈（Ownership Chain）

資源的擁有者推導路徑，detector 須沿此鏈驗證：

```
user ──owns──▶ account ──owns──▶ wallet(account_id, coin_id)
order.userId ── must == ── authenticatedUser.id
runner/settlement ── via order ── 推導回 userId
withdraw/transfer ── from_account.userId == authenticatedUser.id
                  ── to_account 可為他人，但金額/收款人需二次確認
```

> 多租戶補充：若有 tenant，所有歸屬鏈須再加 `resource.tenantId == principal.tenantId` 一層。

---

## 3. 授權矩陣（誰能對什麼做什麼）

| 動作 | 對象歸屬要求 | 角色 | 額外授權 | 對應 MF / PAT |
|------|-------------|------|---------|--------------|
| 查餘額 | account.userId == self | user | — | MF-01 |
| 提款 | from.userId == self | user | 金額>閾值→二次驗證/velocity | MF-01 / PAT-SEC-101/112 |
| 轉帳 | from.userId == self | user | 收款人確認 + 重放防護 | MF-02 / PAT-SEC-107 |
| 結算 | 系統，依 order 推導 | system | 業務合理性守衛 | MF-03 / PAT-BIZ-002 |
| 退款/沖正 | 原訂單歸屬 | operator | **maker-checker** + 上限 | MF-?? / PAT-SEC-108 |
| 手動調帳 | 任一帳戶 | senior-operator | **maker≠checker** + 額度分級 + 理由 + 審計 | MF-05 / PAT-SEC-108 |
| 後台查他人帳 | 任一帳戶 | operator | 最小範圍 + 存取審計 | — / PAT-SEC-111 |

---

## 4. Maker-Checker 雙人覆核清單

凡落在下表的操作，單人完成即為漏洞（PAT-SEC-108）：

```
[ ] 手動調帳 / 補單 / 沖正
[ ] 超過額度的退款
[ ] 風控名單增刪（白名單繞過風險）
[ ] 匯率/手續費率/收益率上限等關鍵參數變更
[ ] 大額提款放行
強制：checkerId != makerId；超額需更高層級；全程 append-only 審計（INV-T-01）
```

---

## 5. 偵測條目（schema 化，供 detector 直接執行）

```yaml
id: PAT-SEC-101            # 本矩陣是 PAT-SEC-101 的 ground-truth 來源
title: 越權動帳（IDOR）— 歸屬校驗缺失
status: active
confidence: high
severity_base: P0
applies_to: [withdraw, transfer, query-balance, refund]
cwe: [CWE-639, CWE-863]
owasp_api: [API1, API5]
flows: [MF-01, MF-02, MF-05]
invariants: [INV-ST-01]
sources: ["HTTP accountId|userId|orderId|fromAccount"]
sinks: ["walletService.debit", "transferService.transfer", "balanceQuery"]
required_sanitizers:
  - "resolveOwner(resourceId).userId == securityContext.userId"
  - "多租戶: resource.tenantId == principal.tenantId"
detect:
  static_queries:
    - "對每個 sink 的 id 參數，反查是否經過歸屬鏈校驗（第 2 節）"
  db_evidence:
    - "歸屬是否由 repository SQL 的 WHERE user_id=#{currentUser} 強制？"
false_positive_checks:
  - "FP-001 歸屬校驗是否在 enum lambda / Service delegate 內？"
  - "歸屬是否在 MyBatis mapper 的 WHERE 條件強制（非 controller）？"
confirm_when:
  - "id 來自請求且 path 上（含 DB 層）無歸屬鏈校驗"
reproduce:
  - "user A 的 token + user B 的 accountId/orderId → 操作成功即確認"
oracle: ["INV-ST-01 違反，或越權讀寫他人資源成功"]
rule_ref: RULE-SEC-101
created: 2026-06-01
reproduced_count: 0
```

---

## 6. 維護規則

1. 新增任一資金端點 → 在第 3 節登錄其授權要求，並在 money-flow-map 對應 MF
2. 任何「請求帶 id 直接定位資源」的程式碼 → 對照本矩陣檢查歸屬鏈
3. 落在第 4 節清單卻單人完成 → 強制 P0
4. 多租戶系統務必補 tenant 層歸屬，否則跨租戶越權

---

## 7. 數據分類與敏感度矩陣 (Data Classification)

> 地位：**授權校驗的深度依據**。決定了不同類型的數據需要何種級別的 Sanitizer。
> 註：本節為資料分級的唯一權威來源（已從 financial-security-patterns 合併至此）。

| 數據類別 | 範例 | 敏感度 | 訪問控制要求 |
| :--- | :--- | :--- | :--- |
| **P1: 核心金流數據** | 餘額、交易流水、銀行卡號、密碼 | 極高 | 強制主體歸屬校驗 (Ownership) + 全程加密 + 審計日誌 |
| **P2: 個人隱私數據 (PII)** | 手機號、身份證號、住址、姓名 | 高 | 歸屬校驗 + 脫敏展示 |
| **P3: 業務配置數據** | 商戶手續費率、交易限額、黑名單 | 中 | 角色權限校驗 (RBAC) + 變更雙人審核 |
| **P4: 公開引用數據** | 幣種代碼、銀行名稱、營業網點清單 | 低 | 公開讀取，寫入需管理員權限 |

**偵測邏輯更新**：
- 若 Sink 涉及 P1 類數據，缺失 Ownership Sanitizer 一律定性為 **P0 漏洞**。
- 若 Sink 涉及 P2 類數據，缺失 Sanitizer 定性為 **P1/P2 漏洞**（視合規法規如 GDPR/PIPL 而定）。
