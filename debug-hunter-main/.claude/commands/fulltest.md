請為以下版本或功能產出完整的 FullTest 驗收清單：**$ARGUMENTS**

## 你的任務

1. 讀取 `knowledge-base/swag-test-process.md` 的 FullTest 標準流程
2. 讀取 `knowledge-base/swag-business-logic.md` 確認業務不變量
3. 讀取 `knowledge-base/swag-product-map.md` 確認受影響的產品範圍

## 執行步驟

**Step 1：確認測試範圍**
若用戶尚未說明，詢問：
- 本次版本變更了哪些功能模組？
- 需要測試哪些產品（Web / Moor / Ramen / Sushi）？
- 是否包含金流變更？（若有，觸發支付 FullTest）

**Step 2：產出分層清單**
依以下分類輸出 Checkbox 格式清單：

### 直播核心功能
- 一般直播、Show、一對一、一對多流程
- 邀請機制、計費、退款

### 影片與內容
- 長影片、短影音、限時動態上傳與購買

### 金流（若適用）
- 信用卡儲值（必測）
- AFTEE 先享後付（必測）
- ⚠️ 支付寶/轉帳/虛擬幣：FullTest 不需測試

### 帳號功能
- 電話/Email 修改（不可刪除驗證）
- VIP 等級顯示
- 封鎖管理

### Ramen / China App（若有涉及）
- 6 城市載入時間 < 10 秒
- SWAG 字樣隱藏確認
- API 加密 header 存在

**Step 3：依嚴重度排序**
P0 項目排最前面，並標注「🔴 必過才能上線」

**Step 4：產出測試帳號需求清單**
根據清單列出需要準備的帳號組合（參考 `knowledge-base/swag-test-accounts.md`）
