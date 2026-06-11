請立即執行環境脈絡收集，並顯示當前測試環境的完整資訊。

## 執行步驟

**Step 1：執行環境收集腳本**

```bash
python3 scripts/env_context.py
```

**Step 2：顯示摘要**
以表格格式顯示：
- OS 系統與架構
- 裝置類型（desktop / mobile）
- 網路類型（WiFi / 有線 / 4G / 5G）
- VPN 狀態（啟用 / 未啟用）
- IP 位置（城市、國家、ISP）

**Step 3：自動警告判斷**
- 若 VPN 啟用 → 顯示警告：「⚠️ VPN 啟用中——支付相關測試（ECPay/AFTEE）將因 IP 白名單失敗，請先關閉 VPN」
- 若地區非 TW → 顯示提示：「目前 IP 位於境外，部分 SWAG 功能可能受地理封鎖影響」

**Step 4：輸出可附加的 Bug Report 環境欄位**
輸出可直接複製貼到 Jira/GitHub Issue 的 Markdown 表格：

```markdown
## 環境脈絡
| 欄位 | 值 |
|------|---|
| 收集時間 | ... |
| OS | ... |
| 裝置類型 | ... |
| 網路 | ... |
| VPN | ... |
| IP / 位置 | ... |
```

若腳本執行失敗（未安裝 psutil），提示用戶：`pip3 install psutil requests`
