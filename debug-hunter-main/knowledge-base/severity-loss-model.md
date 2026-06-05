---
file_id: severity-loss-model
kind: reference
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 180
owner: knowledge-writer-agent
---

# 漏洞等級與損失量化模型（Severity & Loss Model）

> 地位：**決策與優先級核心**。將主觀的「我覺得很嚴重」轉化為機器可讀的風險分值。

---

## 1. 風險分值公式

$$RiskScore = (Impact_{Financial} + Impact_{Compliance} + Impact_{Reputation}) \times Likelihood$$

### A. 財務影響 (Financial Impact)
| 等級 | 直接損失金額 (USD 等值) | 分值 |
| :--- | :--- | :--- |
| 極大 | > $1,000,000 | 10 |
| 重大 | $100,000 - $1,000,000 | 7 |
| 一般 | $10,000 - $100,000 | 4 |
| 輕微 | < $10,000 | 1 |

### B. 合規影響 (Compliance Impact)
| 類別 | 描述 | 分值 |
| :--- | :--- | :--- |
| 吊銷牌照 | 違反 PCI-DSS, AML 或國家級金融法規，面臨停業風險 | 10 |
| 重額罰金 | 引發監管機構正式調查並預期處以重罰 | 6 |
| 警告合規 | 輕微違反數據隱私或報告要求 | 2 |

### C. 可能性 (Likelihood / Likelihood_Exploit)
| 級別 | 描述 | 分值 |
| :--- | :--- | :--- |
| 確定性 | 公網無需權限即可利用 (RCE, Auth Bypass) | 1.0 |
| 高 | 需普通用戶權限或內網存取 (IDOR, SQLi) | 0.7 |
| 中 | 利用條件苛刻，涉及複雜競態或特定時鐘週期 | 0.4 |
| 低 | 需多個高權限帳號協作或非標準配置 | 0.1 |

---

## 2. 等級映射矩陣 (Severity Mapping)

| RiskScore | Severity 等級 | 對應處理要求 |
| :--- | :--- | :--- |
| 15 - 20 | **P0 (Critical)** | 立即熔斷業務，2小時內修復，CTO 介入 |
| 10 - 14 | **P1 (High)** | 當日修復，回溯受影響帳戶，Security Head 介入 |
| 5 - 9 | **P2 (Medium)** | 下一迭代修復，加強審計日誌 |
| < 5 | **P3 (Low)** | 記錄在案，視成本優化 |

---

## 3. 自動判定邏輯（AI 調用）

當 AI 發現一個 Finding 時，應：
1. **識別 Affected Objects**: 判定受影響的是「全系統」、「特定商戶」還是「單一用戶」。
2. **查詢 `money-flow-map`**: 判定匯點 (Sink) 是否涉及核心清結算。
3. **計算 $Likelihood$**: 檢查路徑上的 `required_sanitizers` 缺失程度。
4. **輸出 Severity**: 依上述矩陣給出定級理由。
