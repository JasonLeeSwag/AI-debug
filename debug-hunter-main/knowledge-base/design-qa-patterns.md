# Design QA 模式庫（SWAG UI 驗查規則）

---

## PAT-UI-001：Figma 設計稿顏色未對齊 Design Token

**發現方式**：人工比對 / Playwright snapshot diff
**嚴重度**：P1

**症狀**：
```css
/* ❌ 硬編碼色碼，與 Figma 不一致 */
.btn-primary { background-color: #8B5CF6; }

/* ✅ 使用 Design Token */
.btn-primary { background-color: var(--color-primary); }
```

**SWAG 常見色票**：
| Token 名稱 | 用途 | 色碼 |
|-----------|------|------|
| `--color-primary` | 主要按鈕、重點連結 | `#7C3AED` |
| `--color-surface` | 卡片背景 | `#1A1A2E` |
| `--color-text-primary` | 主要文字 | `#F3F4F6` |
| `--color-danger` | 錯誤、警告 | `#EF4444` |
| `--color-success` | 成功狀態 | `#10B981` |

---

## PAT-UI-002：元件缺少必要的狀態實作

**發現方式**：手動測試各狀態 / Playwright 狀態測試
**嚴重度**：P1

**必須實作的五種狀態**：
```
Default → Hover → Active → Disabled → Loading
```

**SWAG 業務特定狀態**：
- **點數不足**：打賞按鈕 / 投注按鈕的特殊 disabled 狀態，需引導儲值
- **遊戲進行中**：下注按鈕 disabled，顯示「等待開獎」
- **支付處理中**：防止重複提交的 loading 狀態

**Playwright 狀態測試範例**：
```javascript
test('TC-STATE-001: 點數不足時投注按鈕狀態', async ({ page }) => {
  // Mock 用戶點數為 0
  await page.route('/api/user/balance', route =>
    route.fulfill({ json: { points: 0 } })
  );
  await page.goto('/game/dragon-tiger');
  const betBtn = page.locator('[data-testid="bet-button"]');
  await expect(betBtn).toBeDisabled();
  await expect(betBtn).toHaveAttribute('aria-label', /點數不足/);
  // 應引導到儲值頁
  await expect(page.locator('[data-testid="topup-cta"]')).toBeVisible();
});
```

---

## PAT-UI-003：表單輸入邊界未在 UI 層防守

**發現方式**：邊界值測試
**嚴重度**：P0（直接關聯業務損失）

**SWAG 業務特定輸入限制**：

| 場景 | 限制規則 | UI 提示文字 |
|------|---------|-----------|
| 儲值金額 | 正整數，最小 100，最大 50,000 | 「最低儲值 $100，最高 $50,000」 |
| 投注金額 | 正數，不得超過當前點數餘額 | 「投注金額不可超過剩餘點數」 |
| 打賞點數 | 正整數，不得為負 | — |
| 提領金額 | 最小 1,000 元，最大當日限額 | 「當日提領上限 $XXX」 |

**Playwright 邊界測試**：
```javascript
test('TC-INPUT-001: 儲值金額邊界驗證', async ({ page }) => {
  await page.goto('/payment/topup');
  const input = page.locator('[data-testid="amount-input"]');
  const submitBtn = page.locator('[data-testid="submit-btn"]');

  // 低於最小值
  await input.fill('50');
  await submitBtn.click();
  await expect(page.locator('[data-testid="error-msg"]')).toContainText('最低儲值 $100');

  // 超過最大值
  await input.fill('99999');
  await submitBtn.click();
  await expect(page.locator('[data-testid="error-msg"]')).toContainText('最高 $50,000');

  // 負數
  await input.fill('-100');
  await expect(input).toHaveValue('');
});
```

---

## PAT-UI-004：響應式斷點破版

**發現方式**：多裝置截圖比對
**嚴重度**：P1

**SWAG 需支援的斷點**：
```
Mobile:  375px（iPhone SE）、390px（iPhone 14）
Tablet:  768px（iPad）
Desktop: 1280px、1440px
```

**Playwright 多斷點測試**：
```javascript
const VIEWPORTS = [
  { name: 'mobile', width: 375, height: 812 },
  { name: 'tablet', width: 768, height: 1024 },
  { name: 'desktop', width: 1440, height: 900 },
];

for (const vp of VIEWPORTS) {
  test(`TC-RWD-001: 儲值頁面 ${vp.name} 斷點視覺`, async ({ page }) => {
    await page.setViewportSize({ width: vp.width, height: vp.height });
    await page.goto('/payment/topup');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveScreenshot(`topup-${vp.name}.png`);
  });
}
```

---

## PAT-UI-005：SPEC 需求遺漏實作

**發現方式**：逐條對照 SPEC 清單
**嚴重度**：依 SPEC 條目而定

**常見 SWAG SPEC 遺漏項目**：

| SPEC 條目類型 | 常遺漏的實作 |
|-------------|------------|
| 支付成功 | 缺少「點數立即更新」（需即時反映，不能等重整） |
| 支付失敗 | 缺少錯誤代碼說明 + 重試按鈕 |
| 遊戲結算 | 缺少「贏/輸」動畫，直接跳結果 |
| 打賞 | 缺少「送出中」過渡狀態 |
| 提領申請 | 缺少「審核中」狀態的 UI 呈現 |

**SPEC 符合性清單範本**：
```markdown
## SPEC 需求對照表

| # | SPEC 要求 | 實作狀態 | 備註 |
|---|----------|---------|------|
| 1 | 支付成功後 3 秒內跳轉 | ✅ | 實測約 1.5 秒 |
| 2 | 失敗顯示錯誤碼 | ⚠️ | 有訊息但無錯誤碼 |
| 3 | 點數即時更新 | ❌ | 需重整才更新 |
| 4 | 重試按鈕 | ❌ | 未實作 |
```

---

## PAT-UI-006：可及性（Accessibility）缺失

**發現方式**：axe-core / Playwright accessibility snapshot
**嚴重度**：P2

**高頻缺失項目**：
```jsx
{/* ❌ 缺少 alt */}
<img src="/icons/ecpay.png" />

{/* ✅ */}
<img src="/icons/ecpay.png" alt="綠界支付" />

{/* ❌ 按鈕無描述性文字 */}
<button><CloseIcon /></button>

{/* ✅ */}
<button aria-label="關閉對話框"><CloseIcon /></button>

{/* ❌ 表單欄位無 label 關聯 */}
<input type="text" placeholder="輸入金額" />

{/* ✅ */}
<label htmlFor="amount">儲值金額</label>
<input id="amount" type="text" />
```

**Playwright 可及性掃描**：
```javascript
const { checkA11y } = require('axe-playwright');

test('TC-A11Y-001: 儲值頁面可及性掃描', async ({ page }) => {
  await page.goto('/payment/topup');
  await checkA11y(page, null, {
    detailedReport: true,
    detailedReportOptions: { html: true },
  });
});
```

---

## PAT-UI-007：Flutter Web 特定 UI 問題

**發現方式**：Flutter Web 實機測試
**嚴重度**：P1

**Flutter Web 常見 Design QA 問題**：

| 問題 | 症狀 | 處理方式 |
|------|------|---------|
| 字體渲染差異 | Web 字體與 App 不一致 | 指定 `fontFamily` 使用 Web 字型 |
| 捲軸行為 | 滑鼠捲軸與觸控捲軸行為不同 | 使用 `ScrollBehavior` 統一處理 |
| 圖片模糊 | 高解析度螢幕（Retina）圖片模糊 | 使用 `@2x` 圖片或 SVG |
| 動畫卡頓 | 複雜動畫在低階裝置卡頓 | 降低 FPS 或改用 CSS 動畫 |
| 鍵盤遮擋輸入框 | 手機鍵盤彈出後，輸入框被遮住 | 使用 `resizeToAvoidBottomInset` |

---

## Design QA 標準流程

```
1. 收到 SPEC + Figma 截圖
        ↓
2. 逐條閱讀 SPEC，建立「需求清單」
        ↓
3. 對照 Figma，建立「視覺基準」
        ↓
4. 檢查實作（截圖 / 程式碼 / 線上環境）
        ↓
5. 產出問題清單（P0/P1/P2 分級）
        ↓
6. 自動生成 Playwright 測試腳本
        ↓
7. 開發修復後，重跑 Playwright 確認轉綠
```

---

## 嚴重度定義

| 等級 | 定義 | 範例 | 上線阻擋 |
|------|------|------|---------|
| **P0** | 功能不可用 / 造成業務損失 | 支付按鈕點不動、點數不更新 | 是 |
| **P1** | 視覺嚴重偏差 / 功能殘缺 | 顏色錯誤、缺少 loading 狀態 | 是 |
| **P2** | 小視覺偏差 / 可及性問題 | 間距差 4px、缺少 alt | 否（列 backlog） |
| **P3** | 建議優化 | 動畫可以更流暢 | 否 |
