---
file_id: knowledge-schema
kind: meta
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 365
owner: knowledge-writer-agent
external_refs: []
---

# 知識庫元結構與治理 Schema（Knowledge Schema & Governance）

> 檔案路徑：knowledge-base/knowledge-schema.md
> 地位：**元檔（meta-file）**——規範「其他所有 KB 檔該長什麼樣」與「RECYCLE 回寫的入庫準則」。
> 為何最優先：三模型交叉覆查的共識——KB 若沒有統一的機器可讀結構與入庫門檻，內容越多，AI 偵測精度反而越低、RECYCLE 自我進化會把知識庫越寫越爛。
> 維護者：`agents/knowledge-writer.md`（回寫前須通過本檔的 lint）；所有 agent 讀取 pattern 時依本 schema 解析。

---

## 為什麼需要這個檔（問題）

目前 KB 多為「給人讀的文章」：敘述完整但**結構不一致**，LLM 難以穩定地把它轉成「可執行的偵測動作」。後果：
- 同一類資訊在不同檔用不同寫法 → 模型解析不穩、偵測漂移
- RECYCLE 回寫沒有格式約束 → 格式崩壞、孤島知識、循環引用
- 沒有「可信度 / 狀態 / 證據要求」欄位 → candidate 與 confirmed 混為一談 → 誤報

**解法**：每個可偵測知識條目 = 一個**固定 schema 的結構化單元**（YAML frontmatter + Markdown 說明），讓「人可讀」與「機器可執行」並存。

---

## 1. 通用檔頭（所有 KB 檔開頭都要有）

```yaml
---
file_id: financial-security-patterns      # 檔案唯一 id（= 檔名去副檔名）
kind: pattern-catalog                      # pattern-catalog | invariant | inventory | registry | playbook | meta | reference
status: active                             # active | draft | deprecated
schema_version: 1.0                         # 遵循本檔的版本
last_reviewed: 2026-06-01                   # 最後人工覆查日（知識新鮮度依據）
stale_after_days: 180                       # 超過未覆查 → lint 警告（防知識腐壞）
owner: knowledge-writer-agent
external_refs:                              # 引用的外部標準（落地不過期：標版本）
  - "OWASP API Top 10 2023#API1"
  - "CWE-639"
---
```

---

## 2. 偵測條目 Schema（pattern / 不變量 / 規則共用核心欄位）

每個 `PAT-*`、`INV-*`、`RULE-*` 條目 = 一個 YAML 區塊 + Markdown 補充。**這是本框架最重要的格式約定。**

```yaml
id: PAT-SEC-101                # 全域唯一，跨檔引用的錨點
title: 資金操作缺乏帳戶歸屬校驗（IDOR）
status: active                 # active | candidate | confirmed | suppressed | deprecated
confidence: high              # high | medium | low（影響 TRIAGE 是否需人工確認）
severity_base: P0             # 預設等級（最終由 severity-loss-model 校準）

# —— 分類與交叉引用（防孤島：每條都必須能連回地圖/不變量/標準）——
applies_to: [withdraw, transfer, settlement]   # 業務場景
cwe: [CWE-639, CWE-863]
owasp_api: [API1]
flows: [MF-01, MF-02]          # money-flow-map 的金流 id
invariants: [INV-ST-01]        # 被違反的 financial-invariants id
compliance: [PCI:Req7, ASVS:V4.1, AML:-]

# —— Taint 模型（偵測的核心：source → sanitizer → sink）——
sources:                       # 不可信輸入，標可定位位置語意
  - "HTTP @RequestParam accountId"
  - "HTTP @PathVariable orderId"
sinks:                         # 資金匯點，標具體 class.method
  - "walletService.debit(accountId, amount)"
  - "settlementService.settle(order)"
required_sanitizers:          # 缺任一即 Finding；存在但可繞過另列（見下）
  - "acc.userId == securityContext.userId   # 帳戶歸屬"
bypassable_sanitizers:        # 「有寫但可被繞過」也要建模（降漏報）
  - "僅在 Controller 校驗但 Service 另有入口可直達 sink"

# —— 偵測動作（讓 LLM/工具知道具體怎麼查）——
detect:
  static_queries:
    - "trace each source to each sink; require all required_sanitizers on path"
  runtime_queries:
    - "audit log 中是否存在 operator.userId != account.userId 的動帳"
  db_evidence:                 # ★ 必查 DB 證據才能定 confirmed
    - "歸屬是否由 repository SQL 的 WHERE user_id=? 強制？若是則非漏洞"

# —— 降誤報門檻（confirmed 前必過）——
false_positive_checks:        # 對應 ai-scan-false-positive-patterns 的 FP-*
    - "FP-001 間接呼叫鏈：歸屬校驗是否在 enum lambda / delegate 內？"
    - "歸屬是否由 DB constraint / repository 層強制（非 controller）？"
confirm_when:
    - "source 抵達 sink 且 path 上無等效 required_sanitizer（含 DB 層）"

# —— 復現與驗收（連 reproduce-scenarios / attack-regression-corpus）——
reproduce:
    - "以 user A 的 token 帶入 user B 的 accountId 提款"
oracle:                        # 「攻擊成功」的判定 = 違反哪條不變量
    - "INV-ST-01 被違反，或越權動帳成功"

# —— 修復與規則化 ——
fix_strategy: "以認證主體為錨點，請求 id 僅用於一致性校驗"
rule_ref: RULE-SEC-101
fix_ref: settlement-checklist#三

# —— 來源與生命週期 ——
source_event: BUG-EXAMPLE-IDOR
created: 2026-06-01
reproduced_count: 0           # RECYCLE 升級門檻依據（見第 4 節）
```

> Markdown 區塊（人讀補充）緊接在 YAML 後：描述、程式碼正反例、推廣原則。**YAML 給機器、Markdown 給人，兩者不可互相取代。**

---

## 3. 四條硬規則（LLM 解析與回寫時強制）

1. **所有路徑必須可定位**：source/sink/sanitizer 一律用 `class.method`、endpoint、Kafka topic、MyBatis mapper、table/index 名稱——不准只寫「在某處校驗」。
2. **「缺 sanitizer」與「sanitizer 存在但可繞過」分開建模**：前者進 `required_sanitizers`，後者進 `bypassable_sanitizers`。只看前者會漏報繞過型漏洞。
3. **DB 證據是 confirmed 的必要條件**：凡牽涉重複/越權/競態，未查 `db_evidence`（唯一索引、WHERE 條件、CHECK、鎖）前，最高只能標 `candidate`，不得標 HIGH。（直接對應 FP-003 教訓）
4. **`rules-registry.md` 只做索引**：完整的 detect / false_positive_checks / reproduce / oracle 留在 pattern 檔，registry 僅存 id→pattern 的對照與健康度，避免雙寫漂移。

---

## 4. RECYCLE 回寫入庫準則（自我進化的安全閥）

knowledge-writer 回寫新知識前，**必須**通過下列門檻，否則只能進 `status: candidate`：

```
[ ] 唯一 id 且不與既有衝突
[ ] YAML 必填欄位齊全（id/status/confidence/sources/sinks/required_sanitizers/oracle）
[ ] 至少連結 1 個 flow + 1 個 invariant（防孤島知識）
[ ] 通過 false_positive_checks（防把誤報寫成 pattern）
[ ] reproduced_count ≥ 2 才可由 candidate 升 active（防語義漂移：一次性 bug 不夠格成通用 pattern）
[ ] 若是「正面基線/修復範例」，須附驗收證據（防邏輯污染：錯誤修復被當基線）
```

**狀態機**：`candidate → (復現 ≥2 次 + 過 FP 檢查) → active → (失效/被取代) → deprecated`。
`suppressed` 為已確認的長期誤報模式，保留以抑制重複回報。

---

## 5. RECYCLE 必避的反模式（Anti-patterns，Gemini 提出）

| 反模式 | 症狀 | 本 schema 的防線 |
|--------|------|-----------------|
| **語義漂移** | 把特定業務 bug 當通用 pattern，KB 充斥噪音 | reproduced_count ≥ 2 才轉 active |
| **邏輯污染** | 錯誤修復被回寫成「正面基線」，全系統集體降智 | 正面基線須附驗收證據 |
| **循環引用** | A 引 B、B 引 A，推理死循環 | 交叉引用一律用單向 id（flows/invariants/cwe），lint 偵測環 |
| **孤島知識** | 新模式沒打標籤，無法與 money-flow-map/invariants 關聯 | 入庫強制至少連 1 flow + 1 invariant |
| **知識腐壞** | 舊知識在新環境（如 Java 21）誤導 | last_reviewed + stale_after_days，過期 lint 警告 |

---

## 6. Lint 檢查（可做成 CI / pre-commit）

```
對每個 KB 檔與每個條目：
[ ] 檔頭 frontmatter 齊全且 schema_version 相符
[ ] 每個 id 全域唯一
[ ] 每個 flows/invariants/cwe 引用都指向存在的目標（無斷鏈）
[ ] 無循環引用
[ ] active 條目的 reproduced_count ≥ 2
[ ] last_reviewed 未超過 stale_after_days
[ ] required_sanitizers 與 sinks 非空（pattern 類）
```

---

## 7. 漸進遷移策略（不必一次重寫全部）

1. 新增的條目一律用本 schema（即日生效）
2. 既有 13 個 KB 檔：**先補檔頭 frontmatter**（低成本），條目本體分批 schema 化
3. 優先 schema 化「直接碰錢且高頻」的：PAT-SEC-101/103/104、INV-ST-01/03
4. 每次 RECYCLE 順手把碰到的舊條目升級為 schema 格式（邊用邊遷移）

> 相關元檔：[[finding-evidence-standard]]（finding 的證據與生命週期，與本檔的條目 schema 互補）。
