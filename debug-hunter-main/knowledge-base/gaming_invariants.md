# SWAG 博弈遊戲系統不變量與防禦指南 (Gaming Invariants & Defenses)

> **檔案識別碼**: gaming-invariants
> **適用範疇**: 龍虎鬥 (Dragon Tiger)、百家樂 (Baccarat)、骰寶 (Sic Bo)、轉盤 (Roulette) 等博弈遊戲。
> **技術棧**: Python (Game Core), Node.js/WebSockets, React/JSX, JS, RobotFramework, Playwright

---

## 1. 博弈核心不變量 (Gaming Invariants)

博弈遊戲涉及高頻、高並發的資金（鑽石）劃轉。任何微小的邏輯漏洞或並發衝突，都會在短時間內造成無法挽回的巨大資損。以下不變量在遊戲生命週期中必須**恆成立**。

| 不變量 ID | 名稱 | 數學/邏輯定義 | 驗證機制 (Assert/Check) |
| :--- | :--- | :--- | :--- |
| **INV-GAME-01** | **下注餘額守恆** | `用戶下注前餘額 - 下注鑽石數 == 用戶下注後餘額` | 扣款必須使用數據庫事務 (Transaction)，且必須校驗 `Balance >= BetAmount`。 |
| **INV-GAME-02** | **結算金額守恆** | `用戶贏取鑽石數 == 下注鑽石數 * 賠率 - 抽水 (Rake)` | 賠率表 (Paytable) 必須硬編碼於後端，嚴禁由前端傳入賠率或派彩金額。 |
| **INV-GAME-03** | **下注時效守衛** | `下注請求時間 < 遊戲開牌時間 (Round_Lock_Time)` | 嚴禁在開牌後、甚至開牌中接受任何下注或修改下注的請求。 |
| **INV-GAME-04** | **單局下注上限** | `SUM(User_Bets_In_Round) <= Round_Max_Bet` | 必須防止單一用戶通過並發請求突破單局最高下注額度限制。 |
| **INV-GAME-05** | **開牌隨機不可預測** | `RNG_Result` 必須由後端加密種子或合規硬體 (HRNG) 生成 | 前端 React/JS 僅負責渲染動畫，嚴禁在開牌前將開牌結果發送至前端。 |

---

## 2. 常見博弈遊戲 Bug 模式與攻擊路徑

### PAT-GAME-101: 延遲下注與「未來之眼」 (Late Betting / Past Posting)
*   **觸發特徵**: 遊戲服務器（WebSockets）在開牌（如龍虎鬥開牌、百家樂發牌）時，鎖定下注的狀態流轉存在延遲，或者校驗下注時間使用的是「客戶端時間」而非「服務器數據庫時間」。
*   **攻擊路徑**: 攻擊者監聽 WebSockets 廣播。當龍虎鬥開出「龍」的瞬間，攻擊者利用高腳本（Python/WebSockets）在服務器尚未完全鎖定下注的幾毫秒內，發送「投注龍」的請求。由於服務器時間校驗不嚴，該投注被視為有效，實現 **100% 勝率**。
*   **防禦策略**:
    ```python
    # Python 遊戲核心防禦範例：嚴格時間鎖與狀態機校驗
    def process_bet(user_id, game_round_id, bet_area, bet_amount):
        # 1. 使用 Redis 樂觀鎖或 DB 鎖鎖定該局遊戲狀態
        game_round = GameRound.objects.select_for_update().get(id=game_round_id)
        
        # 2. 嚴格校驗遊戲狀態
        if game_round.status != RoundStatus.BETTING:
            raise GameStateException("Betting is already locked for this round!")
            
        # 3. 嚴格校驗服務器當前時間
        if datetime.utcnow() >= game_round.lock_time:
            # 即使狀態還是 BETTING，但時間已過，強制鎖定並拒絕
            game_round.status = RoundStatus.LOCKED
            game_round.save()
            raise GameStateException("Round lock time reached. Bet rejected.")
    ```

### PAT-GAME-102: 並發重複投注與負餘額 (Double Betting / Negative Balance)
*   **觸發特徵**: 扣除用戶餘額時，未採用悲觀鎖（`SELECT FOR UPDATE`）、樂觀鎖（`CAS / Version`）或數據庫約束，而是採用了「先讀取餘額，在內存計算，再寫回數據庫」的危險模式。
*   **攻擊路徑**: 攻擊者餘額僅剩 100 鑽石。他使用腳本同時發起 10 個「投注 100 鑽石」的並發請求。因為服務器並行處理，10 個請求同時讀取到餘額為 100，全部校驗通過並扣款，導致用戶投注了 1000 鑽石，**餘額變為 -900 鑽石**。
*   **防禦策略**:
    ```sql
    -- SQL 原子扣款防禦
    UPDATE user_wallet 
    SET balance = balance - :bet_amount 
    WHERE user_id = :user_id AND balance >= :bet_amount;
    -- 必須檢查受影響行數 (Rows Affected)，若為 0 則拋出餘額不足異常。
    ```

### PAT-GAME-103: 斷線重連狀態丟失與重複結算 (Reconnection Double Claim)
*   **觸發特徵**: 遊戲結算時，若用戶在開牌瞬間斷線，重新連接時系統會嘗試重新初始化或補償結算。
*   **攻擊路徑**: 攻擊者在百家樂即將開牌時主動斷開 WebSocket 連接。服務器在處理斷線重連邏輯時，由於狀態標記未及時更新，導致該局遊戲被結算了兩次，用戶獲得了雙倍的派彩。
*   **防禦策略**: 每一局遊戲的結算必須綁定唯一的 `game_round_id`。在數據庫中建立 `game_settlement` 表，並將 `game_round_id` 與 `user_id` 設為**聯合唯一索引 (Unique Index)**，確保任何情況下單局單人只能結算一次。

---

## 3. SWAG QA 博弈自動化測試與 Bug 偵測劇本

### RobotFramework 遊戲高並發下注測試 (防並發負餘額)
```robot
*** Settings ***
Library    Process
Library    RequestsLibrary
Library    Collections

*** Variables ***
${BASE_URL}          https://game.swag.live/api/v1
${BET_URL}           /game/bet
${USER_TOKEN}        Bearer_Valid_Token_Here

*** Test Cases ***
Verify Concurrent Betting Negative Balance Prevention
    [Documentation]    測試並發下注時，系統是否能防止餘額被扣成負數。
    [Setup]    Reset User Balance To 100
    
    # 創建 5 個並發進程同時發送投注 100 鑽石的請求
    ${p1}=    Start Process    python    -c    "import requests; requests.post('${BASE_URL}${BET_URL}', json={'roundId': 1001, 'area': 'DRAGON', 'amount': 100}, headers={'Authorization': '${USER_TOKEN}'})"
    ${p2}=    Start Process    python    -c    "import requests; requests.post('${BASE_URL}${BET_URL}', json={'roundId': 1001, 'area': 'DRAGON', 'amount': 100}, headers={'Authorization': '${USER_TOKEN}'})"
    ${p3}=    Start Process    python    -c    "import requests; requests.post('${BASE_URL}${BET_URL}', json={'roundId': 1001, 'area': 'DRAGON', 'amount': 100}, headers={'Authorization': '${USER_TOKEN}'})"
    
    ${r1}=    Wait For Process    ${p1}
    ${r2}=    Wait For Process    ${p2}
    ${r3}=    Wait For Process    ${p3}
    
    # 驗證最終餘額
    ${balance_resp}=    GET On Session    swag_api    /user/balance    headers={'Authorization': '${USER_TOKEN}'}
    ${balance}=    Convert To Integer    ${balance_resp.json()['balance']}
    Should Be True    ${balance} >= 0    User balance is negative: ${balance}!
```

### Playwright / JS 模擬 Websocket 延遲投注攻擊 (Past Posting Test)
```javascript
const { test, expect } = require('@playwright/test');
const WebSocket = require('ws');

test('測試 WebSocket 開牌後延遲投注拒絕', async () => {
  const wsUrl = 'wss://game.swag.live/ws/v1/dragon-tiger';
  const ws = new WebSocket(wsUrl, {
    headers: { 'Authorization': 'Bearer_Test_Token' }
  });

  await new Promise((resolve) => ws.on('open', resolve));

  // 監聽開牌消息
  ws.on('message', async (data) => {
    const message = JSON.parse(data.toString());
    
    // 當收到開牌結果廣播時（此時投注通道應已關閉）
    if (message.event === 'ROUND_RESULT') {
      const roundId = message.roundId;
      const winner = message.winner; // 例如 'DRAGON'
      
      // 惡意嘗試在收到結果後，立即對贏家區域追加投注
      const betPayload = JSON.stringify({
        action: 'BET',
        roundId: roundId,
        area: winner,
        amount: 100
      });
      
      ws.send(betPayload);
    }
    
    // 監聽服務器的回應，必須是拒絕投注
    if (message.event === 'BET_RESPONSE' && message.roundId === roundId) {
      expect(message.status).toBe('FAILED');
      expect(message.error).toContain('locked');
      ws.close();
    }
  });
});
```
