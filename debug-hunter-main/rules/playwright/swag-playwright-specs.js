/**
 * SWAG QA Playwright 自動化安全測試與 Bug 偵測規範
 * 
 * 用途: 供 QA 部門整合進 E2E 自動化測試框架中，針對 swag.live 的前端頁面進行安全與邏輯防禦校驗。
 */

const { test, expect } = require('@playwright/test');

test.describe('SWAG 前端網頁安全防禦與邏輯校驗', () => {

  // 測試 1: 充值/投注輸入框邊界與負數防禦
  test('TC-FE-001: 投注輸入框必須具備嚴格的格式過濾與非負校驗', async ({ page }) => {
    // 進入龍虎鬥遊戲頁面
    await page.goto('https://swag.live/games/dragon-tiger');
    
    const betInput = page.locator('input[placeholder="請輸入鑽石數"]');
    await expect(betInput).toBeVisible();

    // 動作 A: 嘗試輸入負數
    await betInput.fill('-500');
    let value = await betInput.inputValue();
    // 斷言: 前端應自動攔截負號，使其不變為負數
    expect(value).not.toBe('-500');

    // 動作 B: 嘗試輸入科學計數法 'e' (很多瀏覽器 type="number" 會允許輸入 'e' 導致溢出)
    await betInput.fill('1e6');
    value = await betInput.inputValue();
    expect(value).not.toBe('1e6');

    // 動作 C: 嘗試輸入特殊字符與小數點
    await betInput.fill('100.5');
    value = await betInput.inputValue();
    expect(value).not.toBe('100.5');
  });

  // 測試 2: 攔截並校驗支付起點參數（防金額篡改）
  test('TC-FE-002: 創建訂單請求中嚴禁直接傳遞金額參數', async ({ page }) => {
    await page.goto('https://swag.live/diamonds/buy');

    // 攔截創建訂單的 API 請求
    await page.route('**/api/v1/payment/create-order', async (route) => {
      const request = route.request();
      const postData = JSON.parse(request.postData() || '{}');
      
      // 核心斷言: 前端發出的 Payload 中絕對不能包含 amount (金額) 或 diamonds (加分數) 字段
      // 金額必須由後端根據 productId 在 DB 中查詢，防範客戶端篡改
      expect(postData.amount).toBeUndefined();
      expect(postData.diamonds).toBeUndefined();
      expect(postData.productId).toBeDefined(); // 僅能傳遞產品 ID

      await route.continue();
    });

    // 點擊購買 1000 鑽石的按鈕
    const buyButton = page.locator('button[data-product-id="diamond_1000"]');
    await buyButton.click();
  });

  // 測試 3: 直播間彈幕 XSS 防禦校驗
  test('TC-FE-003: 直播間彈幕渲染必須自動轉義 HTML 標籤（防範 XSS）', async ({ page }) => {
    await page.goto('https://swag.live/live/test_room_01');

    const chatInput = page.locator('input[placeholder="跟主播聊點什麼..."]');
    await expect(chatInput).toBeVisible();

    // 發送包含惡意 XSS Payload 的彈幕
    const xssPayload = '<img src=x onerror="window.xss_triggered=true">';
    await chatInput.fill(xssPayload);
    await page.keyboard.press('Enter');

    // 稍等 1 秒讓彈幕渲染
    await page.waitForTimeout(1000);

    // 核心斷言: 瀏覽器中絕對不能觸發惡意 JS 執行的 window.xss_triggered 標記
    const xssTriggered = await page.evaluate(() => window.xss_triggered);
    expect(xssTriggered).toBeUndefined();
  });

});
