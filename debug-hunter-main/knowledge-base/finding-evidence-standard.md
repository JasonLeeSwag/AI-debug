---
file_id: finding-evidence-standard
kind: meta
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 365
owner: knowledge-writer-agent
external_refs: []
---

# Finding 證據標準與生命週期（Finding Evidence Standard）

> 檔案路徑：knowledge-base/finding-evidence-standard.md
> 地位：**元檔**——規範「一個 Finding 要附什麼證據、如何從疑似走到確認、何時可標 HIGH」。
> 為何最優先：三模型共識——降誤報最有效的手段不是事後人工複核，而是**把證據要求變成 finding 的『出生證明』**。沒有證據的 finding 不准升級。
> 對應：把 `ai-scan-false-positive-patterns.md`（事後 checklist）升級為**事前 gate**；與 `knowledge-schema.md` 的條目 schema 互補（一個管「知識長怎樣」，一個管「發現長怎樣」）。

---

## 核心原則

> **No evidence, no severity.**（沒有證據，就沒有嚴重度）
> 一個 finding 在補齊證據前，最高只能是 `candidate`，不得進入 TRIAGE 的 P0/P1，更不得對外宣稱。

debug-hunter 的最大風險不是漏報，而是**用自信的語氣報出錯誤的高危 finding**（FP-001/002/003 都是這類）。本標準用「證據門檻 + 反證義務」把這條路堵死。

---

## 1. Finding 生命週期（狀態機）

```
candidate ──(補齊必要證據 + 過反證檢查)──▶ confirmed ──(修復+驗收)──▶ resolved
    │                                          │
    └──(反證成立/查得既有防護)──▶ suppressed ◀──┘
```

| 狀態 | 含義 | 可否進 TRIAGE | 可否對外/告警 |
|------|------|--------------|--------------|
| `candidate` | 疑似，證據未齊 | 否（僅排隊待證） | 否 |
| `confirmed` | 證據齊 + 反證未推翻 | 是，正常定級 | 是 |
| `suppressed` | 已查得防護或為已知誤報 | 否 | 否（回寫誤報庫） |
| `resolved` | 已修復並驗收 | — | 結案 |

---

## 2. 每個 Finding 的必備欄位（出生即須具備）

```yaml
finding_id: SF-2026-0012
pattern_ref: PAT-SEC-101          # 對應的知識條目 id（無對應 → 標 novel 待人工）
status: candidate                  # candidate | confirmed | suppressed | resolved
confidence: medium

# —— 證據三件套（缺一不可升 confirmed）——
taint_path:                        # ① 完整可定位的 source→sink 路徑
  source: "WithdrawController.withdraw#@RequestParam accountId (line 28)"
  steps:
    - "WithdrawController.withdraw() → walletService.debit()"
  sink: "WalletServiceImpl.debit(accountId, amount) (line 53)"
missing_sanitizer: "path 上無 acc.userId == currentUser 校驗"

db_evidence:                       # ② DB 層證據（重複/越權/競態類強制）
  checked: true
  finding: "wallet 表無 user_id 歸屬於 SQL WHERE；debit SQL 僅 WHERE account_id"
  # checked:false 時，status 最高只能 candidate

exploit_premise:                   # ③ 可利用前提（攻擊者真能觸發嗎）
  - "端點對外暴露且僅需登入態"
  - "accountId 可列舉/可猜"

# —— 反證義務（必須主動嘗試推翻自己）——
refutation_checks:
  - check: "FP-001 歸屬是否在 enum lambda/delegate 間接校驗？"
    result: "否，已展開 3 層呼叫鏈確認"
  - check: "FP-003 DB 是否有唯一索引/狀態過濾提供保護？"
    result: "否"
  refuted: false                   # true → 轉 suppressed

# —— 違反的不變量（confirmed 的客觀錨點）——
invariant_violated: [INV-ST-01]

# —— 影響（交給 severity-loss-model 量化）——
blast_radius: "任一帳戶餘額上限"
exploit_cost: low

created: 2026-06-01
evidence_sources: ["靜態追蹤", "DB schema 檢視", "呼叫鏈展開"]
```

---

## 3. 升級門檻（candidate → confirmed）

**全部滿足才可升 confirmed 並進 TRIAGE：**

```
[ ] taint_path 完整且 source/sink 皆可定位到 class.method:line
[ ] missing_sanitizer 明確（或 bypassable_sanitizer 已證明可繞過）
[ ] 涉及重複/越權/競態 → db_evidence.checked = true
[ ] exploit_premise 成立（攻擊者真能觸發，非理論可達）
[ ] refutation_checks 全跑過且 refuted = false
[ ] 能指出被違反的 invariant（客觀判據，非主觀「感覺危險」）
```

**任一不滿足** → 留 `candidate`，記錄缺哪項證據，回 detector/reproducer 補蒐。

---

## 4. 反證義務（Adversarial Self-Refutation）★ 降誤報核心

每個 finding 在升 confirmed 前，**必須主動嘗試證明自己是錯的**。預設立場是「這可能是誤報」，要有證據才推翻這個預設。至少跑：

| 反證問題 | 對應誤報模式 |
|---------|-------------|
| 防護是否在間接呼叫鏈（enum lambda / Strategy / delegate）內？ | FP-001 |
| 被指為缺失的程式碼，是否只是舊版/已被 comment 的非主路徑？ | FP-002 |
| DB 層是否已有唯一索引 / 狀態過濾 / 約束提供保護？ | FP-003 |
| 「技術合約違反」是否被誇大為「一定造成資損」？ | FP-003 |
| sink 是否實際不可達（dead code / feature flag off）？ | 通用 |

> 反證成立 → `suppressed` + 回寫 `ai-scan-false-positive-patterns.md`（讓同類自動被抑制）。
> 這條規則把「降誤報」從一次性人工複核，變成**每個 finding 內建、可累積的能力**。

---

## 5. 與閉環各 Stage 的接點

- **Stage 1 DETECT**：detector / security-fraud-detector 產出的每個 finding 一律先 `candidate`，附 taint_path + missing_sanitizer
- **Stage 2 TRIAGE**：只處理 `confirmed`；`candidate` 退回補證據，不浪費 triage 與人力
- **Stage 2.5 REPRODUCE**：PoC「成功」= `invariant_violated` 為真，據此把 confidence 升 high
- **Stage 4 VERIFY**：修復後同一 finding 的 reproduce 由成功轉失敗、不變量恆成立 → `resolved`
- **Stage 5 RECYCLE**：`suppressed` → 誤報庫；`confirmed` 的新型 → 依 knowledge-schema 入庫（reproduced_count++）

---

## 6. 報告語氣規範（避免「自信的錯誤」）

```
confirmed  → 可用肯定語氣，附證據三件套
candidate  → 必須用「疑似 / 待證」語氣，並列出缺哪項證據
suppressed → 說明為何判定非漏洞（哪個防護擋住），不列入風險清單
```

> 嚴禁把 `candidate` 用 confirmed 的語氣呈現——這是 debug-hunter 信任度的生命線。

---

> 相關元檔：[[knowledge-schema]]（知識條目的 schema 與 RECYCLE 入庫準則）。
> 相關：[[ai-scan-false-positive-patterns]]（具體誤報案例庫，本檔的反證問題即源於此）。
