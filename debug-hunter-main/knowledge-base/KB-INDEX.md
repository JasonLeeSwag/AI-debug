---
file_id: KB-INDEX
kind: meta
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 90
owner: knowledge-writer-agent
external_refs: []
---

# 知識庫導覽索引（KB Index / Manifest）

> 用途：全庫單一導覽入口。列出所有 KB 檔的 id / kind / 提供的 ID / 交叉引用 / 對應 Stage，讓 AI 與人都能一致地導航，**防止孤島知識與斷鏈引用**。
> 維護：新增/刪除 KB 檔或新增 PAT/INV/RULE 時，同步更新本檔。
> 一致性檢查見最後一節。

---

## 1. 檔案清單（24 檔）

| file_id | kind | 提供的關鍵 ID | 引用 | 對應 Stage |
|---------|------|--------------|------|-----------|
| **KB-INDEX** | meta | — | (all) | 全域 |
| **knowledge-schema** | meta | schema, 入庫狀態機 | finding-evidence-standard | 全域/RECYCLE |
| **finding-evidence-standard** | meta | finding 生命週期, 反證義務 | ai-scan-false-positive-patterns, knowledge-schema | DETECT/TRIAGE |
| money-flow-map | inventory | MF-01..08 | threat-catalog, invariants, value-authority | THREAT-MODEL |
| threat-catalog | pattern-catalog | STRIDE-FIN, AB-01..12, 供應鏈 | money-flow-map, financial-security-patterns | THREAT-MODEL |
| authorization-ownership-matrix | inventory | 歸屬鏈, 授權矩陣, maker-checker | money-flow-map, PAT-SEC-101/108 | DETECT |
| workflow-state-machine-catalog | inventory | PAT-WF-001, 狀態機 | invariants, persistence-consistency | DETECT |
| value-authority-sanitizer-registry | registry | PAT-SEC-VAL-001, 五閘落點 | financial-security-patterns, persistence | DETECT |
| persistence-consistency-controls | inventory | PAT-PERSIST-001, DB 防護 | finding-evidence-standard, invariants | DETECT/VERIFY |
| financial-bug-patterns | pattern-catalog | PAT-FIN/CON/BIZ-* | rules-registry, invariants | DETECT |
| financial-security-patterns | pattern-catalog | PAT-SEC-101..114, 資料分級 | money-flow-map, invariants, compliance | DETECT |
| financial-invariants | invariant | INV-TXN/ST/T-* | property-test-catalog | DETECT/VERIFY/GUARD |
| refund-reversal-compensation-patterns | pattern-catalog | PAT-REF-001..005 | workflow-state-machine, invariants | DETECT |
| time-window-cutoff-calendar-rules | pattern-catalog | PAT-TIME-001..004 | financial-bug-patterns, glossary | DETECT |
| version-compatibility-matrix | reference | Java21/SpringBoot3 風險 | financial-bug-patterns | DETECT |
| compliance-mapping | registry | PCI/ASVS/API/AML 對應 | financial-security-patterns, invariants | RECYCLE |
| ai-scan-false-positive-patterns | pattern-catalog | FP-001..003 | finding-evidence-standard | TRIAGE |
| severity-loss-model | reference | ALE 量化公式 | finding-evidence-standard, rules-registry | TRIAGE |
| reproduce-scenarios | reference | SCENE-* | reproducer | REPRODUCE |
| property-test-catalog | pattern-catalog | PBT-FIN-* | invariants, attack-regression-corpus | REPRODUCE/VERIFY |
| attack-regression-corpus | reference | CORP-* | finding-evidence-standard, reproduce-scenarios | VERIFY/RECYCLE |
| rules-registry | registry | RULE-FIN/CON/BIZ/SEC-*, metrics | (all patterns) | FIX/RECYCLE |
| settlement-checklist | reference | 6 類檢查 + 編碼基線 | authorization-ownership, value-authority | FIX |
| oss-debug-security-loop | reference | 工具整合 (Semgrep/CodeQL...) | rules-registry | DETECT/VERIFY |

---

## 2. 依閉環 Stage 的讀取順序

```
Stage 0 THREAT-MODEL → money-flow-map, threat-catalog, authorization-ownership-matrix
Stage 1 DETECT       → financial-{bug,security}-patterns, financial-invariants,
                       value-authority-sanitizer-registry, workflow-state-machine-catalog,
                       persistence-consistency-controls, refund/time/version 補充
                       （產出一律先 candidate，依 finding-evidence-standard）
Stage 2 TRIAGE       → finding-evidence-standard, severity-loss-model, ai-scan-false-positive
Stage 2.5 REPRODUCE  → reproduce-scenarios, property-test-catalog
Stage 4 VERIFY       → financial-invariants, attack-regression-corpus, persistence-consistency
Stage 5 RECYCLE      → knowledge-schema(入庫), rules-registry, compliance-mapping,
                       attack-regression-corpus(新增語料)
```

---

## 3. 三層防線對照

| 防線 | 主要檔 |
|------|--------|
| 特徵比對（已知寫法） | financial-{bug,security}-patterns, rules-registry |
| Taint source→sink（已知攻擊面） | value-authority-sanitizer-registry, money-flow-map, authorization-ownership-matrix |
| 不變量（未知後果的網） | financial-invariants, property-test-catalog, persistence-consistency-controls |

---

## 4. 一致性檢查（防斷鏈/孤島/循環）

```
[ ] 每個 file_id 在本表唯一，且檔案存在
[ ] 每個檔的 frontmatter file_id 與本表一致
[ ] 所有 flows(MF-*) 引用 → money-flow-map 存在該 id
[ ] 所有 invariants(INV-*) 引用 → financial-invariants 存在該 id
[ ] 所有 rule_ref(RULE-*) 引用 → rules-registry 存在該 id
[ ] 交叉引用為單向（pattern→invariant/flow），無 A↔B 循環
[ ] 每個 pattern 至少連 1 flow + 1 invariant（非孤島）
```

> 可用 grep 抽出所有 `MF-`/`INV-`/`RULE-`/`PAT-` 引用，與各登錄檔比對，找出斷鏈。
