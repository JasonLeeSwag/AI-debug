# debug-hunter v2.0 進化總結（驗收用）

> 本輪目標：讓 debug-hunter 更能抓出**金融與財務安全漏洞**。
> 方法：Claude 主導 + Codex / Gemini 三模型交叉覆查（CCG），逐輪共識後落地。
> 日期：2026-06-01

---

## 一眼驗收：做了什麼

| 面向 | v1（原始） | v2.0（本輪後） |
|------|-----------|---------------|
| 偵測軌道 | 正確性 bug | **正確性 + 財務安全/舞弊雙軌** |
| 閉環階段 | 6（DETECT 起） | **7（新增 Stage 0 威脅建模）** |
| 偵測方法 | 特徵比對 | **特徵 + taint source→sink + 不變量 三層防線** |
| knowledge-base | 8 檔 | **24 檔**（全數 schema 化檔頭） |
| agents | 3 | **5**（+threat-modeler, +security-fraud-detector） |
| 知識治理 | 無 | **schema 化 + 證據門檻 + RECYCLE 入庫狀態機（防自我退化）** |
| 風險定級 | 主觀 1~5 | **ALE 期望資損客觀公式** |
| 可執行規則 | 概念 | **Semgrep 規則檔 + pass/fail fixture** |
| 端到端驗證 | 無 | **純 JDK demo，實際編譯執行通過（exit 0）** |

---

## 新增 / 變更檔案清單

### 元結構治理（Tier 0）
- `knowledge-base/knowledge-schema.md` — 條目 YAML schema + RECYCLE 入庫狀態機 + 5 反模式防線
- `knowledge-base/finding-evidence-standard.md` — finding 生命週期 + 證據三件套 + 反證義務
- `knowledge-base/KB-INDEX.md` — 全庫導覽索引 + 一致性檢查

### 業務 ground-truth（Tier 1，提升 recall）
- `authorization-ownership-matrix.md` — 歸屬鏈 + 授權矩陣 + maker-checker（打 IDOR）
- `workflow-state-machine-catalog.md` — 合法狀態躍遷（CWE-841）
- `value-authority-sanitizer-registry.md` — 數值決定權 + 五閘落點（降誤報）
- `persistence-consistency-controls.md` — DB 層防護登錄（confirmed 的 DB 證據）

### 動態驗證與回歸（Tier 2）
- `property-test-catalog.md` — jqwik 屬性測試 + 蛻變測試 + Jazzer fuzzing
- `attack-regression-corpus.md` — 每漏洞 PoC + 違反 INV + 修復後結果

### 補漏與認知（Tier 3）
- `refund-reversal-compensation-patterns.md` — 退款/沖正/補償（資損高發區）
- `time-window-cutoff-calendar-rules.md` — 帳務日/cutoff/T+N/DST
- `domain-glossary.md` — 金融術語對齊（清算vs結算等）
- `severity-loss-model.md` — ALE 期望資損量化
- `version-compatibility-matrix.md` — Java 21 / Spring Boot 3 特有風險

### 安全模式（v2.0 既有）
- `financial-security-patterns.md` — PAT-SEC-101~114（PAT-SEC-101 已 schema 化示範）+ 資料分級附錄
- `financial-invariants.md` — INV-TXN/ST/T
- `money-flow-map.md`, `threat-catalog.md`（+供應鏈分支）, `compliance-mapping.md`（版本經校正）

### 合併進既有檔（不新建，避免碎片化）
- secure-coding-baseline → `settlement-checklist.md`（第七節）
- data-classification → `financial-security-patterns.md`（附錄）
- third-party-risk → `threat-catalog.md`（供應鏈分支）
- detection-metrics → `rules-registry.md`（偵測效能度量）

### 可執行規則與 demo
- `rules/semgrep/financial-security.yml` — RULE-SEC-101/102/106/109 Semgrep 規則
- `rules/semgrep/financial-security.java` — pass/fail 測試 fixture
- `examples/vulnerable-settlement/IdorDemo.java` — 端到端閉環 demo（已驗證通過）

### agents
- `agents/threat-modeler.md`, `agents/security-fraud-detector.md`
- `AGENT.md` 升 v2.0（7 階段 + 雙軌 + 不變量驗收 + 金額計價定級）

---

## 三模型協作紀錄

- **Codex** 貢獻：業務 ground-truth 優先（authorization/state-machine/sanitizer/persistence）、Semgrep 落地範例、demo 必須能 build、外部標準版本校正（ASVS 5.0=V2/4.0.3=V11、PCI v4.0.1、SWC/DASP 已停維護）
- **Gemini** 貢獻：元結構治理（schema/feedback-loop）、反模式（語義漂移/邏輯污染/循環引用/孤島）、ALE 量化公式、KB-INDEX 欄位、glossary 術語
- **Claude** 綜合：分層落地、三層防線整合、一致性與閉環接線、實作與驗證

外部標準事實校正已套用至 `compliance-mapping.md`。

---

## 如何跑

```bash
# 端到端 demo（純 JDK，零依賴）
cd examples/vulnerable-settlement && javac IdorDemo.java && java IdorDemo

# Semgrep 規則測試（需先安裝 semgrep）
semgrep --test rules/semgrep/

# KB 一致性 lint（思路見 KB-INDEX.md 第 4 節）
for f in knowledge-base/*.md; do head -1 "$f" | grep -q '^---$' || echo "缺 frontmatter: $f"; done
```

---

## 後續 TODO（未做，留待你決定）

- [ ] 將 RULE-SEC-103/104/108/112 等語意型規則以 CodeQL 實作（Semgrep 易誤報）
- [ ] 把更多 PAT-SEC 條目補上機器可讀 YAML 區塊（目前示範了 PAT-SEC-101）
- [ ] demo 擴充第二個漏洞（偽造回調 PAT-SEC-104）展示外部信任邊界
- [ ] 為 Semgrep 規則接 CI gate（PR 觸發）
- [ ] money-flow-map 以實際專案金流補齊（目前為範本骨架）
- [x] 安裝 semgrep 後實跑 `--test` 驗證規則 fixture → **semgrep 1.144.0 `--test` 5/5 規則通過、0 失敗、exit 0；直接掃描確認 6 個 finding 全部命中 vuln 行、安全行零誤報**
- [x] 統一測試/語料命名 → property test 用 `PBT-FIN-01~03`、回歸語料用 `CORP-001~003`，全庫零殘留舊命名
- [x] 修復 codex 平行寫入造成的 `financial-security.yml` 結構損壞（重複鍵）→ 規則重寫為可靠命中
