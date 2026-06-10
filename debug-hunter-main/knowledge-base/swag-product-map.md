# SWAG 產品地圖（Product Map）

> QA 必讀：每次測試前確認你在測哪個產品、哪個環境、哪個分支。
> 不同產品的技術堆疊、加密方式、分支完全不同。

---

## 產品總覽

| 類別 | 產品名稱 | 技術類型 | 核心說明 | 測試重點 |
|------|---------|---------|---------|---------|
| **主播端** | **Moor** | Mobile App (iOS/Android) | 主播專用：直播、上傳影片、貼文、限動。可申請 Beta 版 | Moor 版本通常比 Flutter Web 新 |
| **主播端** | **Flutter Web** | Flutter Web | 網頁版主播入口，須透過 **OBS** 連線。Web Production 登入主播帳號 → 點「建立」開啟 | 需安裝 OBS + Agora 插件才能測開播 |
| **用戶端** | **Sushi App** | Hybrid (Web View + Native Flutter) | 以 **Ramen(Web)** 為基礎，關鍵效能區域（直播間內）改由 **Native Flutter** 實作。目標成為主流 | Web↔Native 切換是否順暢；直播間狀態同步 |
| **用戶端** | **Ramen** | Web View in Android Native App | 純網頁包在 App 殼內。**目前用戶主力產品**。API Response 有加密（見下方） | 僅 **Android**；主要給中國用戶；有加密 |
| **用戶端** | **Ramen - MDM** | Web View in iOS Native App | 同 Ramen 但為 iOS 版本 | 僅 **iOS**；功能同 Android Ramen |
| **環境端** | **Web (Chrome/Safari)** | 一般瀏覽器 | `https://swag.live/` 前端版更主要測試環境 | PC 測 Chrome 為主、Safari 為輔 |
| **環境端** | **PWA** | 一般瀏覽器 | 網頁內點「加入主畫面」，偽裝成 App 的快捷入口 | 安裝後行為是否與 Web 一致 |

---

## 環境與分支對照

| 產品 | 測試 URL / 取得方式 | 對應分支 | 後端 |
|------|-------------------|---------|------|
| **Web 前端（測試版）** | `https://{v3-277}.app.swag.live`（版本號依當次不同）或從 GitHub Repo → View deployment | `v3.xxx` 分支 | 串接**正式環境**後端 |
| **Web 前端（正式）** | `https://swag.live/` | `v3.xxx` 最新 release | 正式環境 |
| **Ramen / Ramen-MDM** | 測試機上的 App | `feature/china-app` 分支（含加密/隱藏 swag 字樣等特殊設定） | 正式環境 |
| **Moor** | 測試機上的測試 App（Beta / Non-beta）| — | 正式環境 |
| **後端 (BE)** | 直接上正式環境，無獨立測試環境 | — | — |

> ⚠️ **重要**：後端無獨立測試環境，BE 發版即上正式，測試以**回歸測試**為主。

---

## Ramen API 加密機制

Ramen（含 MDM）的 API Response 有加密，目的是防止中間人攔截到敏感內容。

- **加密判斷方式**：在 Network 面板的 response header 中查看 `x-encrypted-algo`，欄位值即為所用加密演算法。
- **影響**：在 DevTools Network 面板可以看到 API Request，但 **Response Body 無法直接閱讀**（顯示加密字串）。
- **測試注意**：若需驗證 API Response 內容，需透過前端行為或後台資料比對，無法直接讀取 Network Response。

---

## 各產品 QA 測試策略

### Web（Chrome/Safari）
- 前端版更的**主要測試環境**，涵蓋大部分業務邏輯
- PC 測試以 **Chrome 為主、Safari 為輔**
- 手機橫屏暫不處理
- UI/UX 以「創意（設計稿）」為對齊基準

### Moor（主播端 App）
- 需準備 **Beta 帳號**與 **Non-beta 帳號**各一
- 若 Flutter Web 有重大更新，Moor 必須同步 Full Test
- 已知問題（Known Issues）：
  - **Transify key 露出**：已知問題，暫不處理
  - **置頂文字無法刪除**：執行刪除後主播端消失，但**用戶端仍顯示**
  - **一對一結算顯示異常**：超過預扣時間後關播，History 畫面不加預扣金額，但後台實際已收款

### Sushi App（用戶端 Hybrid）
- 重點測試：Web（首頁）→ Native（直播間）**切換是否順暢**（Loading 過久或閃退）
- 驗證：Web 端取得的鑽石/追蹤狀態，進入 Native 直播間後是否**即時更新**
- 效能：Native 直播間在不同 Android 機型的流暢度（理論上優於 Ramen Web View）

### Ramen / MDM（中國用戶端）
- 每週固定城市排程測試（詳見 `swag-china-qa.md`）
- 載入耗時標準：不得超過 **10 秒**
- 異常時需蒐集：螢幕錄影、網速截圖、.har 檔、Process ID & Version、DevTool 流水圖

---

## 測試工具清單

| 用途 | 工具 | 連結 |
|------|------|------|
| Android 螢幕投影/控制 | scrcpy | https://github.com/genymobile/scrcpy |
| Android ADB | ADB | https://esisterebbb.blogspot.com/... |
| iPhone 螢幕投影 | iDescriptor | https://github.com/iDescriptor/iDescriptor |
| 圖片/影片壓縮 | HandBrake | https://handbrake.fr/ |
| 電腦開播 | OBS | https://obsproject.com/ |
| OBS Agora 插件 | swag-flutter issue #7306 | GitHub |
| Spotlight 增強 | Raycast | https://www.raycast.com/ |
| 中國撥測 | BOCE 波測 | admin@swag.live / Swag5566 |
| ICP 備案查詢 | 工業和信息化部政務服務平台 | 點選「備案查詢」分類 |

---

## 金流測試範圍（FullTest）

> 金流測試僅針對特定支付管道，並非全測。

| 測試項目 | 是否測試 | 備註 |
|---------|---------|------|
| **信用卡** | ✅ 是 | 核心測試項目 |
| **AFTEE**（先享後付） | ✅ 是 | 核心測試項目 |
| **支付寶 / 轉帳 / 虛擬幣** | ❌ 否 | 暫不需測試 |

> ⚠️ 在 Live 環境測試**未公開的金流商**時，必須使用掛有 `Beta` Tag 的帳號，測完記得**退發票**。
