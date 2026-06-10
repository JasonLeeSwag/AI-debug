# 環境脈絡模式庫（Environment Context Patterns）

> 所有 SWAG QA 測試在執行前，必須收集並記錄當下的環境脈絡。
> 同一個 Bug 在不同環境下行為可能完全不同——環境脈絡是根因分析的關鍵證據。

---

## 標準環境脈絡欄位

每份測試報告、Bug report、PoC 復現記錄，都應附帶以下資訊：

```json
{
  "env_context": {
    "collected_at": "2026-06-10T10:30:00+08:00",
    "os": {
      "system": "macOS 14.5",
      "arch": "arm64",
      "device_type": "desktop"
    },
    "network": {
      "type": "wifi",
      "interface": "en0",
      "vpn_active": false,
      "vpn_interface": null
    },
    "location": {
      "ip": "114.x.x.x",
      "city": "Taipei",
      "country": "TW",
      "isp": "AS3462 Chunghwa Telecom",
      "timezone": "Asia/Taipei"
    }
  }
}
```

---

## 如何收集環境資訊

### Python 測試（pytest / 腳本）

```python
from scripts.env_context import collect, print_summary

# 在測試 setup 或 conftest.py 中
@pytest.fixture(scope="session", autouse=True)
def env_context(request):
    ctx = collect()
    print_summary(ctx)
    # 附加到測試報告的 metadata
    request.config._metadata = request.config._metadata or {}
    request.config._metadata["環境脈絡"] = ctx
    return ctx
```

### Playwright 測試

```javascript
// playwright.config.js 或個別測試的 beforeAll
const { collect_as_json } = require('../scripts/env_context');

test.beforeAll(async ({ page }) => {
  // 收集 Python 端環境（OS、網路、VPN、IP）
  const serverEnv = JSON.parse(await exec('python3 scripts/env_context.py --json'));

  // 收集瀏覽器端環境（user agent、螢幕、網路類型）
  const browserEnv = await page.evaluate(() => {
    const conn = navigator.connection || {};
    return {
      userAgent: navigator.userAgent,
      deviceType: /Mobi|Android|iPhone|iPad/i.test(navigator.userAgent) ? 'mobile' : 'desktop',
      screen: { width: screen.width, height: screen.height, dpr: window.devicePixelRatio },
      network: {
        type: conn.type || 'unknown',
        effectiveType: conn.effectiveType || 'unknown',
        downlinkMbps: conn.downlink || null,
        rttMs: conn.rtt || null,
      },
      timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
    };
  });

  console.log('[ENV]', JSON.stringify({ ...serverEnv, browser: browserEnv }, null, 2));
});
```

### Robot Framework

```robot
*** Settings ***
Library    ../scripts/env_context.py    WITH NAME    EnvCtx

*** Test Setup ***
Collect And Log Environment

*** Keywords ***
Collect And Log Environment
    ${ctx}=    EnvCtx.Collect Environment Context
    Set Suite Variable    ${ENV_CONTEXT}    ${ctx}
    # 支付相關測試：確認不在 VPN 下執行
    Run Keyword If    '${SUITE_NAME}' == 'Payment Tests'
    ...    EnvCtx.Assert No Vpn
```

### CLI 快速查詢

```bash
# 純文字摘要
python3 scripts/env_context.py

# JSON 格式（可 pipe 到 jq）
python3 scripts/env_context.py --json | jq '.network'

# 離線環境（跳過 IP 查詢）
python3 scripts/env_context.py --no-location
```

---

## 各環境對 SWAG 功能的影響

### PAT-ENV-001：VPN 啟用導致支付回調被擋

**症狀**：ECPay / 支付寶 / 微信支付回調成功，但平台後端 Log 顯示「IP not in whitelist」，點數未到帳。

**根因**：支付閘道設有 IP 白名單，VPN 出口 IP 不在許可清單內。

**重現條件**：
```
os: any
network.vpn_active: true
payment: ECPay / Alipay / WeChat
```

**QA 處理**：
```python
# conftest.py
from scripts.env_context import collect

def pytest_configure(config):
    ctx = collect()
    if ctx['network']['vpn_active'] and 'payment' in config.option.markexpr:
        pytest.exit(
            "⚠️  偵測到 VPN 啟用，支付回調測試需要真實台灣 IP，請關閉 VPN",
            returncode=2
        )
```

---

### PAT-ENV-002：弱網路（4G/低 downlink）導致 WebSocket 斷線打賞失敗

**症狀**：直播打賞後點數已扣，但主播端未收到；重試機制觸發雙重扣款。

**重現條件**：
```
network.effectiveType: "3g" 或 "2g"
network.rttMs: > 500
feature: live_gifting / WebSocket
```

**Playwright 弱網路模擬**：
```javascript
test('TC-LIVE-弱網路打賞不重複扣點', async ({ page, context }) => {
  // 模擬 4G 低訊號
  await context.route('**/*', async route => {
    await new Promise(r => setTimeout(r, 800)); // 模擬 800ms 延遲
    await route.continue();
  });

  const before = await getUserPoints(page);
  await sendGift(page, { points: 100 });
  await page.waitForTimeout(5000); // 等待重試機制
  const after = await getUserPoints(page);

  // 只能扣一次，不管重試幾次
  expect(after).toBe(before - 100);
});
```

---

### PAT-ENV-003：行動裝置 / 觸控螢幕 UI 差異

**症狀**：桌面版測試全過，但 iOS Safari 上點數輸入框出現小數鍵盤，導致使用者輸入 `100.0`，後端拒絕（只接受整數）。

**重現條件**：
```
os.device_type: "mobile"
os.system: "iOS"
browser: Safari
feature: topup_input / bet_input
```

**Playwright 行動裝置測試**：
```javascript
const { devices } = require('@playwright/test');

// 測試 iPhone 14 Pro
test.use({ ...devices['iPhone 14 Pro'] });

test('TC-MOBILE-儲值金額輸入', async ({ page }) => {
  await page.goto('/payment/topup');
  const input = page.locator('[data-testid="amount-input"]');

  // 行動裝置應使用 number 鍵盤（無小數點）
  await expect(input).toHaveAttribute('inputmode', 'numeric');
  await expect(input).toHaveAttribute('pattern', '[0-9]*');
});
```

---

### PAT-ENV-004：時區差異導致博弈遊戲開局時間錯誤

**症狀**：海外玩家（UTC+0）看到的龍虎鬥開局倒數計時與台灣玩家（UTC+8）不同步，導致延遲投注窗口判斷錯誤。

**重現條件**：
```
location.timezone: "UTC" 或非 "Asia/Taipei"
feature: gambling_round_timer
```

**QA 檢查**：
```python
import pytest
from datetime import datetime, timezone, timedelta

def test_round_timer_uses_server_time(api_client):
    """
    開局時間應使用伺服器時間（Asia/Taipei UTC+8），
    不應受客戶端時區影響
    """
    round_info = api_client.get('/api/game/dragon-tiger/current-round')
    server_time = round_info['server_time']   # 後端回傳
    close_time  = round_info['bet_close_at']  # 投注截止時間

    # 確認是 UTC+8
    assert '+08:00' in server_time or 'CST' in server_time, \
        f"伺服器時間應為 UTC+8，實際：{server_time}"

    # 確認截止時間在未來（不受客戶端時區影響）
    close_dt = datetime.fromisoformat(close_time)
    now_utc8 = datetime.now(timezone(timedelta(hours=8)))
    assert close_dt > now_utc8, "投注截止時間已過（可能時區換算錯誤）"
```

---

### PAT-ENV-005：地理位置封鎖導致直播間無法存取

**症狀**：特定地區 IP（如中國大陸）被 CDN 或 Nginx 封鎖，導致直播流加載失敗，QA 環境若未模擬地區限制，則測試無法覆蓋此情境。

**環境變數補充**：在 Bug report 中標注 `location.country` 是重要證據。

---

### PAT-ENV-006：OS 版本差異導致 Flutter Web 渲染問題

**症狀**：Flutter Web 在 Windows 10 Chrome 上正常，但 Windows 7 Edge 上字體渲染模糊，點擊區域偏移。

**重現條件**：
```
os.system: "Windows"
os.version: "10.0.14393" (Windows 10 舊版) 或 "6.1" (Windows 7)
browser: Edge 舊版
```

---

## 環境脈絡 × Bug 嚴重度加權

當 Bug 只在特定環境下出現，嚴重度調整原則：

| 環境限制 | 嚴重度調整 | 說明 |
|---------|-----------|------|
| 只在 VPN 下出現 | 降 1 級 | 一般用戶不開 VPN |
| 只在 2G/3G 弱網路 | 不降級 | 許多東南亞用戶用手機 4G |
| 只在特定 OS 版本 | 降 1 級，但要確認目標用戶 OS 分布 | — |
| 只在境外 IP | 依業務決定 | 若 SWAG 計畫進軍境外，不降級 |
| 在所有環境都出現 | 原始嚴重度 | — |

---

## Bug Report 環境脈絡範本

貼到 Jira / Linear / GitHub Issue 時，固定附帶這段：

```markdown
## 環境脈絡
| 欄位 | 值 |
|------|---|
| 收集時間 | 2026-06-10 10:30:00 +08:00 |
| OS | macOS 14.5 (arm64) |
| 裝置類型 | desktop |
| 網路 | WiFi (en0) |
| VPN | 未啟用 |
| IP / 位置 | 114.x.x.x / Taipei, TW |
| ISP | Chunghwa Telecom |
| 瀏覽器（若有） | Chrome 125 / iPhone 14 Pro Safari |
| 螢幕（若有） | 390×844 @3x (mobile) |
| 網路品質（若有） | effectiveType: 4g / RTT: 45ms |
```

---

## 規則摘要

| Rule ID | 規則 | 嚴重度 |
|---------|------|--------|
| RULE-ENV-001 | 所有測試必須附帶環境脈絡快照 | MAJOR |
| RULE-ENV-002 | 支付相關測試執行前必須確認 VPN 狀態 | CRITICAL |
| RULE-ENV-003 | 行動裝置測試必須覆蓋 iOS Safari + Android Chrome | MAJOR |
| RULE-ENV-004 | 弱網路（3G/2G）模擬必須涵蓋打賞、支付流程 | MAJOR |
| RULE-ENV-005 | 時區相關時間顯示必須以 UTC+8 伺服器時間為準 | MAJOR |
