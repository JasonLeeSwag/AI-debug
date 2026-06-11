請對以下程式碼或功能模組執行 SWAG 專屬 Bug 與安全掃描：**$ARGUMENTS**

## 你的任務

1. 讀取 `AGENT.md` 的 DETECT 階段指引
2. 依據業務模組選擇對應知識庫：
   - 博弈遊戲 → `knowledge-base/gambling-game-patterns.md`
   - 金流支付 → `knowledge-base/payment-gateway-patterns.md`
   - 直播打賞 → `knowledge-base/streaming-platform-patterns.md`
   - 通用業務 → `knowledge-base/swag-bug-patterns.md`
   - 業務邏輯 → `knowledge-base/swag-business-logic.md`

## 執行步驟

**Step 1：確認輸入**
若用戶尚未提供程式碼，請求提供：程式碼片段 / PR diff / 功能說明

**Step 2：業務不變量核查**
對照以下不變量逐一比對：
- `INV-PAY-*`：充值金額守恆、回調冪等、簽章防篡改
- `INV-GAME-*`：下注餘額守恆、下注時效守衛
- `INV-STR-*`：打賞扣加守恆、鑽石 Log 必存
- `INV-LIVE-MOO-*`：邀請排他、一對一計費、Show 阻擋機制

**Step 3：安全漏洞掃描**
依照 `knowledge-base/financial-security-patterns.md` 檢查：
- IDOR / 越權
- Mass Assignment
- 重放攻擊
- 審計日誌缺失

**Step 4：輸出報告**
格式：
```
## 🔴 BUG-001：[問題標題]（P0/P1/P2）
位置：[檔案:行號]
問題：[說明]
修復：[具體修復方案或程式碼]
```
並在報告末尾附上：違反的不變量 ID + 建議補充的測試案例
