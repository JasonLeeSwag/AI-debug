# SWAG 直播平台與 API 買分後台不變量與防禦指南 (Streaming & Admin Invariants)

> **檔案識別碼**: streaming-invariants
> **適用範疇**: SWAG 成人直播平台 (swag.live)、直播間互動、主播打賞、API 買分/調帳後台。
> **技術棧**: Python (Admin API), Node.js, React/JSX, JS, RobotFramework, Playwright, Appium

---

## 1. 直播與後台核心不變量 (Streaming & Admin Invariants)

SWAG 直播平台（swag.live）結合了高流量直播與即時打賞，而 API 買分後台則是代理商與商戶的管理中樞。這兩者在業務邏輯與權限控制上必須嚴格遵守以下不變量。

| 不變量 ID | 名稱 | 數學/邏輯定義 | 驗證機制 (Assert/Check) |
| :--- | :--- | :--- | :--- |
| **INV-STR-01** | **打賞扣加守恆** | `用戶扣除鑽石數 == 主播增加鑽石數 + 平台抽成` | 打賞操作必須在單一數據庫事務中完成，且兩端動帳金額必須完全匹配。 |
| **INV-STR-02** | **付費解鎖時效** | `解鎖付費內容 (如私密影片) -> 用戶獲得永久/限時訪問權` | 解鎖記錄必須持久化，防止用戶重複點擊解鎖導致多次扣款。 |
| **INV-ADM-01** | **買分/調帳雙人覆核** | `後台調帳金額 > 門檻 -> 必須 Maker-Checker 審批` | 嚴禁單一管理員帳號直接對商戶或用戶進行大額無授權加分。 |
| **INV-ADM-02** | **商戶額度守恆** | `商戶給用戶加分 -> 商戶自身額度扣除等值分數` | 商戶（Agent）不能憑空創造分數，必須先向平台「買分」充實自身額度。 |
| **INV-ADM-03** | **API 密鑰安全** | `API 請求簽章驗證 == TRUE` 且 `IP 白名單 == TRUE` | 買分 API 後台必須強制執行 IP 白名單校驗與 HMAC 簽章驗證。 |

---

## 2. 常見直播與後台 Bug 模式與攻擊路徑

### PAT-STR-101: 禮物打賞並發「免費送」 (Concurrent Gifting / Race Condition)
*   **觸發特徵**: 用戶在直播間點擊送禮（如跑車、火箭）時，後端未對用戶錢包進行並發鎖定，而是異步異步扣款。
*   **攻擊路徑**: 攻擊者帳戶僅有 10 鑽石，一個火箭需要 1000 鑽石。攻擊者使用自動化腳本，在幾毫秒內向 API 發送 500 次「送火箭」請求。因為異步扣款隊列處理延遲，前幾百個請求未檢測到餘額不足，導致主播收到了價值數十萬鑽石的火箭，而攻擊者未花一分錢。
*   **防禦策略**:
    ```python
    # Python 打賞扣款防禦（使用 Redis 分布式鎖與原子扣減）
    def send_gift(user_id, anchor_id, gift_id):
        gift = Gift.objects.get(id=gift_id)
        lock_key = f"wallet_lock:{user_id}"
        
        # 1. 獲取用戶錢包分布式鎖，超時時間 3 秒
        with redis.lock(lock_key, timeout=3):
            wallet = UserWallet.objects.get(user_id=user_id)
            if wallet.balance < gift.price:
                raise InsufficientBalanceException("鑽石不足！")
                
            # 2. 原子扣減
            wallet.balance -= gift.price
            wallet.save()
            
            # 3. 增加主播收益
            anchor_wallet = AnchorWallet.objects.get(anchor_id=anchor_id)
            anchor_wallet.diamonds += gift.anchor_share
            anchor_wallet.save()
    ```

### PAT-ADM-101: 買分後台越權調帳 (B2B Admin IDOR)
*   **觸發特徵**: API 買分後台接口（如 `/api/admin/agent/transfer`）僅依賴前端傳遞的 `agent_id` 或 `merchant_id`，未在後端校驗當前登錄的 Token 是否擁有操作該商戶的權限。
*   **攻擊路徑**: 攻擊者（二級代理商）登錄後台，攔截調帳請求，將 `agent_id` 修改為一級代理商或平台的 `agent_id`，從而**直接調用一級代理商的額度**給自己的用戶加分。
*   **防禦策略**: 嚴格執行**基於角色的權限控制 (RBAC)**。後端必須從加密 Token（如 JWT）中解析出當前操作者的 `user_id` 和 `role`，並從數據庫中查詢其隸屬關係，嚴禁直接信任請求體 (Body) 中的權限或身份參數。

### PAT-ADM-102: 商戶買分 API 重放攻擊 (Replay Attack)
*   **觸發特徵**: 商戶對接 SWAG 的買分接口（B2B API）未引入隨機數（Nonce）與時間戳（Timestamp）校驗。
*   **攻擊路徑**: 攻擊者攔截了一次成功的買分 API 請求封包（包含合法的簽章）。因為沒有時間戳校驗，攻擊者原封不動地多次重送（Replay）該請求，導致系統**重複執行加分**。
*   **防禦策略**:
    ```python
    # B2B API 簽章與防重放校驗
    def validate_b2b_request(request):
        signature = request.headers.get('X-SWAG-Signature')
        timestamp = int(request.headers.get('X-SWAG-Timestamp'))
        nonce = request.headers.get('X-SWAG-Nonce')
        
        # 1. 限制請求時效在 5 分鐘內，防範歷史請求重放
        current_time = int(time.time())
        if abs(current_time - timestamp) > 300:
            raise SecurityException("Request expired!")
            
        # 2. 檢查 Nonce 是否重複使用（使用 Redis 緩存 5 分鐘）
        if not redis.set(f"api_nonce:{nonce}", "1", ex=300, nx=True):
            raise SecurityException("Replay attack detected!")
            
        # 3. 驗證 HMAC 簽章
        payload = request.body
        expected_sig = hmac.new(SECRET_KEY, payload, hashlib.sha256).hexdigest()
        if not hmac.compare_digest(expected_sig, signature):
            raise SecurityException("Signature verification failed!")
    ```

---

## 3. SWAG QA 直播與後台自動化測試與 Bug 偵測劇本

### RobotFramework 買分後台 API 越權測試 (IDOR 偵測)
```robot
*** Settings ***
Library    RequestsLibrary
Library    Collections

*** Variables ***
${BASE_URL}          https://admin.swag.live/api/v1
${TRANSFER_URL}      /agent/transfer
${SUB_AGENT_TOKEN}   Bearer_Sub_Agent_Token_Here

*** Test Cases ***
Verify Sub Agent Cannot Transfer From Master Agent Account
    [Documentation]    測試二級代理商是否能篡改參數，從一級代理商帳戶中調帳。
    Create Session    admin_api    ${BASE_URL}
    ${headers}=    Create Dictionary    Authorization=${SUB_AGENT_TOKEN}    Content-Type=application/json
    # 故意將 source_agent_id 設為一級代理商 (ID: 8888)，target_user_id 設為自己的測試帳號
    ${data}=    Create Dictionary    source_agent_id=8888    target_user_id=9999    amount=50000
    ${response}=    POST On Session    admin_api    ${TRANSFER_URL}    json=${data}    headers=${headers}    expected_status=403
    Should Contain    ${response.text}    Permission denied
```

### Playwright / Appium 直播間並發打賞測試 (Race Condition Test)
```javascript
const { test, expect } = require('@playwright/test');

test('直播間極速連續送禮測試（防禦並發免費送禮）', async ({ page }) => {
  // 1. 登錄測試帳號（餘額調整為僅能買 1 個禮物，例如 50 鑽石）
  await page.goto('https://swag.live/anchor/test_anchor_01');
  
  // 2. 開啟並發請求監聽
  let successCount = 0;
  let failedCount = 0;
  
  page.on('response', response => {
    if (response.url().includes('/api/v1/live/gift')) {
      if (response.status() === 200) {
        successCount++;
      } else if (response.status() === 400) {
        failedCount++;
      }
    }
  });

  // 3. 模擬極速點擊「送禮物」按鈕 10 次 (每次 50 鑽石)
  const giftButton = page.locator('button[data-gift-id="gift_50"]');
  await giftButton.waitFor({ state: 'visible' });
  
  // 使用 Promise.all 並發點擊
  await Promise.all([
    giftButton.click({ clickCount: 5, delay: 5 }),
    giftButton.click({ clickCount: 5, delay: 5 })
  ]);

  // 4. 斷言：成功的次數「絕對不能大於 1」
  console.log(`Success Gifting: ${successCount}, Failed Gifting: ${failedCount}`);
  expect(successCount).toBeLessThanOrEqual(1);
});
```
