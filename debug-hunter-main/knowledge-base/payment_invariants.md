# SWAG 金流與付費平台不變量與防禦指南 (Payment Invariants & Defenses)

> **檔案識別碼**: payment-invariants
> **適用範疇**: 綠界 (ECPay)、91app、支付寶 (Alipay)、微信支付 (WeChat Pay)、信用卡與代幣 (Diamond) 購買系統。
> **技術棧**: Python, Node.js (Express/NestJS), React, JS, RobotFramework, Playwright

---

## 1. 金流核心不變量 (Payment Invariants)

在 SWAG 的金流付費體系中，無論經過哪一個第三方支付平台，以下金融不變量必須**恆成立**。任何違反不變量的行為均視為 **P0 級致命資損 Bug**。

| 不變量 ID | 名稱 | 數學/邏輯定義 | 驗證機制 (Assert/Check) |
| :--- | :--- | :--- | :--- |
| **INV-PAY-01** | **充值金額守恆** | `用戶實付金額 * 匯率 (或代幣比例) == 用戶帳戶新增鑽石數 (Diamond)` | 嚴禁在前端計算兌換比例，必須在後端對比第三方支付回調 (Callback) 的 `trade_amt`。 |
| **INV-PAY-02** | **狀態機單向流轉** | `PaymentStatus: PENDING -> SUCCESS` 或 `PENDING -> FAILED` | 嚴禁逆向流轉（如 `SUCCESS -> PENDING`）或從終態變更（`SUCCESS -> FAILED`）。 |
| **INV-PAY-03** | **請求與回調冪等性** | `Callback(MerchantTradeNo) + N_times == 1_Processing_Effect` | 相同交易序號的多次回調通知，系統僅能處理一次加分/扣款，其餘必須返回成功。 |
| **INV-PAY-04** | **金額正值防禦** | `Request.Amount > 0` 且 `Response.TradeAmt > 0` | 嚴禁傳入負數或零，杜絕退款或溢領漏洞。 |
| **INV-PAY-05** | **簽章防篡改** | `ComputeSignature(Payload, Salt) == Request.Signature` | 每次支付請求與回調，必須使用對應平台的雜湊算法（如 SHA256）及金鑰校驗。 |

---

## 2. 常見金流支付 Bug 模式與攻擊路徑

### PAT-PAY-101: 支付回調偽造與繞過 (Callback Spoofing)
*   **觸發特徵**: 後端支付回調端點（如 `/api/v1/payment/ecpay/callback`）未驗證簽章（Signature/CheckMacValue），或直接信任客戶端傳入的 `status=success` 參數。
*   **攻擊路徑**: 攻擊者使用 Postman 直接向 SWAG 回調 API 發送構造好的 JSON/Form 數據，假裝綠界或微信支付已付款成功，從而實現**無成本買分/刷鑽石**。
*   **防禦策略**:
    ```python
    # Python 防禦範例：嚴格驗證簽章與實付金額
    def ecpay_callback_handler(request):
        payload = request.form.to_dict()
        received_mac = payload.pop('CheckMacValue', None)
        
        # 1. 驗證簽章
        calculated_mac = generate_ecpay_signature(payload, ECPAY_HASH_KEY, ECPAY_HASH_IV)
        if received_mac != calculated_mac:
            raise SecurityException("Invalid CheckMacValue! Potential attack detected.")
            
        # 2. 驗證訂單存在性與金額
        order = Order.objects.get(id=payload['MerchantTradeNo'])
        if order.status != OrderStatus.PENDING:
            return "1|OK"  # 冪等處理，已成功的訂單直接返回
            
        # 3. 驗證第三方實付金額與系統訂單金額是否完全一致
        third_party_amount = int(payload['TradeAmt'])
        if order.amount_minor_units != third_party_amount * 100: # 假設 DB 存分，ECPay 傳元
            raise SecurityException("Amount mismatch! Potential parameters tampering.")
    ```

### PAT-PAY-102: 金額參數篡改 (Parameter Tampering)
*   **觸發特徵**: 在調起第三方支付（如支付寶、微信、綠界）時，支付金額由前端（React/JSX）直接計算並作為參數傳給後端或第三方，後端未進行二次校驗。
*   **攻擊路徑**: 攻擊者在網頁端（React/JS）攔截請求，將 `amount=1000` 改為 `amount=1`。隨後跳轉到支付寶付款 1 元，但後端在回調時直接根據支付寶成功的 `amount=1` 去給用戶充值了 1000 元價值的鑽石。
*   **防禦策略**: 支付起點必須由後端控制。前端僅傳遞 `product_id`，後端查詢數據庫獲取真實價格，生成訂單後，直接由後端向第三方支付平台下單並獲取跳轉 URL。

### PAT-PAY-103: 微信/支付寶回調的「0 元購」 (Null-Amount Callback)
*   **觸發特徵**: 部分支付平台回調中包含退款或部分退款字段，或者狀態碼解析不嚴格（如將微信的 `REFUND` 誤判為 `SUCCESS`）。
*   **攻擊路徑**: 攻擊者發起付款後立即申請退款。微信發送退款回調，SWAG 後端因為僅檢查了 `return_code == SUCCESS`，卻未校驗 `result_code` 或交易類型，導致退款成功的同時，系統又給用戶加了一次鑽石。
*   **防禦策略**: 嚴格對照微信/支付寶官方 API 文檔，只有在 `trade_status == TRADE_SUCCESS`（支付寶）或 `result_code == SUCCESS` 且無退款標記（微信）時才執行動帳。

---

## 3. SWAG QA 金流自動化測試與 Bug 偵測劇本

### RobotFramework 金流接口測試劇本
```robot
*** Settings ***
Library    RequestsLibrary
Library    Collections

*** Variables ***
${BASE_URL}          https://api.swag.live/api/v1
${BYPASS_PAY_URL}    /payment/ecpay/callback
${VALID_ORDER_ID}    SWAG202606050001

*** Test Cases ***
Verify Callback Signature Validation
    [Documentation]    測試當回調簽章不正確時，系統必須拒絕請求，防範偽造回調。
    Create Session    swag_api    ${BASE_URL}
    ${data}=    Create Dictionary    MerchantTradeNo=${VALID_ORDER_ID}    TradeAmt=1000    RtnCode=1    CheckMacValue=INVALID_SIGNATURE_FOR_TEST
    ${headers}=    Create Dictionary    Content-Type=application/x-www-form-urlencoded
    ${response}=    POST On Session    swag_api    ${BYPASS_PAY_URL}    data=${data}    headers=${headers}    expected_status=400
    Should Contain    ${response.text}    Invalid CheckMacValue

Verify Amount Tampering Prevention
    [Documentation]    測試回調金額與系統訂單不一致時，系統必須拒絕，防範金額篡改。
    Create Session    swag_api    ${BASE_URL}
    # 假設這筆訂單在系統中是 1000 元，我們故意傳送 1 元的回調
    ${correct_sig}=    Calculate Signature For Test    MerchantTradeNo=${VALID_ORDER_ID}    TradeAmt=1    RtnCode=1
    ${data}=    Create Dictionary    MerchantTradeNo=${VALID_ORDER_ID}    TradeAmt=1    RtnCode=1    CheckMacValue=${correct_sig}
    ${headers}=    Create Dictionary    Content-Type=application/x-www-form-urlencoded
    ${response}=    POST On Session    swag_api    ${BYPASS_PAY_URL}    data=${data}    headers=${headers}    expected_status=400
    Should Contain    ${response.text}    Amount mismatch
```

### Playwright 端到端支付流程阻斷與篡改測試
```javascript
// Playwright / JS 測試範例
const { test, expect } = require('@playwright/test');

test('攔截並驗證支付請求參數防篡改', async ({ page }) => {
  await page.goto('https://swag.live/diamonds/buy');
  
  // 1. 攔截向後端發起的創建訂單請求
  await page.route('**/api/v1/payment/create-order', async (route) => {
    const request = route.request();
    const postData = JSON.parse(request.postData() || '{}');
    
    // 驗證前端發出的請求中，是否「只傳遞了 productId」而沒有「直接傳遞金額」
    expect(postData.amount).toBeUndefined(); // 應由後端決定金額，不應由前端傳遞
    expect(postData.productId).toBeDefined();
    
    await route.continue();
  });

  // 點擊購買 1000 鑽石的按鈕
  await page.click('button[data-product-id="diamond_1000"]');
});
```
