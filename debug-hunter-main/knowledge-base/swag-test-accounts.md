# SWAG 測試帳號管理（Test Accounts）

> 來源：Notion 測試帳號規範、jbot 使用手冊
> ⚠️ 本文件不記錄實際帳號密碼，僅記錄帳號類型、管理規則、jbot 操作語法。

---

## 一、帳號類型

| 類型 | 說明 | 主要用途 |
|------|------|---------|
| **Mod View** | 超級測試帳號，無需任何付費即可解鎖所有功能 | 快速驗證 UI、不需要鑽石的場景 |
| **Beta 帳號** | 掛有 `Beta` Tag 的主播帳號 | 測試未公開 Feature、未公開金流商 |
| **Non-beta 帳號** | 一般主播帳號（無 Beta Tag） | 模擬正式主播行為 |
| **一般用戶帳號** | 標準用戶帳號，可持有鑽石 | 測試打賞、購買、直播觀看 |
| **VIP 用戶帳號** | 特定 VIP 等級的用戶帳號 | 測試 VIP 特权功能 |

### Beta 帳號的特殊規則
- 部分 Feature 只對 Beta 帳號開放（可看到功能入口）
- 在 Live 環境測試**未公開金流商**時，必須使用 Beta 帳號
- 測完後記得**退發票**（避免測試資料污染正式帳戶）

---

## 二、VIP 等級

| 版本 | 範圍 | 備註 |
|------|------|------|
| **舊版** | Lv.0 - Lv.8 | 逐步廢棄 |
| **新版** | Lv.0 - Lv.100 | 見 GitHub issue #9889 |

**重置規則**：每 **3 個月**重置一次 VIP 等級

**升級方式**：任何花費行為皆累積 VIP 進度

---

## 三、jbot（Slack Bot）使用指南

> jbot 在 Slack 頻道 **`#swag-bot-pro`** 中使用。
> 主要功能：管理測試帳號的 Tag、存入/取出鑽石。

### 3.1 查詢帳號資訊

```
// 查詢用戶資訊（by email）
/jbot user info email@example.com

// 查詢用戶資訊（by user ID）
/jbot user info --id <user_id>
```

### 3.2 Tag 管理

```
// 新增 Tag
/jbot tag add --user <email_or_id> --tag <tag_name>

// 移除 Tag
/jbot tag remove --user <email_or_id> --tag <tag_name>

// 查看用戶 Tag 清單
/jbot tag list --user <email_or_id>
```

**常用 Tag**：
| Tag | 說明 |
|-----|------|
| `Beta` | 開放 Beta 功能入口 |
| `VIP` | VIP 特殊權限 |
| `QA` | 標記為 QA 測試帳號 |

### 3.3 鑽石（Diamond）存入 / 取出

```
// 存入鑽石
/jbot diamond deposit --user <email_or_id> --amount <數量>

// 取出鑽石（退款）
/jbot diamond withdraw --user <email_or_id> --amount <數量>

// 查詢鑽石餘額
/jbot diamond balance --user <email_or_id>
```

> **注意**：鑽石操作會記錄在後台 Log 中，測試完成後若需清帳，需手動 withdraw。

### 3.4 批次操作

```
// 批次存入鑽石給多帳號（格式依 jbot 版本不同，以 #swag-bot-pro 頻道為準）
/jbot diamond deposit --users <email1>,<email2> --amount <數量>
```

---

## 四、測試帳號準備 Checklist

### 直播間測試（一般場景）
- [ ] 主播帳號（Non-beta）× 1
- [ ] 用戶帳號 × 2（至少，模擬多用戶互動）
- [ ] 確認用戶帳號有足夠鑽石

### 一對一測試
- [ ] 主播帳號 × 1
- [ ] 用戶帳號 × 1（需有鑽石）
- [ ] 確認鑽石數量 ≥ 預扣金額（5 分鐘費用）

### Show 測試
- [ ] 主播帳號 × 1
- [ ] 用戶帳號 × 3（模擬票券購買，達標需多人）
- [ ] 確認各用戶帳號有足夠鑽石

### 支付測試
- [ ] Beta 帳號 × 1（若測試未公開金流商）
- [ ] 信用卡測試卡資訊（ECPay 提供的測試卡號）
- [ ] 確認 VPN **未啟用**（否則 IP 白名單會擋回調）
- [ ] 測試後記得退發票（Beta 帳號）

### 封鎖測試
- [ ] 主播帳號 × 1
- [ ] 用戶帳號 × 2（一個被封鎖、一個未封鎖）
- [ ] 驗證被封鎖用戶的所有互動行為

---

## 五、帳號狀態清理規範

> 每次大型測試後，應恢復帳號至乾淨狀態，避免污染下次測試。

| 項目 | 操作 |
|------|------|
| 測試鑽石 | 透過 jbot withdraw 取出 |
| 測試 Tag | 透過 jbot tag remove 移除 |
| 封鎖關係 | 手動到帳號設定取消封鎖 |
| 已購內容 | 通常無法還原（記錄 baseline 即可） |
| Beta Tag | 測試完未公開功能後視需求移除 |

---

## 六、帳號類型 × 測試場景對照

| 測試場景 | 建議帳號組合 |
|---------|------------|
| UI 快速驗證 | Mod View 帳號（無需鑽石） |
| 計費邏輯測試 | 一般用戶帳號 + 足量鑽石 |
| Beta Feature 測試 | Beta 主播帳號 + 一般用戶帳號 |
| FullTest 金流 | Beta 帳號 + 信用卡測試資訊 |
| VIP 功能測試 | 對應等級 VIP 帳號 |
| 中國 App（Ramen）測試 | 一般用戶帳號（Android 測試機） |
| 封鎖功能測試 | 主播帳號 + 2 組用戶帳號 |
