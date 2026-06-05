# SWAG QA Debug Hunter 演進摘要 (Evolution Summary)

## v2.0 → v3.0 (2026-06-05) — SWAG QA 全面重構版

### 核心變更

**業務場景全面升級**
- 從通用金融系統升級為 SWAG 台灣成人直播平台專屬
- 新增博弈遊戲（龍虎鬥、百家樂）完整不變量與攻擊模式
- 新增直播打賞競態、付費解鎖繞過等直播平台特有威脅
- 新增第三方金流（綠界 ECPay、91app、支付寶、微信支付）回調防禦
- 新增 B2B API 買分後台 IDOR 越權與重放攻擊防禦

**技術棧全面替換**
- 移除所有 Java / Spring Boot 相關代碼、規則與示例
- 新增 Python 後端防禦模式（Django ORM 悲觀鎖、Flask 回調驗證）
- 新增 React/JSX 前端安全審查規則（防金額篡改、防 XSS）
- 新增 JavaScript/TypeScript WebSocket 遊戲服務器安全模式
- 新增 RobotFramework 金流接口自動化測試劇本
- 新增 Playwright E2E 前端防禦自動化測試基線
- 新增 Appium 移動端 SSL Pinning 安全校驗
- 新增 Flutter Web/App 本地狀態篡改防禦

**知識庫重構**
- `knowledge-base/payment_invariants.md` — 金流與支付防禦知識庫（全新）
- `knowledge-base/gaming_invariants.md` — 博弈遊戲不變量（全新）
- `knowledge-base/streaming_invariants.md` — 直播與後台知識庫（全新）
- `knowledge-base/frontend_app_invariants.md` — 前端與 App 防禦（全新）

**Agent 模組重構**
- `agents/swag_detector.md` — 取代舊版 detector.md + security-fraud-detector.md
- `agents/swag_reproducer.md` — 取代舊版 reproducer.md，新增 Python/WebSocket PoC 模板

**靜態規則升級**
- `rules/semgrep/swag-security-rules.yml` — 取代舊版 Java Semgrep 規則，新增 Python/JS/React 規則
- `rules/playwright/swag-playwright-specs.js` — 全新 Playwright 前端安全測試規範

---

## v1.0 → v2.0 (2026-06-01) — 原版 debug-hunter 財務安全版

- 初始版本，針對 Java/Spring Boot 金融系統
- 7 階段閉環（威脅建模 → 偵測 → 分類 → 復現 → 修復 → 驗收 → 回收）
- 三層防線（特徵比對 → Taint 污染流 → 金融不變量）
