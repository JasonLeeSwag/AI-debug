---
file_id: threat-catalog
kind: pattern-catalog
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 180
owner: threat-modeler-agent
external_refs: ["OWASP API Top 10 2023", "MITRE ATT&CK"]
---

# 威脅目錄（Threat Catalog）— STRIDE-FIN + 濫用案例

> 檔案路徑：knowledge-base/threat-catalog.md
> 用途：以**攻擊劇本層**補強 `financial-security-patterns.md`（程式碼層）。Patterns 答「程式怎麼寫錯」，本檔答「攻擊者想達成什麼、怎麼達成」。
> 維護者：`agents/threat-modeler.md`
> 連動：每個威脅 → 對應 money-flow-map 的 MF-*、financial-security-patterns 的 PAT-SEC-*、financial-invariants 的 INV-*

---

## 為何要威脅目錄（而非只有 patterns）

特徵庫是「後見之明」——只收錄看過的寫法。威脅目錄是「前瞻假設」——從攻擊者**目標**出發，即使我們沒看過某段程式碼，也能問「攻擊者要偷錢，這條金流有沒有給他機會？」。這讓偵測從「特徵驅動」升級為「假設驅動」，能抓未知模式。

---

## STRIDE-FIN 威脅總表

| 威脅類 | 攻擊者目標 | 金融化提問 | 對應 Pattern | 對應不變量 |
|--------|-----------|-----------|-------------|-----------|
| Spoofing 偽冒 | 假扮他人/可信來源 | 能否冒用身分動帳？偽造回調/簽章？ | PAT-SEC-101/104 | INV-T-03 |
| Tampering 竄改 | 改數值/狀態獲利 | 能否改金額/餘額/狀態/手續費？ | PAT-SEC-102/106/114 | INV-TXN-02 |
| Repudiation 抵賴 | 否認自己的操作 | 動帳後能否抵賴？審計可竄改？ | PAT-SEC-110 | INV-T-01 |
| Info Disclosure 洩漏 | 取得他人資金資訊 | 餘額/PII/卡號會否外洩或越權查詢？ | PAT-SEC-109/111 | — |
| DoS / Drain 掏空 | 快速抽乾資金 | 能否無限速提款？放大其他漏洞？ | PAT-SEC-112 | INV-ST-01 |
| Elevation 提權 | 取得高權限操作 | 能否越權調帳？單人完成高權限？ | PAT-SEC-108 | INV-T-01 |
| Abuse 業務濫用（金融特有） | 利用業務規則套利 | 雙花/重放/優惠疊加/預言機操縱？ | PAT-SEC-103/105/107/113 | INV-ST-03 |

---

## 濫用案例庫（Abuse Cases）

格式：「身為 ___（攻擊者角色），我嘗試 ___（動作），期望 ___（獲利），系統若缺 ___（防線）則得逞。」

| abuse_id | 攻擊者 | 動作 | 期望獲利 | 缺失防線 | 對應 MF / PAT / INV |
|----------|--------|------|---------|---------|---------------------|
| AB-01 | 一般使用者 | 改 accountId 為他人 | 提領他人資金 | 帳戶歸屬校驗 | MF-01 / PAT-SEC-101 / INV-ST-01 |
| AB-02 | 一般使用者 | amount 送負數 | 反向入帳造錢 | 數值域校驗 | MF-02 / PAT-SEC-102 / INV-TXN-02 |
| AB-03 | 腳本攻擊者 | 並發 20 筆提款 | 超提（雙花） | 原子扣款/鎖 | MF-01 / PAT-SEC-103 / INV-ST-01 |
| AB-04 | 任意外部 | POST 偽造支付成功 | 白嫖入帳 | 回調簽章+金額比對 | MF-04 / PAT-SEC-104 / INV-T-03 |
| AB-05 | 持倉者 | 結算瞬間拉抬/砸盤價格 | 定向獲利 | 多源中位數+偏離熔斷 | MF-03 / PAT-SEC-105 / INV-ST-03 |
| AB-06 | 一般使用者 | body 夾帶 balance 欄位 | 直接改餘額 | DTO 白名單 | MF-01 / PAT-SEC-106 / INV-ST-02 |
| AB-07 | 中間人 | 攔截後重送提款封包 | 重複轉帳 | nonce+時間窗+簽章 | MF-02 / PAT-SEC-107 / INV-T-04 |
| AB-08 | 內部人員 | 單人後台調帳 | 掏空+難追責 | maker-checker+審計 | MF-05 / PAT-SEC-108 / INV-T-01 |
| AB-09 | 一般使用者 | 報表參數注入 SQL | 竊取全帳本 | 參數化+白名單 | MF-07 / PAT-SEC-109 |
| AB-10 | 羊毛黨 | 疊加多券+自我推薦 | 群體套利 | 互斥+上限+一次性 | MF-06 / PAT-SEC-113 / INV-TXN-05 |
| AB-11 | 被盜帳號 | 高頻提款搶在風控前 | 加速掏空 | 速率+velocity+凍結 | MF-01 / PAT-SEC-112 |
| AB-12 | 一般使用者 | 猜他人冪等鍵 | 干擾/覆蓋他人交易 | 高熵鍵+簽章綁定 | MF-02 / PAT-SEC-114 |

---

## 威脅建模 SOP（threat-modeler 執行）

1. 取 `money-flow-map.md` 每條 MF-*
2. 逐一套 STRIDE-FIN 七類，問對應提問
3. 命中 → 從濫用案例庫挑/新增 AB-*，寫出攻擊者劇本
4. 標注：候選 PAT-SEC、風險 INV、可達性、攻擊成本
5. 依「資金可達性 × 低攻擊成本」排序，輸出待驗證威脅清單給 detector
6. 找不到對應已知 Pattern 的金流 → 標「新攻擊面」，優先人工深究

---

## 新增威脅（模板）

```markdown
| AB-NN | {攻擊者角色} | {動作} | {期望獲利} | {缺失防線} | {MF-* / PAT-SEC-* / INV-*} |
```

> 第三方/供應鏈風險（webhook 偽造須 Pull-over-Push 主動核實、依賴 RCE 如 Fastjson、外部回應視為 taint source）已整合於上方「供應鏈 / 上游信任失效」節。
