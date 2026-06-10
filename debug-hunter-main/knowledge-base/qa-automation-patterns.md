# QA 自動化測試最佳實踐與 Bug 模式知識庫
# SWAG 成人直播平台 QA 部門專用

version: 1.0.0
domain: qa-automation
platform: swag.live
language: zh-TW

---

## 一、SWAG QA 技術堆疊概覽

### 1.1 測試框架選用原則

| 框架 | 適用場景 | 主要用途 |
|------|---------|---------|
| Robot Framework | API 整合測試、E2E 回歸測試 | 讀取性強，非工程師也可撰寫與維護 |
| Playwright (Python) | Web E2E 測試（swag.live 桌面/手機版） | 現代瀏覽器自動化，支援 async/await |
| Appium | iOS/Android 原生 App 測試 | 跨平台行動裝置測試 |
| pytest | Python 單元測試、整合測試 | 快速回饋，適合開發者撰寫 |
| Flutter Integration Test | Flutter Web 測試 | SWAG Flutter Web 版本的 E2E 測試 |

### 1.2 測試金字塔（SWAG 版本）

```
            ╱ E2E ╲
           ╱ Robot  ╲
          ╱ Playwright╲
         ╱─────────────╲
        ╱  整合測試       ╲
       ╱  pytest + API    ╲
      ╱────────────────────╲
     ╱      單元測試          ╲
    ╱    pytest unit tests     ╲
   ╱──────────────────────────╲
```

- **單元測試**：最多、最快，開發者在 PR 前執行
- **整合測試**：API 層測試，驗證服務間互動
- **E2E 測試**：最少，覆蓋關鍵業務流程，CI 每次部署後執行

---

## 二、Robot Framework 最佳實踐與常見 Bug

### PAT-RF-001：測試資料污染（Test Data Contamination）

**類別**：測試隔離  
**嚴重程度**：高（會導致不穩定的測試結果，難以偵錯）  
**觸發場景**：多個 Test Suite 共用同一組測試帳號、同一環境同時跑多個測試  

**問題描述**  
測試直接操作共用資料庫的持久化帳號，多個測試套件之間的資料互相干擾。例如一個測試消耗了點數後，另一個期望點數足夠的測試就會失敗。

**錯誤範例**

```robot
*** Settings ***
# 危險：無 Suite Teardown，測試結束後不清理資料
# 危險：使用共用的固定測試帳號

*** Variables ***
${TEST_USER}    test_user_001    # 所有 Suite 共用同一帳號

*** Test Cases ***
TC-001 購買點數測試
    Buy Points    ${TEST_USER}    100
    # 測試結束後沒有清理，下次測試時餘額不確定

TC-002 打賞測試
    # 依賴上一個測試留下的點數狀態 —— 不可靠！
    Send Gift    ${TEST_USER}    streamer_001    50
```

**正確範例**

```robot
*** Settings ***
Library     RequestsLibrary
Resource    ../resources/user-factory.resource
Suite Setup     Create Isolated Test User
Suite Teardown  Delete Test User And Cleanup

*** Variables ***
${TEST_USER_ID}     ${NONE}    # 每次 Suite 動態建立

*** Keywords ***
Create Isolated Test User
    [Documentation]    建立測試專用的隔離帳號，附帶足夠的測試點數
    ${user}=    Create Test User Via API    prefix=qa_rf_
    Set Suite Variable    ${TEST_USER_ID}    ${user.id}
    # 設定測試需要的初始點數
    Set User Points    ${TEST_USER_ID}    10000

Delete Test User And Cleanup
    [Documentation]    測試結束後刪除測試帳號及所有相關資料
    Run Keyword If    '${TEST_USER_ID}' != 'None'
    ...    Delete Test User    ${TEST_USER_ID}
    # 確保清理相關的 Redis 快取
    Flush User Cache    ${TEST_USER_ID}

*** Test Cases ***
TC-001 購買點數測試
    [Setup]     Set User Points    ${TEST_USER_ID}    0    # 明確設定初始狀態
    Buy Points    ${TEST_USER_ID}    100
    ${points}=    Get User Points    ${TEST_USER_ID}
    Should Be Equal As Numbers    ${points}    100
    [Teardown]  Set User Points    ${TEST_USER_ID}    0    # 還原狀態
```

---

### PAT-RF-002：硬式寫死環境配置

**類別**：測試可維護性  
**嚴重程度**：中（導致測試在錯誤環境執行，可能造成正式環境資料污染）  
**觸發場景**：開發者複製測試程式碼時忘記修改 URL  

**問題描述**  
測試程式碼中硬式寫死環境 URL、帳號密碼、API Key，導致測試無法在不同環境（dev/staging/prod）中複用，且有誤操作正式環境的風險。

**錯誤範例**

```robot
*** Variables ***
${BASE_URL}     https://swag.live          # 危險：正式環境 URL
${ADMIN_TOKEN}  eyJhbGciOiJSUzI1NiJ9...   # 危險：正式環境 Token 寫死
${DB_HOST}      prod-db.internal            # 危險：正式 DB 位址

*** Test Cases ***
TC-PAYMENT-001 綠界支付測試
    # 這會對正式環境發出真實支付請求！
    POST    ${BASE_URL}/api/payments/ecpay    data=${payment_data}
```

**正確範例**

```robot
# robot.yaml（環境配置）
environments:
  staging:
    BASE_URL: https://staging.swag.live
    ECPay_MODE: sandbox
  production:
    BASE_URL: https://swag.live
    ECPay_MODE: live

# variables/staging.yaml
BASE_URL: https://staging.swag.live
API_VERSION: v2
ECPay_MERCHANT_ID: "%{ECPAY_STAGING_MERCHANT_ID}"    # 從環境變數讀取
ADMIN_TOKEN: "%{STAGING_ADMIN_TOKEN}"                  # 不寫入程式碼
```

```robot
*** Settings ***
# 從環境變數或設定檔讀取，不寫死
Variables    variables/%{TEST_ENV}.yaml

*** Variables ***
# 這裡的值來自 variables 檔案，不是硬式寫死
${BASE_URL}     ${NONE}    # 由 variables 檔案注入

*** Test Cases ***
TC-PAYMENT-001 綠界支付測試
    # 使用沙箱環境，不影響正式環境
    ${response}=    POST    ${BASE_URL}/api/payments/ecpay
    ...    json=${payment_data}
    Should Be Equal As Integers    ${response.status_code}    200
```

---

### PAT-RF-003：等待機制不穩定（Flaky Tests）

**類別**：測試穩定性  
**嚴重程度**：中（測試結果不可靠，CI 頻繁誤報）  
**觸發場景**：CI 伺服器負載高時、API 回應較慢時  

**問題描述**  
用固定的 `Sleep` 時間等待頁面載入或 API 回應，在不同環境下的執行速度不同，導致測試有時通過有時失敗（Flaky）。

**錯誤範例**

```robot
*** Test Cases ***
TC-LIVE-001 開始直播後出現在列表
    Click Button    開始直播
    Sleep    5s              # 危險：固定等待，在慢速環境可能不夠
    ${streams}=    Get Live Streams
    Should Contain    ${streams}    我的直播間
```

**正確範例**

```robot
*** Settings ***
Library    SeleniumLibrary
Library    RequestsLibrary

*** Test Cases ***
TC-LIVE-001 開始直播後出現在列表
    Click Button    開始直播
    # 等待特定條件滿足，而非固定時間
    Wait Until Element Is Visible    xpath://div[@data-testid='live-stream-card']    timeout=30s
    # 或等待 API 回傳預期結果
    Wait Until Keyword Succeeds    30s    2s    Verify Stream Appears In List

*** Keywords ***
Verify Stream Appears In List
    ${response}=    GET    ${BASE_URL}/api/streams/live
    ${streams}=     Set Variable    ${response.json()['data']}
    Should Be True    len(${streams}) > 0
    [Return]    ${streams}
```

---

### PAT-RF-004：敏感資料寫入 Robot Log

**類別**：資料安全 / 合規  
**嚴重程度**：高（支付資料、密碼洩露在測試 Log 中，違反 PCI DSS）  
**觸發場景**：支付整合測試、登入測試  

**問題描述**  
Robot Framework 預設會記錄所有變數和請求/回應內容，若未特別處理，信用卡號、密碼、JWT Token 等敏感資料會明文出現在 HTML 報告中。

**錯誤範例**

```robot
*** Keywords ***
Verify Payment Processing
    ${payment_data}=    Create Dictionary
    ...    card_number=4111111111111111
    ...    cvv=123
    ...    amount=1000
    Log    ${payment_data}    # 危險：信用卡資料明文記錄
    ${response}=    POST    ${BASE_URL}/api/payments    json=${payment_data}
    Log    ${response.json()}    # 危險：可能包含交易詳情
```

**正確範例**

```robot
*** Settings ***
Library    RequestsLibrary

*** Keywords ***
Verify Payment Processing
    [Documentation]    支付測試，敏感資料不記錄於 Log
    ${payment_data}=    Create Dictionary
    ...    card_number=${TEST_CARD_NUMBER}    # 從環境變數讀取
    ...    cvv=${TEST_CARD_CVV}
    ...    amount=1000

    # 使用 console=no 且不記錄敏感欄位
    Log    執行支付請求，金額：${payment_data['amount']}    console=yes
    # 遮罩敏感資料
    ${masked_card}=    Mask Sensitive Data    ${payment_data['card_number']}
    Log    卡號（遮罩）：${masked_card}    console=yes

    ${response}=    POST    ${BASE_URL}/api/payments    json=${payment_data}
    # 只記錄非敏感的回應欄位
    Log    支付回應 status_code：${response.status_code}    console=yes
    Log    交易號：${response.json()['trade_no']}    console=yes
    # 不記錄完整回應（可能含敏感資料）

*** Keywords ***
Mask Sensitive Data
    [Arguments]    ${data}
    ${length}=    Get Length    ${data}
    ${masked}=    Evaluate    '*' * (${length} - 4) + '${data[-4:]}'
    [Return]    ${masked}
```

---

## 三、Playwright 最佳實踐與常見 Bug

### PAT-PW-001：Selector 耦合 DOM 結構

**類別**：測試可維護性  
**嚴重程度**：中（UI 改版後大量測試失敗）  
**觸發場景**：前端進行樣式重構、元件改版  

**問題描述**  
使用 CSS 類名或 XPath 路徑作為選擇器，這些選擇器與 UI 實作強度耦合，前端改版後大量測試失敗，需要逐一修改。

**錯誤範例**

```python
# 錯誤範例：依賴 CSS 類名和 DOM 結構
async def test_send_gift(page):
    await page.click('.gift-panel .btn.primary.large[data-gift="rose"]')
    await page.click('//div[@class="container"]//button[contains(@class, "confirm-btn")]')
    # 以上兩行在 UI 改版後可能全部失敗
```

**正確範例**

```python
# 正確範例：使用語意化選擇器和 data-testid
async def test_send_gift(page):
    # 使用 data-testid（由前端工程師維護，語意明確）
    await page.click('[data-testid="gift-rose-button"]')
    await page.click('[data-testid="gift-confirm-button"]')

    # 或使用 ARIA 角色（無障礙語意）
    await page.get_by_role('button', name='送出禮物').click()

    # 等待成功訊息
    await expect(page.get_by_test_id('gift-success-toast')).to_be_visible()
```

**前端配合規範（需與前端工程師協定）**

```jsx
// 前端元件加入 data-testid
function GiftPanel({ gifts }) {
  return (
    <div data-testid="gift-panel">
      {gifts.map(gift => (
        <button
          key={gift.id}
          data-testid={`gift-${gift.name}-button`}
          onClick={() => selectGift(gift)}
        >
          {gift.name}
        </button>
      ))}
      <button data-testid="gift-confirm-button" onClick={confirmGift}>
        確認送出
      </button>
    </div>
  );
}
```

---

### PAT-PW-002：多 Tab/彈窗處理缺失

**類別**：測試覆蓋率  
**嚴重程度**：高（支付流程測試失敗，主要業務路徑未被驗證）  
**觸發場景**：點擊「前往支付」後跳轉至綠界/支付寶頁面  

**問題描述**  
SWAG 的支付流程會開啟第三方支付頁面（新 Tab 或彈窗），Playwright 若未正確處理，測試會在跳轉後卡住無法繼續。

**錯誤範例**

```python
# 錯誤範例：未處理新 Tab
async def test_purchase_points(page):
    await page.click('[data-testid="buy-points-button"]')
    await page.click('[data-testid="ecpay-option"]')
    await page.click('[data-testid="proceed-to-payment"]')
    # 危險：此時頁面已跳轉到 ECPay，但 page 物件還是原來的
    await page.fill('#card-number', '4111111111111111')  # 找不到元素，測試失敗
```

**正確範例**

```python
# 正確範例：正確處理彈窗/新 Tab
async def test_purchase_points(page, context):
    await page.click('[data-testid="buy-points-button"]')
    await page.click('[data-testid="ecpay-option"]')

    # 方式一：等待新 Tab 開啟
    async with context.expect_page() as new_page_info:
        await page.click('[data-testid="proceed-to-payment"]')

    payment_page = await new_page_info.value
    await payment_page.wait_for_load_state('networkidle')

    # 在新 Tab（支付頁面）中操作
    await payment_page.fill('#CardNo', '4311952222222222')  # ECPay 測試卡號
    await payment_page.fill('#CardExpireMonth', '12')
    await payment_page.fill('#CardExpireYear', '25')
    await payment_page.fill('#CardCVC', '222')
    await payment_page.click('#SubmitButton')

    # 等待回調完成，原頁面顯示成功
    await expect(page.get_by_test_id('payment-success-message')).to_be_visible(timeout=30000)

# 沙箱環境：Mock 支付，不真實跳轉第三方
async def test_purchase_points_with_mock(page):
    # 攔截支付 API，直接 Mock 成功回應
    await page.route('**/api/payments/ecpay**', lambda route: route.fulfill(
        status=200,
        content_type='application/json',
        body='{"success": true, "trade_no": "TEST_TRADE_001", "status": "paid"}'
    ))

    await page.click('[data-testid="buy-points-button"]')
    await page.click('[data-testid="ecpay-option"]')
    await page.click('[data-testid="proceed-to-payment"]')
    await expect(page.get_by_test_id('payment-success-message')).to_be_visible()
```

---

### PAT-PW-003：網路請求未 Mock（速度慢/不穩定）

**類別**：測試效率 / 穩定性  
**嚴重程度**：中（CI 執行時間過長，外部 API 不穩定導致誤報）  
**觸發場景**：支付 API 測試、第三方身分驗證  

**問題描述**  
E2E 測試每次都真實呼叫外部支付 API（綠界、支付寶、微信支付），導致測試速度慢，且外部服務不穩定時測試誤報。

**正確範例**

```python
# conftest.py：共用的 Mock 設定
import pytest
from playwright.async_api import Page, Route

@pytest.fixture
async def mock_ecpay(page: Page):
    """Mock 綠界支付 API，避免真實支付"""
    async def handle_ecpay(route: Route):
        url = route.request.url
        if '/AioCheckOut/' in url:
            # 模擬 ECPay 支付頁面（沙箱）
            await route.fulfill(
                status=200,
                content_type='text/html',
                body='<html><body><form id="payment-form">...</form></body></html>'
            )
        elif '/QueryTradeInfo/' in url:
            await route.fulfill(
                status=200,
                content_type='application/json',
                body='{"TradeStatus":"1","TradeAmt":"100","PaymentDate":"2026/06/05"}'
            )
        else:
            await route.continue_()

    await page.route('**/ecpay.com.tw/**', handle_ecpay)
    yield
    await page.unroute('**/ecpay.com.tw/**')

# 測試使用 Mock
async def test_purchase_100_points(page, mock_ecpay):
    await page.goto('/buy-points')
    await page.click('[data-testid="100-points-option"]')
    await page.click('[data-testid="buy-with-ecpay"]')
    # Mock 的 ECPay 立即回應，不需等待真實 API
    await expect(page.get_by_test_id('purchase-success')).to_be_visible(timeout=5000)
```

---

## 四、Appium 最佳實踐與常見 Bug

### PAT-APPIUM-001：iOS/Android 元素 ID 不一致

**類別**：跨平台相容性  
**嚴重程度**：中（iOS 和 Android 使用不同的元素識別策略）  

**問題描述**  
iOS 使用 `accessibility id`，Android 使用 `resource-id`，若測試程式碼未處理差異，只能在單一平台執行。

**正確範例**

```python
# utils/element_finder.py
from appium.webdriver.common.appiumby import AppiumBy
import os

PLATFORM = os.getenv('PLATFORM', 'android').lower()

def find_gift_button(driver, gift_name: str):
    """跨平台元素定位"""
    if PLATFORM == 'ios':
        return driver.find_element(AppiumBy.ACCESSIBILITY_ID, f'gift_{gift_name}')
    elif PLATFORM == 'android':
        return driver.find_element(
            AppiumBy.ANDROID_UIAUTOMATOR,
            f'new UiSelector().resourceId("live.swag.app:id/gift_{gift_name}")'
        )

# 建議：要求前端工程師同步設定 accessibility id
# Android: android:contentDescription="gift_rose"
# iOS: accessibilityIdentifier = "gift_rose"
```

---

### PAT-APPIUM-002：ScrollView 處理錯誤

**類別**：測試穩定性  
**嚴重程度**：中（無法找到滾動後才出現的元素）  

**問題描述**  
列表頁面（如禮物清單、主播列表）需要滾動才能看到所有元素，若測試未處理滾動，目標元素不在視窗中就無法點擊。

**正確範例**

```python
def scroll_to_gift(driver, gift_name: str, max_scrolls: int = 5):
    """滾動直到找到目標禮物"""
    for _ in range(max_scrolls):
        try:
            element = driver.find_element(
                AppiumBy.ACCESSIBILITY_ID, f'gift_{gift_name}'
            )
            if element.is_displayed():
                return element
        except Exception:
            pass

        # 向上滾動（從下往上）
        screen_size = driver.get_window_size()
        driver.swipe(
            start_x=screen_size['width'] // 2,
            start_y=int(screen_size['height'] * 0.8),
            end_x=screen_size['width'] // 2,
            end_y=int(screen_size['height'] * 0.3),
            duration=500
        )

    raise Exception(f"找不到禮物：{gift_name}（已滾動 {max_scrolls} 次）")
```

---

### PAT-APPIUM-003：網路狀態切換測試缺失

**類別**：測試覆蓋率  
**嚴重程度**：高（行動端用戶常遇到網路切換，打賞/訂閱中斷場景未測試）  

**問題描述**  
SWAG 行動 App 的核心場景（打賞、訂閱、支付）在網路切換瞬間可能產生重複請求或資料不一致，但這類場景未被自動化測試覆蓋。

**正確範例**

```python
import subprocess

def toggle_airplane_mode(driver, enable: bool):
    """切換飛航模式（需要有 root 或 ADB 權限）"""
    if PLATFORM == 'android':
        state = 'enable' if enable else 'disable'
        subprocess.run(['adb', 'shell', f'cmd connectivity airplane-mode {state}'])
    # iOS 需透過 Appium 的特定方法或系統設定

def test_gift_during_network_switch(driver):
    """測試打賞時網路切換的冪等性"""
    initial_points = get_user_points(driver)

    # 點擊送禮後立即切換飛航模式
    tap_gift_button(driver, 'rose')

    import time
    time.sleep(0.5)  # 讓請求發出但尚未回應
    toggle_airplane_mode(driver, enable=True)
    time.sleep(2)
    toggle_airplane_mode(driver, enable=False)
    time.sleep(3)  # 等待重連和重試

    final_points = get_user_points(driver)
    # 點數只應扣除一次
    assert initial_points - final_points <= ROSE_GIFT_COST
```

---

## 五、API 測試最佳實踐

### PAT-API-001：JWT Token 過期處理

**類別**：認證測試  
**嚴重程度**：高（Token 過期時 API 應回傳 401，而非 500 或其他非預期狀態）  

**正確範例**

```python
import pytest
import jwt
import time
from httpx import AsyncClient

@pytest.fixture
def expired_token():
    """建立已過期的 JWT Token 用於測試"""
    payload = {
        'user_id': 99999,
        'exp': int(time.time()) - 3600,  # 1 小時前過期
        'iat': int(time.time()) - 7200,
    }
    return jwt.encode(payload, 'test-secret', algorithm='HS256')

async def test_api_rejects_expired_token(client: AsyncClient, expired_token: str):
    response = await client.get(
        '/api/streams/live',
        headers={'Authorization': f'Bearer {expired_token}'}
    )
    assert response.status_code == 401
    assert response.json()['error'] == 'token_expired'
    # 驗證回應包含重新登入的提示
    assert 'login_url' in response.json()

async def test_token_refresh_flow(client: AsyncClient):
    """驗證 Token 更新流程"""
    # 取得快過期的 Token（剩下 30 秒）
    short_lived_token = create_token_expiring_in(seconds=30)

    response = await client.post(
        '/api/auth/refresh',
        headers={'Authorization': f'Bearer {short_lived_token}'}
    )
    assert response.status_code == 200
    new_token = response.json()['access_token']
    assert new_token != short_lived_token
```

---

### PAT-API-002：Rate Limit 邊界測試缺失

**類別**：API 健壯性  
**嚴重程度**：中（Rate Limit 配置錯誤可能導致正常用戶被鎖定或 DDoS 防護失效）  

**正確範例**

```python
import asyncio
import httpx

async def test_gift_api_rate_limit():
    """驗證打賞 API 的 Rate Limit 設定"""
    client = httpx.AsyncClient()
    headers = {'Authorization': f'Bearer {TEST_TOKEN}'}

    responses = []
    # 在 1 秒內發送 20 次打賞請求
    tasks = [
        client.post('/api/gifts', json={'gift_id': 1, 'amount': 1}, headers=headers)
        for _ in range(20)
    ]
    responses = await asyncio.gather(*tasks, return_exceptions=True)

    status_codes = [r.status_code for r in responses if not isinstance(r, Exception)]

    # 驗證 Rate Limit 正常觸發（應有 429 回應）
    assert 429 in status_codes, "Rate Limit 未觸發，可能存在安全風險"
    # 驗證合理請求仍被允許（前幾筆應成功）
    assert 200 in status_codes, "所有請求都被拒絕，Rate Limit 設定過嚴"

    # 驗證 429 回應包含 Retry-After 標頭
    rate_limited = [r for r in responses if r.status_code == 429]
    assert all('Retry-After' in r.headers for r in rate_limited)
```

---

### PAT-API-003：分頁邊界未測試

**類別**：API 健壯性  
**嚴重程度**：低（邊界情況未處理可能導致用戶端崩潰或資料重複載入）  

**正確範例**

```python
async def test_pagination_edge_cases(client: AsyncClient):
    """測試分頁 API 的邊界情況"""

    # 1. 第一頁
    resp = await client.get('/api/streams?page=1&limit=10')
    assert resp.status_code == 200
    data = resp.json()
    assert 'data' in data
    assert 'total' in data
    assert 'has_next' in data

    # 2. 超出總頁數
    resp = await client.get('/api/streams?page=99999&limit=10')
    assert resp.status_code == 200  # 不應報錯
    assert resp.json()['data'] == []  # 空陣列而非 null
    assert resp.json()['has_next'] == False

    # 3. limit=0（邊界）
    resp = await client.get('/api/streams?page=1&limit=0')
    assert resp.status_code == 422  # 參數驗證錯誤

    # 4. limit 超過最大值
    resp = await client.get('/api/streams?page=1&limit=10000')
    assert resp.status_code in [200, 422]
    if resp.status_code == 200:
        # 自動截斷至最大允許值
        assert len(resp.json()['data']) <= 100  # 假設最大 100

    # 5. 負數 page
    resp = await client.get('/api/streams?page=-1&limit=10')
    assert resp.status_code == 422
```

---

## 六、QA 自動化規則（RULE-QA 系列）

| 規則 ID | 規則描述 | 類別 | 強制程度 |
|--------|---------|------|---------|
| RULE-QA-001 | 每個 Test Suite 必須有 Suite Teardown 清理測試資料 | 測試隔離 | 強制 |
| RULE-QA-002 | 禁止在測試程式碼中硬式寫死正式環境 URL、帳號、密碼、Token | 安全性 | 強制 |
| RULE-QA-003 | 禁止使用 Sleep 等待，必須使用條件等待（Wait Until） | 測試穩定性 | 強制 |
| RULE-QA-004 | 涉及敏感資料（支付、密碼、Token）的 Log 必須遮罩 | 資料安全 | 強制 |
| RULE-QA-005 | Playwright 選擇器優先使用 data-testid，禁止使用 CSS 類名作為主要選擇器 | 可維護性 | 建議 |
| RULE-QA-006 | 對外部 API（支付、簡訊）的測試必須使用 Mock 或沙箱環境 | 測試隔離 | 強制 |
| RULE-QA-007 | 每個金流相關 API 測試必須包含對應的負向測試（餘額不足、無效 Token 等） | 測試完整性 | 建議 |
| RULE-QA-008 | E2E 測試套件執行時間超過 10 分鐘時，必須評估是否可平行化 | 效率 | 建議 |
| RULE-QA-009 | Flaky Test（三次執行中有一次失敗）必須在一週內修復或標記 @xfail | 品質維護 | 強制 |
| RULE-QA-010 | 所有測試帳號必須使用測試專用的 email 格式（如 qa+xxx@swag.live） | 帳號管理 | 強制 |

---

## 七、SWAG QA 測試環境管理

### 7.1 測試環境架構

```
┌─────────────────────────────────────────────────────┐
│                   CI/CD Pipeline                     │
│                                                      │
│  ┌──────────┐    ┌──────────┐    ┌──────────────┐   │
│  │  開發環境  │    │ Staging  │    │   正式環境    │   │
│  │   (dev)  │    │ (staging)│    │   (prod)     │   │
│  └────┬─────┘    └────┬─────┘    └──────────────┘   │
│       │               │                              │
│  pytest unit    Robot + Playwright                   │
│  pytest integ   E2E 回歸測試                          │
│  （每次 PR）     （每次部署後）                         │
└─────────────────────────────────────────────────────┘

測試環境說明：
- dev：本機或開發伺服器，使用 pytest 單元/整合測試
- staging：完整功能的預生產環境，使用所有自動化測試套件
- prod：正式環境，僅執行不影響資料的煙霧測試

支付環境對應：
- dev/staging → 綠界沙箱 / 支付寶沙箱 / 微信支付沙箱
- prod → 正式支付環境（謹慎測試）
```

### 7.2 測試資料產生器

```python
# tests/factories/user_factory.py
import uuid
import httpx

class SwagTestUserFactory:
    """SWAG 測試用戶工廠，快速建立隔離的測試帳號"""

    BASE_URL = os.getenv('TEST_API_BASE_URL')
    ADMIN_TOKEN = os.getenv('TEST_ADMIN_TOKEN')

    @classmethod
    async def create_user(
        cls,
        points: int = 10000,
        age_verified: bool = True,
        prefix: str = 'qa_'
    ) -> dict:
        """建立測試用戶，預設有足夠點數且已完成年齡驗證"""
        unique_id = uuid.uuid4().hex[:8]
        user_data = {
            'username': f'{prefix}{unique_id}',
            'email': f'qa+{unique_id}@swag-test.internal',
            'password': 'Test@12345',
            'age_verified': age_verified,
            'initial_points': points
        }

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f'{cls.BASE_URL}/admin/test-users',
                json=user_data,
                headers={'Authorization': f'Bearer {cls.ADMIN_TOKEN}'}
            )
            resp.raise_for_status()
            return resp.json()

    @classmethod
    async def delete_user(cls, user_id: int):
        """清理測試用戶及所有關聯資料"""
        async with httpx.AsyncClient() as client:
            await client.delete(
                f'{cls.BASE_URL}/admin/test-users/{user_id}',
                headers={'Authorization': f'Bearer {cls.ADMIN_TOKEN}'}
            )

    @classmethod
    async def create_expired_subscription(
        cls, user_id: int, streamer_id: int, expired_days_ago: int = 1
    ):
        """建立已過期的訂閱（用於測試到期後的行為）"""
        from datetime import datetime, timedelta, timezone
        expired_at = datetime.now(timezone.utc) - timedelta(days=expired_days_ago)

        async with httpx.AsyncClient() as client:
            resp = await client.post(
                f'{cls.BASE_URL}/admin/test-subscriptions',
                json={
                    'user_id': user_id,
                    'streamer_id': streamer_id,
                    'expires_at': expired_at.isoformat()
                },
                headers={'Authorization': f'Bearer {cls.ADMIN_TOKEN}'}
            )
            resp.raise_for_status()
```

### 7.3 CI/CD 整合建議（GitHub Actions）

```yaml
# .github/workflows/qa-automation.yml
name: QA Automation Tests

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]
  deployment_status:  # 部署完成後觸發

jobs:
  unit-tests:
    name: Python Unit Tests
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install -r requirements-test.txt
      - run: pytest tests/unit/ -v --cov=app --cov-report=xml
      - uses: codecov/codecov-action@v4

  integration-tests:
    name: API Integration Tests
    runs-on: ubuntu-latest
    needs: unit-tests
    services:
      postgres:
        image: postgres:15
        env:
          POSTGRES_PASSWORD: testpass
      redis:
        image: redis:7
    steps:
      - uses: actions/checkout@v4
      - run: pip install -r requirements-test.txt
      - run: pytest tests/integration/ -v
        env:
          TEST_DATABASE_URL: postgresql://postgres:testpass@localhost/testdb
          TEST_REDIS_URL: redis://localhost:6379

  e2e-tests:
    name: E2E Tests (Robot Framework + Playwright)
    runs-on: ubuntu-latest
    needs: integration-tests
    if: github.event_name == 'deployment_status' && github.event.deployment_status.state == 'success'
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - run: pip install robotframework playwright robotframework-browser
      - run: playwright install chromium
      - name: Run Robot Framework Tests
        run: |
          robot \
            --variable BASE_URL:${{ vars.STAGING_URL }} \
            --variable ECPay_MODE:sandbox \
            --outputdir results/ \
            tests/robot/
        env:
          STAGING_ADMIN_TOKEN: ${{ secrets.STAGING_ADMIN_TOKEN }}
          ECPAY_STAGING_MERCHANT_ID: ${{ secrets.ECPAY_STAGING_MERCHANT_ID }}
      - name: Upload Test Results
        if: always()
        uses: actions/upload-artifact@v4
        with:
          name: robot-results
          path: results/

  mobile-tests:
    name: Appium Mobile Tests
    runs-on: macos-latest    # iOS 測試需要 macOS
    needs: integration-tests
    if: github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - name: Run Android Tests
        run: |
          pytest tests/appium/ -v \
            --platform android \
            --device-name "emulator-5554"
        env:
          APPIUM_HOST: localhost
          APPIUM_PORT: 4723
```

---

*最後更新：2026-06-05*  
*適用框架版本：Robot Framework 6.x / Playwright 1.4x / Appium 2.x*
