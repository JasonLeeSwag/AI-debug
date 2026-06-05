---
file_id: money-flow-map
kind: inventory
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 90
owner: threat-modeler-agent
external_refs: ["OWASP API Top 10 2023#API9"]
---

# 資金流地圖（Money-Flow Map）— 活文件

> 檔案路徑：knowledge-base/money-flow-map.md
> 用途：枚舉系統中**所有「錢會移動」的路徑**，作為 Stage 0 威脅建模與 taint 偵測的根本基準。
> 維護者：`agents/threat-modeler.md`（每次掃描更新）、人工架構審查
> 核心價值：**沒有完整的資金流清單，就不可能宣稱「掃過所有攻擊面」。** 這份地圖是「覆蓋率誠實」的依據。

---

## 為何資金流地圖是一切的起點

漏洞發生在「錢移動」的地方。若連系統有幾條金流都列不齊，偵測就只是碰運氣。本地圖回答四個問題：
1. **錢從哪進 / 哪出**（入口與匯點）
2. **金額由誰決定**（使用者？前端？後端權威？外部）——這決定了竄改風險
3. **信任邊界在哪**（不可信→可信的轉換點，即清洗閘應在之處）
4. **這條金流可能違反哪條不變量**（連到 `financial-invariants.md`）

---

## 欄位定義

| 欄位 | 說明 |
|------|------|
| flow_id | 唯一編號 MF-NN |
| 入口 | HTTP 端點 / Kafka topic / 排程 / 回調 |
| 觸發者 | 使用者 / 系統 / 外部 / 排程 |
| 資金匯點 | credit / debit / settle / withdraw / transfer / ledger.post / 動態 SQL |
| 金額決定權 | request（高危）/ frontend（高危）/ backend（權威）/ external（需比對） |
| 信任邊界 | 哪個方法/層是不可信→可信的轉換點 |
| 必備清洗閘 | 歸屬 / 數值域 / 授權 / 完整性 / 原子性（缺哪個） |
| 風險不變量 | INV-* |
| 對應威脅 | PAT-SEC-* / 見 threat-catalog.md |
| 覆蓋狀態 | 未建模 / 已建模 / 已掃描 / 已驗證 |

---

## 資金流清單（範例骨架，依實際系統補齊）

| flow_id | 入口 | 觸發者 | 資金匯點 | 金額決定權 | 必備清洗閘 | 風險不變量 | 對應威脅 | 覆蓋狀態 |
|---------|------|--------|---------|-----------|-----------|-----------|---------|---------|
| MF-01 | POST /api/withdraw | 使用者 | walletService.debit | request | 歸屬+數值域+原子+速率 | INV-ST-01 | PAT-SEC-101/102/103/112 | 未建模 |
| MF-02 | POST /api/transfer | 使用者 | debit+credit | request | 歸屬+數值域+重放 | INV-TXN-01 | PAT-SEC-102/107 | 未建模 |
| MF-03 | Kafka settlement-close | 系統 | settlementService.settle | external(行情) | 完整性+冪等 | INV-ST-03/INV-T-02 | PAT-CON-001/PAT-BIZ-003/PAT-SEC-105 | 已掃描 |
| MF-04 | POST /payment/callback | 外部閘道 | order.markPaid+credit | external | 完整性(簽章)+我方比對 | INV-T-03 | PAT-SEC-104 | 未建模 |
| MF-05 | POST /admin/adjustBalance | 內部人員 | walletService.credit | request | 授權(maker-checker)+審計 | INV-T-01 | PAT-SEC-108/110 | 未建模 |
| MF-06 | 領券/返現 promo | 使用者 | discount/credit | backend | 數值域+互斥+一次性 | INV-TXN-05 | PAT-SEC-113 | 未建模 |
| MF-07 | GET /api/ledger（報表） | 使用者 | 動態 SQL 查詢 | request | 數值域(參數化)+歸屬 | — | PAT-SEC-109 | 未建模 |
| MF-08 | 批次結算 PowerJob | 排程 | batchUpWallets | backend | 原子(行鎖/版本) | INV-ST-02 | PAT-CON-004 | 已掃描 |

> ⚠️ 覆蓋率誠實：上表為**範本骨架**。實際導入時必須以程式碼掃描補齊真實金流，並明確標示「尚未建模」的金流，避免假完整感。

---

## 維護規則

1. 新增資金端點 / MQ / 回調 / 排程 → 立即在此登錄一列，狀態起始為「未建模」
2. Stage 0 威脅建模後 → 更新「對應威脅」與狀態為「已建模」
3. Stage 1 掃描後 → 狀態「已掃描」；Stage 4 驗收後 → 「已驗證」
4. 每次 release 前檢視：是否有「未建模 / 未掃描」的金流？有則 block
5. 與 `threat-catalog.md`、`financial-invariants.md`、`financial-security-patterns.md` 三向連動
