# SWAG 前端網頁與 App 交互防禦指南 (Frontend & Mobile App Defenses)

> **檔案識別碼**: frontend-app-defenses
> **適用範疇**: SWAG Web (swag.live)、React/JSX、Flutter Web、Mobile App (Appium 測試、Flutter App)
> **技術棧**: React/JSX, JS, Flutter, Appium, Playwright

---

## 1. 前端與 App 交互核心不變量 (Frontend & Mobile Invariants)

在成人直播與博弈平台中，前端（React/JSX, Flutter Web）和移動端（Flutter App）是與用戶直接交互的第一線。雖然前端不負責最終的資金和遊戲結算，但前端的安全性直接決定了用戶體驗和惡意用戶的攻擊難度。

| 不變量 ID | 名稱 | 數學/邏輯定義 | 驗證機制 (Assert/Check) |
| :--- | :--- | :--- | :--- |
| **INV-FE-01** | **本地與服務端狀態同步** | `UI.Balance == Server.Balance` | 嚴禁在前端本地修改鑽石餘額，所有餘額顯示必須以服務端返回為準。 |
| **INV-FE-02** | **輸入邊界校驗** | `UI.Input.Amount` 必須通過格式、正值與上限校驗 | 前端輸入框（如充值金額、投注金額）必須限制只能輸入正整數，防止溢出或負數繞過。 |
| **INV-MOB-01** | **SSL Pinning 安全性** | `App.Connection.Certificate == Server.Certificate` | SWAG App 必須啟用 SSL Pinning，防止攻擊者通過 Fiddler/Charles 抓包並篡改 API。 |
| **INV-MOB-02** | **本地緩存不敏感** | `Local_Storage` 嚴禁存儲未加密的 Token、密碼或鑽石數 | 敏感信息必須加密存儲於安全區域（如 iOS Keychain / Android Keystore）。 |

---

## 2. 常見前端與移動端 Bug 模式與攻擊路徑

### PAT-FE-101: 負數/特殊字符輸入繞過 (Negative Input Bypass)
*   **觸發特徵**: React/JSX 輸入框（如打賞、充值、投注）僅使用了 HTML5 的 `type="number"`，而沒有在 React 狀態變更或提交時進行嚴格的非負校驗。
*   **攻擊路徑**: 攻擊者通過 Chrome 開發者工具修改 DOM，去掉 `min="1"` 限制，或者直接通過 Postman 發送 `{"amount": -1000}`。如果後端也未做校驗，可能導致**帳戶餘額不減反增**（扣除負數等於加分）。
*   **防禦策略**:
    ```jsx
    // React / JSX 防禦範例：嚴格受控組件與數值校驗
    import React, { useState } from 'react';

    export function BetInput({ onBetSubmit }) {
      const [betAmount, setBetAmount] = useState('');

      const handleInputChange = (e) => {
        const val = e.target.value;
        // 僅允許正整數輸入，過濾掉 '-', '+', 'e', '.' 等特殊字符
        if (/^\d*$/.test(val)) {
          setBetAmount(val);
        }
      };

      const handleSubmit = () => {
        const amount = parseInt(betAmount, 10);
        if (isNaN(amount) || amount <= 0) {
          alert("請輸入有效的投注金額！");
          return;
        }
        onBetSubmit(amount);
      };

      return (
        <div>
          <input 
            type="text" 
            value={betAmount} 
            onChange={handleInputChange} 
            placeholder="請輸入鑽石數"
          />
          <button onClick={handleSubmit}>投注</button>
        </div>
      );
    }
    ```

### PAT-MOB-101: Flutter Web/App 本地數據篡改 (Client-Side State Tampering)
*   **觸發特徵**: Flutter App 在內存或本地 SQLite 中存儲了 `user_diamonds` 變量，並且在解鎖私密影片或進入 VIP 直播間時，僅在本地判斷 `if (user_diamonds >= video_cost)`，而沒有向服務器發起二次校驗。
*   **攻擊路徑**: 攻擊者使用 Android 逆向工具（如 Frida 或 GameGuardian）直接修改內存中的 `user_diamonds` 值。App 檢測到本地餘額足夠，直接解鎖了付費影片並播放。
*   **防禦策略**: 任何付費內容的解鎖和播放，必須由服務端生成臨時授權 Token（如帶過期時間的播放 URL / DRM 密鑰）。App 端僅負責攜帶 Token 向流媒體服務器請求，嚴禁由本地邏輯決定解鎖狀態。

### PAT-FE-102: React 虛擬 DOM 渲染與 XSS (XSS via Live Chat)
*   **觸發特徵**: 直播間彈幕（Live Chat）在 React 中渲染時，使用了 `dangerouslySetInnerHTML`，或者在 Flutter Web 中直接將彈幕內容作為 HTML 解析。
*   **攻擊路徑**: 攻擊者在彈幕中發送 `<img src=x onerror=alert(document.cookie)>`。當主播或其他用戶看到這條彈幕時，瀏覽器執行了惡意 JS 代碼，導致 **Session Token 被竊取**。
*   **防禦策略**: 嚴禁在渲染用戶輸入內容時使用 `dangerouslySetInnerHTML`。React 默認的 `{message}` 綁定會自動進行 HTML 實體轉義，是安全的。若必須渲染富文本，必須使用 `dompurify` 等庫進行嚴格的消毒 (Sanitize)。

---

## 3. SWAG QA 前端與 App 自動化測試與 Bug 偵測劇本

### Playwright 前端輸入框負數與邊界測試
```javascript
const { test, expect } = require('@playwright/test');

test('驗證投注輸入框不接受負數、小數與科學計數法', async ({ page }) => {
  await page.goto('https://swag.live/games/dragon-tiger');
  
  const betInput = page.locator('input[placeholder="請輸入鑽石數"]');
  await betInput.waitFor({ state: 'visible' });

  // 1. 嘗試輸入負數
  await betInput.fill('-100');
  let value = await betInput.inputValue();
  expect(value).not.toBe('-100'); // 輸入框應自動過濾負號，變為 '100' 或空

  // 2. 嘗試輸入科學計數法 'e'
  await betInput.fill('1e5');
  value = await betInput.inputValue();
  expect(value).not.toBe('1e5'); // 應變為 '15' 或過濾掉 'e'

  // 3. 嘗試輸入小數
  await betInput.fill('50.5');
  value = await betInput.inputValue();
  expect(value).not.toBe('50.5'); // 應變為 '505' 或過濾掉小數點
});
```

### Appium 移動端 SSL Pinning 繞過與安全性校驗
```python
# Appium / Python 安全性測試範例
import unittest
from appium import webdriver
from appium.options.android import UiAutomator2Options

class SwagAppSecurityTest(unittest.TestCase):
    def setUp(self):
        options = UiAutomator2Options()
        options.platform_name = 'Android'
        options.device_name = 'Emulator'
        options.app = '/path/to/swag-live-production.apk'
        # 設置代理為 Charles/Fiddler 的監聽端口
        options.set_capability('proxy', {
            'proxyType': 'manual',
            'httpProxy': '192.168.1.100:8888',
            'sslProxy': '192.168.1.100:8888'
        })
        self.driver = webdriver.Remote('http://localhost:4723', options=options)

    def test_ssl_pinning_active(self):
        # 1. 啟動 App 並嘗試登錄
        # 如果 SSL Pinning 正常運作，App 檢測到代理服務器的自簽名證書，應該會拒絕建立連接
        # 此時登錄操作應該失敗，且不應該有任何敏感數據（如密碼）流向代理服務器
        
        # 尋找登錄按鈕並點擊
        login_btn = self.driver.find_element(by='id', value='btn_login')
        login_btn.click()
        
        # 驗證是否彈出「網絡連接異常 / 證書無效」的提示
        error_toast = self.driver.find_element(by='xpath', value="//*[contains(@text, '連線失敗') or contains(@text, 'SSL')]")
        self.assertIsNotNone(error_toast)

    def tearDown(self):
        self.driver.quit()
```
