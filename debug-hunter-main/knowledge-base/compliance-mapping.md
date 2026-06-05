---
file_id: compliance-mapping
kind: registry
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 180
owner: knowledge-writer-agent
external_refs: ["PCI-DSS v4.0.1", "OWASP ASVS 4.0.3", "OWASP API Top 10 2023", "SOC2", "AML/CFT"]
---

# 合規對應庫（Compliance Mapping）

> 檔案路徑：knowledge-base/compliance-mapping.md
> 用途：把每個 PAT / RULE / INV 對應到外部法規與標準條目，讓技術發現可被**稽核追溯**，並滿足金融監理要求。
> 維護者：`agents/knowledge-writer.md`（Stage 5 RECYCLE 的合規對應步驟）
> 核心價值：金融系統的漏洞不只是技術債，更是**合規事件**。修了 bug 卻無法對監理證明「已控管」，等於沒修。

---

## 涵蓋的標準

| 標準 | 適用範圍 | 與本專案最相關處 |
|------|---------|-----------------|
| **PCI-DSS v4.0.1** | 持卡資料處理 | 敏感資料保護、存取控制、審計、加密 |
| **OWASP ASVS 4.0.3** | 應用安全驗證 | 業務邏輯（V11）、存取控制（V4）、輸入驗證（V5） |
| **OWASP API Security Top 10 (2023)** | API 安全 | 優先映射 API1(BOLA=IDOR)/API3(屬性授權)/API5(功能授權)/API6(敏感業務流)/API9(清單治理)/API10(不安全消費) |
| **AML / CFT（反洗錢/反資恐）** | 金流監控 | 交易監控、可疑交易、velocity、制裁名單 |
| **SOC 2 (Trust Services)** | 服務組織控制 | 變更管理、審計軌跡、職責分離 |
| **個資法 / GDPR** | 個人資料 | PII 最小化、遮罩、洩漏通報 |
| **SWIFT CSP**（如涉跨行） | 銀行間訊息 | 訊息完整性、雙人覆核 |

---

## PAT-SEC ↔ 合規條目對應

| 我方模式 | PCI-DSS | OWASP ASVS | OWASP API | AML/CFT | SOC2 | 個資/GDPR |
|---------|---------|-----------|-----------|---------|------|-----------|
| PAT-SEC-101 IDOR | Req 7 存取控制 | V4.1 物件級授權 | **API1 BOLA** | — | CC6.1 | — |
| PAT-SEC-102 金額竄改 | — | V5 輸入驗證 | API6 | — | — | — |
| PAT-SEC-103 TOCTOU 雙花 | — | V11.1.2 業務限制 | — | — | — | — |
| PAT-SEC-104 回調偽造 | Req 4 傳輸保護 | V11 業務邏輯 | API8 | — | CC6.6 | — |
| PAT-SEC-105 預言機操縱 | — | V11 業務邏輯 | — | 市場操縱監控 | — | — |
| PAT-SEC-106 mass assignment | — | V5.1.2 | **API3 屬性授權** | — | — | — |
| PAT-SEC-107 重放 | Req 4 | V11.1.4 反重放 | — | — | — | — |
| PAT-SEC-108 缺雙人覆核 | Req 7 最小權限 | V4.2 | — | 內控/職責分離 | **CC6.3 職責分離** | — |
| PAT-SEC-109 SQL 注入 | Req 6.2 | V5.3.4 | API8 | — | — | — |
| PAT-SEC-110 缺審計 | **Req 10 審計** | V7 日誌 | — | 交易紀錄保存 | **CC7.2** | — |
| PAT-SEC-111 敏感資料外洩 | **Req 3 儲存保護** | V8 資料保護 | — | — | — | **最小化/遮罩** |
| PAT-SEC-112 缺 velocity | — | V11.1.3 速率 | API4 資源限制 | **交易監控/可疑交易** | — | — |
| PAT-SEC-113 優惠套利 | — | V11.1 業務限制 | — | — | — | — |
| PAT-SEC-114 弱冪等鍵 | — | V11.1.4 | — | — | — | — |

---

## 不變量 ↔ 合規（事中/事後控制）

| 不變量 | 合規意義 |
|--------|---------|
| INV-ST-03 資產守恆 | AML 對帳完整性、財報正確性（SOC2） |
| INV-T-01 可追溯審計 | PCI Req 10、SOC2 CC7、監理紀錄保存 |
| INV-T-03 內外對帳一致 | AML T+1 對帳、清算正確性 |
| INV-T-02 冪等不重複 | 財務正確性、避免重複入帳爭議 |

---

## AML / CFT 專屬控制檢查（金流監控）

> 多數技術掃描忽略 AML，但對金融系統是強制監理。建議納入 Stage 0/4。

```
[ ] 大額交易申報門檻監控（單筆/單日累計）
[ ] 可疑交易樣態偵測（拆單規避、快進快出、循環轉帳）
[ ] 制裁名單 / PEP 篩查（OFAC / 聯合國 / 在地名單）於入金、提款、轉帳前
[ ] velocity 規則（PAT-SEC-112）作為可疑交易訊號來源
[ ] 凍結 / 暫停能力（與 incident playbook 連動）
[ ] 交易紀錄保存年限符合在地法規（通常 5~7 年，append-only）
```

---

## RECYCLE 合規對應步驟（knowledge-writer 執行）

1. 新安全發現 → 在上表登錄其對應的合規條目
2. 修復方案 → 標注「滿足哪條控制要求」，供稽核引用
3. 若發現缺口屬監理強制（如 Req 10 審計、AML 篩查）→ 自動升 P0
4. 季度匯出「合規覆蓋報告」：哪些控制有對應 RULE/INV 保護、哪些仍是空白

---

## 維護備註

> **版本校正（2026-06，經三模型交叉覆查）**：
> - 本表 ASVS 章節號（V4/V5/V11）對應 **ASVS 4.0.3**。**ASVS 5.0 已將「業務邏輯」由 V11 重組為 V2（Validation & Business Logic）**，升級時須整批對應新章節，勿沿用舊號。
> - PCI-DSS 以 **v4.0.1** 為準。
> - **SWC Registry（2020 起）與 DASP Top 10（2018）官方已停止積極維護**，僅作 DeFi 歷史 crosswalk；若涉鏈上資產，主索引改用維護中標準。
> 法規條號會改版，每次更新後校對。在地監理（台灣金管會、虛擬資產函令）需另行補充，本檔以國際標準為骨幹。
