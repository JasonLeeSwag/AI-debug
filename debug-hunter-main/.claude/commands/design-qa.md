請對以下功能執行完整 Design QA：**$ARGUMENTS**

## 你的任務

1. 讀取 `agents/design-qa.md` 了解完整的 Design QA 流程與 5 大檢查項目
2. 讀取 `knowledge-base/design-qa-patterns.md` 了解 SWAG UI 常見問題模式

## 執行步驟

**Step 1：確認輸入**
- 請求用戶提供（若尚未提供）：SPEC 文件（.md / .pdf / 文字）+ Figma 連結或截圖 + 實際畫面截圖或測試 URL

**Step 2：執行 5 大 Design QA 檢查**
- 視覺一致性（Figma vs 實作）
- SPEC 需求符合性（逐條對照）
- SWAG 業務邏輯 UI 驗查（博弈/打賞/支付/買分）
- 可及性稽核（WCAG 2.1 AA）
- 響應式斷點（375px / 768px / 1440px）

**Step 3：產出 Playwright 測試腳本**
- 將測試寫入 `tests/design-qa/$ARGUMENTS.spec.js`（將空格替換為連字號）
- 腳本必須使用 `playwright.config.js` 中定義的 baseURL

**Step 4：自動執行測試**
- 執行 `npx playwright test tests/design-qa/$ARGUMENTS.spec.js`
- 若 Playwright 尚未安裝，先執行 `npm install && npx playwright install --with-deps chromium`

**Step 5：輸出最終報告**
依照 `agents/design-qa.md` 的報告格式，輸出：
- 問題清單（P0 / P1 / P2）
- Playwright 測試執行結果（pass/fail 統計）
- 測試腳本存放位置
- 下一步建議
