# SWAG 平台漏洞示例程式碼

本目錄包含 SWAG 平台（swag.live）常見安全漏洞的示例程式碼，**僅供 QA 部門教育訓練使用**。

---

## 警告

> 此目錄內所有程式碼均**故意包含安全漏洞**，絕對不可部署至任何正式或測試環境。
> 程式碼目的是協助 QA 工程師辨識漏洞樣式，並理解對應的安全修復方式。

---

## 檔案說明

| 檔案 | 語言 | 涵蓋漏洞 |
|------|------|----------|
| `vulnerable_gambling.py` | Python | PAT-GAM-001（不安全亂數）、PAT-GAM-002（float 精度）、PAT-CRED-003（TOCTOU）、PAT-PAY-001（缺簽章驗證） |

---

## 漏洞對應規則

本目錄示例程式碼對應 `rules/semgrep/swag-security.yml` 中定義的規則：

- **RULE-GAM-001**：博弈遊戲禁止使用 `random` 模組，應使用 `secrets`
- **RULE-GAM-002**：賠率/賠付計算應使用 `Decimal`，不得使用 `float`
- **RULE-CRED-001**：點數計算禁止使用 `float`
- **RULE-CRED-002**：點數餘額更新必須使用原子操作（Django `F()` 或 `SELECT FOR UPDATE`）
- **RULE-PAY-001**：支付回調必須先驗證簽章再入帳
- **RULE-PAY-002**：支付回調必須比對回調金額與訂單金額
- **RULE-SEC-001**：資金操作必須使用 JWT 認證的 user_id，不得信任請求參數

---

## 如何使用 Semgrep 掃描

```bash
# 掃描本目錄
semgrep scan --config ../../rules/semgrep/swag-security.yml .

# 掃描並輸出 JSON 報告
semgrep scan --config ../../rules/semgrep/swag-security.yml . --json > report.json
```

---

## 聯絡

QA 部門 - SWAG Platform Security Team
