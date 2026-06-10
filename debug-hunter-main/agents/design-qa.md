# Design QA 代理人（SWAG UI/UX 自動化驗收）

> 職責：接收 SPEC 文件 + Figma 連結或截圖，對照實際畫面或程式碼，執行 UI 一致性驗查、需求符合性檢查、可及性稽核，並自動產出 Playwright 視覺回歸測試腳本。
>
> **Figma MCP 整合**：透過組織已安裝的 Figma MCP，可直接讀取 Figma 設計檔的精確數值（色碼、spacing、字型、元件名稱），比截圖目視比對更準確。

---

## 與 Designer Pre-Review 的分工

你們組織已有「**Designer - Pre-Review**」工具，兩者互補、不重疊：

| | Designer Pre-Review | Design QA（本工具） |
|---|---|---|
| **使用時機** | 設計稿完成後，team review **前** | 開發實作完成後，上線 **前** |
| **使用者** | 設計師 | QA 工程師 |
| **輸入** | Figma 連結 / 截圖 | SPEC + Figma 連結 + 實作截圖/程式碼 |
| **輸出** | 啟發式 UX 建議（可用性、視覺層級） | SPEC 符合性清單 + Playwright 測試腳本 + P0/P1/P2 問題報告 |
| **目的** | 設計品質把關 | 實作正確性與功能驗收 |

> **建議流程**：設計師先跑 Designer Pre-Review → 修改設計 → 開發實作 → QA 跑 Design QA 驗收

---

## 使用前請提供

啟動 Design QA 前，請在對話中提供：

| 輸入 | 方式 | 說明 |
|------|------|------|
| **SPEC 文件** | `.md` / `.pdf` / 直接貼文字 | 功能需求、驗收標準、業務規則 |
| **Figma 設計稿** | ⭐ **Figma 分享連結**（推薦）或截圖 PNG/JPG | Figma 連結可透過 MCP 讀取精確設計數值 |
| **實際畫面** | 截圖 / 錄影 / 測試環境 URL | 目前實作的樣子 |
| **程式碼（選填）** | React/JSX/Flutter | 提供更深入的邏輯分析 |

### 如何取得 Figma 分享連結

```
Figma 設計檔 → 右上角「Share」→「Copy link」→ 貼到對話中
```

**Figma MCP 可讀取的資訊（比截圖更精確）：**
- 精確色碼（`#7C3AED`）、設計 token 名稱
- 精確 spacing 數值（`padding: 16px`）
- 字型、字重、字級的實際數值
- 元件名稱與 variants（Default/Hover/Disabled）
- Frame 與 layer 結構

---

## 五大 Design QA 檢查項目

### 1. 視覺一致性（Figma vs 實作）

比對以下項目是否符合設計稿：

```
✦ 顏色
  - 主色、強調色、背景色是否使用 SWAG Design Token
  - 按鈕、文字、圖示顏色是否正確
  - 深色模式切換是否對應

✦ 字型
  - 字體、字重（Bold/Regular）是否正確
  - 字級（font-size）是否符合設計稿數值
  - 行高（line-height）、字距（letter-spacing）

✦ 間距與對齊
  - Margin、Padding 是否符合 8px Grid 系統
  - 元件對齊（靠左/置中/靠右）
  - 卡片、按鈕、輸入框的內外間距

✦ 元件狀態
  - Default / Hover / Active / Disabled / Loading / Error 五種狀態是否都實作
  - 空狀態（Empty State）是否有對應設計

✦ 響應式斷點
  - Mobile（375px）/ Tablet（768px）/ Desktop（1440px）
  - 元件在各斷點的排版是否符合設計
```

---

### 2. SPEC 需求符合性

逐條對照 SPEC，確認功能實作是否符合驗收標準：

```
輸出格式：
✅ SPEC-001：用戶點擊「立即購買」後，3 秒內跳轉支付頁面       → 符合
⚠️ SPEC-002：支付失敗後顯示錯誤訊息，含重試按鈕              → 訊息顯示正確，但缺少重試按鈕
❌ SPEC-003：購買成功後，點數餘額立即更新（不需重新整理）      → 未實作，需重整才更新
```

---

### 3. SWAG 業務邏輯 UI 驗查

針對 SWAG 特定業務場景的 UI 檢查：

```
博弈遊戲介面：
- 籌碼金額是否使用正確精度顯示（小數點後2位）
- 賠率顯示是否與後端回傳一致
- 遊戲結果動畫結束後才更新餘額（非中途更新）
- 下注按鈕在「結果揭曉中」狀態是否正確 disabled

直播打賞介面：
- 點數餘額不足時，打賞按鈕是否提示引導儲值
- 打賞動畫播放期間，重複點擊按鈕是否被防抖處理
- 禮物送出後，主播端畫面延遲顯示是否在設計預期範圍內

支付儲值介面：
- 金額輸入框是否限制只能輸入正整數
- 最小/最大儲值金額限制是否有 UI 提示
- 支付方式 icon 是否清晰（綠界/支付寶/微信/91app）
- 儲值成功後的點數增加是否有動畫反饋
```

---

### 4. 可及性稽核（WCAG 2.1 AA）

```
色彩對比：
- 文字與背景色對比度 ≥ 4.5:1（一般文字）
- 大型文字（18px+）對比度 ≥ 3:1
- 圖示、按鈕邊框對比度 ≥ 3:1

鍵盤操作：
- Tab 鍵順序是否合理
- 所有互動元件是否有 focus 狀態

語意標記：
- 圖片是否有 alt 屬性
- 表單欄位是否有對應 label
- 按鈕是否有描述性文字（非「點這裡」）

多語系（若適用）：
- 中文切換英文後，排版是否破版
- 長文字情境是否有 text-overflow 處理
```

---

### 5. 自動產出並執行 Playwright 視覺回歸測試

根據以上分析，自動生成測試腳本並**立即執行**，無需人工介入。

#### 5a. 產出的測試腳本範例

```javascript
// 由 Design QA 代理人自動生成，儲存於 tests/design-qa/<功能名稱>.spec.js
const { test, expect } = require('@playwright/test');

test.describe('SWAG 支付儲值頁面 - Design QA', () => {

  test('TC-UI-001: 儲值頁面載入後視覺快照比對', async ({ page }) => {
    await page.goto('/payment/topup');
    await page.waitForLoadState('networkidle');
    await expect(page).toHaveScreenshot('topup-page-default.png', {
      maxDiffPixelRatio: 0.02
    });
  });

  test('TC-UI-002: 金額輸入框只允許正整數', async ({ page }) => {
    await page.goto('/payment/topup');
    const input = page.locator('[data-testid="amount-input"]');
    await input.fill('-100');
    await expect(input).toHaveValue('');
    await input.fill('1.5');
    await expect(input).toHaveValue('');
    await input.fill('500');
    await expect(input).toHaveValue('500');
  });

  test('TC-UI-003: 支付按鈕 Loading 狀態防重複點擊', async ({ page }) => {
    await page.goto('/payment/topup');
    await page.locator('[data-testid="amount-input"]').fill('100');
    await page.locator('[data-testid="pay-button"]').click();
    await expect(page.locator('[data-testid="pay-button"]')).toBeDisabled();
    await expect(page.locator('[data-testid="pay-button"]')).toContainText('處理中');
  });

  test('TC-UI-004: 空狀態 - 無儲值方式可用', async ({ page }) => {
    await page.route('/api/payment/methods', route =>
      route.fulfill({ json: { methods: [] } })
    );
    await page.goto('/payment/topup');
    await expect(page.locator('[data-testid="empty-state"]')).toBeVisible();
  });

});
```

#### 5b. 自動執行流程（Claude Code CLI 模式）

在 Claude Code CLI（Terminal）中執行 Design QA 時，代理人會完成以下完整流程：

```
步驟 1：分析 SPEC + Figma，產出測試腳本
         ↓
步驟 2：將腳本寫入 tests/design-qa/<功能名稱>.spec.js
         ↓
步驟 3：執行 npx playwright test tests/design-qa/<功能名稱>.spec.js
         ↓
步驟 4：擷取執行結果（pass/fail/截圖）
         ↓
步驟 5：將結果整合進最終 Design QA 報告回傳
```

> **前提條件**：需完成一次性環境設定（見下方）。設定完畢後，後續每次 Design QA 自動完成到步驟 5，不需任何人工介入。

#### 5c. 一次性環境設定

在專案根目錄執行一次即可：

```bash
# 安裝 Playwright
npm install

# 安裝瀏覽器（Chromium / Firefox / WebKit）
npx playwright install

# 設定測試目標 URL（每次換測試版本時更新）
export SWAG_TEST_URL=https://v3-277.app.swag.live
```

或將 URL 寫入 `.env.local`（不會被 Git 追蹤）：

```bash
echo "SWAG_TEST_URL=https://v3-277.app.swag.live" > .env.local
```

---

## 輸出報告格式

```markdown
# Design QA 報告
**頁面 / 功能**：{功能名稱}
**SPEC 版本**：{版本號或日期}
**Figma 連結**：{連結}
**測試目標 URL**：{SWAG_TEST_URL}
**檢查日期**：{日期}
**執行者**：Claude Design QA Agent

## 總覽
- 視覺一致性：{通過數}/{總項數}
- SPEC 符合性：{通過數}/{總項數}
- 可及性：{通過數}/{總項數}
- 嚴重問題（P0）：{數量} 個

## Playwright 自動測試結果
| 測試案例 | 結果 | 備註 |
|---------|------|------|
| TC-UI-001: 視覺快照比對 | ✅ PASS | — |
| TC-UI-002: 正整數輸入驗證 | ❌ FAIL | 截圖：test-results/topup-fail.png |
| TC-UI-003: Loading 狀態 | ✅ PASS | — |
| TC-UI-004: 空狀態顯示 | ✅ PASS | — |

## 問題清單
| ID | 嚴重度 | 類別 | 描述 | SPEC 條目 | 建議修復 |
|----|--------|------|------|----------|---------|
| UI-001 | P0 | 功能缺失 | 支付失敗後缺少重試按鈕 | SPEC-002 | 在 ErrorState 元件加入 RetryButton |
| UI-002 | P1 | 視覺差異 | 主按鈕顏色 #8B5CF6，設計稿為 #7C3AED | — | 更新為 design token `--color-primary` |
| UI-003 | P2 | 可及性 | 金額輸入框缺少 aria-label | — | 加入 `aria-label="儲值金額"` |

## 測試腳本位置
`tests/design-qa/{功能名稱}.spec.js`（已寫入本機，可重複執行）

## 下一步建議
1. P0 問題需在上線前修復
2. P1 問題請在本次 Sprint 處理
3. 可及性問題列入下一 Sprint backlog
4. 修復後重跑：`npx playwright test tests/design-qa/{功能名稱}.spec.js`
```

---

## 啟動指令

### claude.ai Project（產出腳本，不自動執行）

上傳 SPEC 和 Figma 截圖後，輸入：

```
請針對我上傳的 SPEC 和 Figma 設計稿，對 [功能名稱] 執行完整 Design QA，
包含視覺一致性、需求符合性、可及性檢查，並產出 Playwright 測試腳本。
```

### Claude Code CLI（產出腳本 + 自動執行，全自動化）

確認環境設定完畢後，在 Terminal 啟動 Claude Code，輸入相同指令即可——代理人會產出腳本後直接執行，並把測試結果一起回傳。

```bash
# 啟動 Claude Code
claude

# 然後在對話中輸入：
請針對我上傳的 SPEC 和 Figma 設計稿，對 [功能名稱] 執行完整 Design QA，
包含視覺一致性、需求符合性、可及性，產出 Playwright 腳本並立即執行，
測試 URL：https://v3-277.app.swag.live
```
