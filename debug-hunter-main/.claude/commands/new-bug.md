請幫我建立一份 Bug Report。功能/問題描述：**$ARGUMENTS**

## 執行步驟

**Step 1：收集環境資訊**
執行：
```bash
python3 scripts/env_context.py
```

**Step 2：產出 Bug Report 草稿**
根據 `knowledge-base/swag-test-process.md` 的標準格式，自動填入以下欄位：

```markdown
## [BUG] $ARGUMENTS

### 嚴重程度
（根據描述自動判斷，可手動調整）
- [ ] P0 - 關鍵（金流異常、系統癱瘓）
- [ ] P1 - 嚴重（核心功能無法使用）
- [ ] P2 - 一般（有 workaround）
- [ ] P3 - 輕微（UI 瑕疵）

### 重現步驟
1. （請補充）
2.
3.

### 預期行為
（請補充）

### 實際行為
（請補充）

### 環境脈絡
（自動填入 env_context 收集結果）

### 附件
- [ ] 截圖 / 影片
- [ ] HAR 檔（Ramen 必附）
- [ ] Console Log
```

**Step 3：業務邏輯比對**
根據 `$ARGUMENTS` 描述的功能模組，對照 `knowledge-base/swag-business-logic.md` 中的業務不變量，判斷：
- 這是 Bug 還是設計如此（Known Issue）？
- 違反了哪條不變量（如 INV-LIVE-MOO-003、INV-WEB-001）？

**Step 4：建議嚴重度**
給出建議的 P0/P1/P2/P3 等級，並說明判斷依據。
