# SWAG 博弈遊戲 Bug 模式知識庫
# gambling-game-patterns.md
# 版本：1.0.0 | 維護團隊：SWAG QA 部門
# 適用範圍：龍虎鬥、百家樂等博弈遊戲模組

---

## 1. 概述

SWAG 平台的博弈遊戲模組面臨三大核心風險：

### 1.1 公正性（Fairness）
博弈遊戲的隨機數必須真正不可預測，確保平台與玩家之間的公平性。使用可預測的偽隨機數生成器（如 Python `random` 模組）會使遊戲結果可被玩家分析和預測，引發嚴重的法規合規與商譽問題。

### 1.2 賠付正確性（Payout Accuracy）
每一筆賠付金額必須精確，賠率計算不允許浮點誤差。不正確的賠付輕則引發玩家客訴，重則造成財務不平衡和法規違規。

### 1.3 並發安全（Concurrency Safety）
博弈結算是高並發場景：多玩家同時下注、多 worker 同時處理結算任務。必須使用分散式鎖和資料庫原子操作防止競態條件導致的雙重結算或超額押注。

---

## 2. 博弈遊戲架構說明

### 2.1 龍虎鬥（Dragon Tiger）

```
遊戲流程：
┌─────────────────────────────────────────────────────────┐
│  BETTING      │  DEALING      │  SETTLEMENT   │  PAYOUT  │
│  (30秒)       │  (發牌)       │  (計算結果)   │  (入帳)  │
│               │               │               │          │
│  接受下注     │  生成牌局     │  比較點數     │  賠付    │
│  驗證下注     │  secrets.RNG  │  龍/虎/平局   │  更新餘額│
│  鎖定下注     │  廣播結果     │  觸發結算     │  清帳    │
└─────────────────────────────────────────────────────────┘

賠率規則：
- 龍贏：押龍 1:1（扣 5% 平台費 → 實際 0.95:1）
- 虎贏：押虎 1:1（扣 5% 平台費 → 實際 0.95:1）
- 平局：押平局 8:1；押龍/虎退還一半押注
- 特殊：押龍/虎且開平局 → 退還 50% 押注
```

### 2.2 百家樂（Baccarat）

```
遊戲流程：
┌────────────────────────────────────────────────────────────┐
│  BETTING      │  DEALING      │  COMPARE      │  PAYOUT    │
│  (30秒)       │  (發牌補牌)   │  (開牌比較)   │  (結算)    │
│               │               │               │            │
│  押閒/莊/和   │  依規則補牌   │  計算點數     │  依賠率    │
│  驗下注限額   │  服務端執行   │  取個位數     │  付賠款    │
│               │  廣播給前端   │  判定勝負     │  扣平台費  │
└────────────────────────────────────────────────────────────┘

賠率規則：
- 閒（Player）贏：1:1
- 莊（Banker）贏：1:1 扣 5% 佣金（實際 0.95:1）
- 和（Tie）：8:1；押閒/莊本金退還

補牌規則（必須服務端強制執行）：
- 閒點 0-5：補牌；6-7：停牌
- 莊點 0-2：必補；3-6：視閒家第三張決定；7：停牌
```

---

## 3. Bug 模式

### PAT-RNG-001：Python random 模組不適合博弈

**描述：**
Python `random` 模組使用 Mersenne Twister（MT19937）算法，是偽隨機數生成器（PRNG）。MT 在數學上已被證明：觀察 624 個連續的 32-bit 輸出後，可完全重建內部狀態，進而預測所有後續輸出。在博弈場景中，這意味著玩家可以通過觀察足夠的遊戲結果來預測未來牌局。

**觸發特徵：**

```python
import random  # 危險信號：博弈代碼中 import random

# 常見錯誤模式一：直接使用 random.choice
def draw_card() -> int:
    card_values = list(range(1, 14)) * 4  # 4 副牌
    return random.choice(card_values)  # 可被預測

# 常見錯誤模式二：shuffle 洗牌
def create_shuffled_deck() -> list:
    deck = list(range(52))
    random.shuffle(deck)  # Mersenne Twister 洗牌，可被還原
    return deck

# 常見錯誤模式三：固定種子（最危險，測試代碼流入正式環境）
random.seed(42)
result = random.randint(1, 6)  # 完全可預測

# 常見錯誤模式四：用 random.random() 產生偽機率
def should_trigger_bonus() -> bool:
    return random.random() < 0.001  # 1/1000 觸發，可被預測
```

**危害等級：** P0 CRITICAL

**危害說明：**
- 玩家可通過統計足夠樣本還原 MT 狀態，預測下一局結果
- 平台面臨博弈公正性認證失效
- 台灣《電子遊戲場業管理條例》合規風險
- 一旦曝光，平台商譽損失極為嚴重

**修復策略：**

```python
import secrets
import os
from typing import TypeVar

T = TypeVar('T')

# 正確方案一：使用 secrets 模組（推薦）
def draw_card_secure() -> int:
    """從牌堆中安全隨機抽牌"""
    card_values = list(range(1, 14)) * 4
    return secrets.choice(card_values)

# 正確方案二：密碼學安全洗牌（Fisher-Yates with secrets）
def create_shuffled_deck_secure() -> list:
    """創建密碼學安全的洗牌牌堆"""
    deck = list(range(52))
    n = len(deck)
    for i in range(n - 1, 0, -1):
        # secrets.randbelow 使用 os.urandom()，密碼學安全
        j = secrets.randbelow(i + 1)
        deck[i], deck[j] = deck[j], deck[i]
    return deck

def secure_choice(population: list) -> T:
    """密碼學安全的 random.choice 替代"""
    if not population:
        raise ValueError("序列不能為空")
    return population[secrets.randbelow(len(population))]

def secure_random_float() -> float:
    """生成 [0.0, 1.0) 的密碼學安全浮點數"""
    # 使用 8 bytes（64 bits）產生高精度浮點數
    return int.from_bytes(os.urandom(8), byteorder='big') / (2**64)

# 正確方案三：可驗證隨機（Provably Fair，最高等級）
import hashlib
import hmac

class ProvablyFairRNG:
    """
    可驗證公平 RNG：
    - 服務端事先公佈 server_seed 的 hash
    - 玩家可提供 client_seed（使結果部分依賴玩家）
    - 遊戲結束後公佈 server_seed，玩家可自行驗證
    """
    def __init__(self, server_seed: bytes, client_seed: bytes, nonce: int):
        self.server_seed = server_seed
        self.client_seed = client_seed
        self.nonce = nonce

    def generate(self) -> bytes:
        message = f"{self.client_seed.hex()}:{self.nonce}".encode()
        return hmac.new(self.server_seed, message, hashlib.sha256).digest()

    def get_server_seed_hash(self) -> str:
        """公佈 server_seed 的 hash（遊戲開始前公佈，遊戲後才公佈原始值）"""
        return hashlib.sha256(self.server_seed).hexdigest()
```

**反哺規則：**
```
RULE-RNG-001: 博弈相關模組禁止 import random，違者為 CRITICAL 缺陷。
  - 掃描路徑: game/, gambling/, baccarat/, dragon_tiger/
  - 掃描模式: ^import random$|^from random import
  - 例外白名單: test_*.py（需 mock 時允許）
  - 嚴重度: CRITICAL
```

---

### PAT-RNG-002：服務端/客戶端 RNG 結果不一致

**描述：**
為了降低延遲，將 RNG 邏輯移到前端計算，服務端只做驗證。這種架構下前端可以在發送結果前先計算出最有利的結果，或通過抓包分析 RNG 種子。

**觸發特徵：**

```javascript
// 前端錯誤：在客戶端生成遊戲結果
function generateGameResult(gameId) {
    // 前端計算結果，再傳給服務端 "驗證"
    const seed = Math.random();  // 客戶端種子，可被操控
    const dragonCard = Math.floor(seed * 13) + 1;
    const tigerCard = Math.floor(Math.random() * 13) + 1;

    return {
        game_id: gameId,
        dragon_card: dragonCard,
        tiger_card: tigerCard,
        result: dragonCard > tigerCard ? 'dragon' : 'tiger'
    };
}

// 更危險：前端傳送計算好的結果
async function submitGameResult(result) {
    await api.post('/game/result', result);  // 服務端直接信任！
}
```

**危害等級：** P0 CRITICAL

**修復策略：**

```python
# 正確：服務端完全主導 RNG，前端只負責顯示

# 服務端：生成並儲存結果
async def create_game_round(room_id: str) -> dict:
    """創建新一局，服務端生成所有隨機數"""
    deck = create_shuffled_deck_secure()  # 服務端洗牌

    # 結果先加密存入 DB，下注期間不公開
    game_round = await GameRound.objects.acreate(
        room_id=room_id,
        dragon_card=deck[0],
        tiger_card=deck[1],
        result=determine_result(deck[0], deck[1]),
        status='BETTING',
        result_hash=hashlib.sha256(  # 公佈 hash，讓玩家可後驗
            f"{deck[0]}:{deck[1]}".encode()
        ).hexdigest()
    )

    # 回傳 round_id 和 result_hash（不含實際結果）
    return {
        "round_id": str(game_round.id),
        "result_hash": game_round.result_hash,  # 可驗證，但無法反推
        "betting_ends_at": (timezone.now() + timedelta(seconds=30)).isoformat()
    }

# 下注結束後廣播結果
async def reveal_result(round_id: str) -> dict:
    game = await GameRound.objects.aget(id=round_id)
    await game.aupdate(status='REVEALED')

    return {
        "dragon_card": game.dragon_card,
        "tiger_card": game.tiger_card,
        "result": game.result,
        # 公佈原始值，玩家可自行驗算 sha256
        "result_preimage": f"{game.dragon_card}:{game.tiger_card}"
    }
```

**反哺規則：**
```
RULE-RNG-002: 遊戲結果只能由服務端生成，前端提交的結果一律視為無效。
  - 觸發條件: API 端點接受包含 result/outcome/card 的請求體
  - 掃描模式: request\.json.*result|request\.form.*card_value
  - 嚴重度: CRITICAL
```

---

### PAT-ODDS-001：百家樂賠率邊計算錯誤

**描述：**
百家樂莊家（Banker）勝率略高於閒家，因此規則上莊家贏須扣除 5% 佣金（Commission）。若遺漏此佣金計算，長期下來平台將多付出大量賠款。

**觸發特徵：**

```python
# 錯誤一：莊家贏不扣佣金
def calculate_baccarat_payout(bet_side: str, bet_amount: float, winner: str) -> float:
    if bet_side == winner:
        return bet_amount * 2.0  # 錯誤：莊家贏應為 bet_amount * 1.95（含本金）
    return 0

# 錯誤二：float 計算佣金
def calculate_banker_commission(bet_amount: float) -> float:
    commission = bet_amount * 0.05  # float 誤差
    return bet_amount - commission   # 累積誤差
```

**危害等級：** P1 HIGH

**修復策略：**

```python
from decimal import Decimal, ROUND_HALF_DOWN
from enum import Enum

class BaccaratBetSide(str, Enum):
    PLAYER = 'player'   # 閒
    BANKER = 'banker'   # 莊
    TIE = 'tie'         # 和

class BaccaratResult(str, Enum):
    PLAYER = 'player'
    BANKER = 'banker'
    TIE = 'tie'

# 賠率常數（用字串初始化，避免 float 誤差）
BACCARAT_ODDS = {
    # (下注方, 結果) -> (本金返還倍數, 淨利倍數)
    (BaccaratBetSide.PLAYER, BaccaratResult.PLAYER):  (Decimal('1'), Decimal('1')),
    (BaccaratBetSide.PLAYER, BaccaratResult.BANKER):  (Decimal('0'), Decimal('0')),
    (BaccaratBetSide.PLAYER, BaccaratResult.TIE):     (Decimal('1'), Decimal('0')),  # 和局退本金
    (BaccaratBetSide.BANKER, BaccaratResult.PLAYER):  (Decimal('0'), Decimal('0')),
    (BaccaratBetSide.BANKER, BaccaratResult.BANKER):  (Decimal('1'), Decimal('0.95')),  # 扣5%佣金
    (BaccaratBetSide.BANKER, BaccaratResult.TIE):     (Decimal('1'), Decimal('0')),  # 和局退本金
    (BaccaratBetSide.TIE,    BaccaratResult.PLAYER):  (Decimal('0'), Decimal('0')),
    (BaccaratBetSide.TIE,    BaccaratResult.BANKER):  (Decimal('0'), Decimal('0')),
    (BaccaratBetSide.TIE,    BaccaratResult.TIE):     (Decimal('1'), Decimal('8')),  # 8:1
}

def calculate_baccarat_payout(
    bet_side: BaccaratBetSide,
    bet_amount: Decimal,
    result: BaccaratResult
) -> Decimal:
    """
    計算百家樂賠付金額（含本金）。

    返回值：玩家最終收到的點數（0 表示全輸）
    """
    key = (bet_side, result)
    if key not in BACCARAT_ODDS:
        raise ValueError(f"未知的賠率組合: {key}")

    principal_multiplier, profit_multiplier = BACCARAT_ODDS[key]
    bet = Decimal(str(bet_amount))

    # 返還 = 本金 * 本金倍數 + 本金 * 淨利倍數
    payout = bet * principal_multiplier + bet * profit_multiplier
    return payout.quantize(Decimal('1'), rounding=ROUND_HALF_DOWN)


# 測試案例
if __name__ == '__main__':
    # 莊家贏，押莊 1000 點
    payout = calculate_baccarat_payout(
        BaccaratBetSide.BANKER, Decimal('1000'), BaccaratResult.BANKER
    )
    assert payout == Decimal('1950'), f"期望 1950，得到 {payout}"  # 1000本金 + 950淨利

    # 和局，押閒 500 點
    payout = calculate_baccarat_payout(
        BaccaratBetSide.PLAYER, Decimal('500'), BaccaratResult.TIE
    )
    assert payout == Decimal('500'), f"期望 500（退本金），得到 {payout}"
```

**反哺規則：**
```
RULE-ODDS-001: 百家樂莊家賠付必須使用 Decimal('0.95') 倍數，禁止 2.0 倍。
  - 掃描模式: banker.*\*\s*2\.0|bet_amount\s*\*\s*2
  - 嚴重度: HIGH
```

---

### PAT-ODDS-002：龍虎鬥平局賠率混淆

**描述：**
龍虎鬥平局規則較特殊：押龍/虎的玩家在開平局時退還 50% 押注（而非全部退還或全輸），但很容易與「全退」或「全輸」搞混，導致賠付邏輯錯誤。

**觸發特徵：**

```python
# 錯誤一：平局時押龍/虎全部退還
def dragon_tiger_payout_wrong_v1(bet_side: str, bet_amount: int, result: str) -> int:
    if result == 'tie':
        if bet_side in ('dragon', 'tiger'):
            return bet_amount  # 錯誤：應退 50%，不是全退

# 錯誤二：平局時押龍/虎全輸
def dragon_tiger_payout_wrong_v2(bet_side: str, bet_amount: int, result: str) -> int:
    if result == 'tie':
        return 0  # 錯誤：押龍/虎應退 50%，押平局才是全輸（若沒押平局）

# 錯誤三：平局賠率搞錯（8:1 含本金還是 8:1 純利）
def dragon_tiger_tie_wrong(bet_amount: int) -> int:
    return bet_amount * 8  # 錯誤：應為 bet_amount * 9（含本金的 8:1）
```

**危害等級：** P1 HIGH

**修復策略：**

```python
from decimal import Decimal, ROUND_HALF_DOWN

# 龍虎鬥賠率規則（正確版本）
# 規則說明：
# - 押龍/虎且贏：1:1（含本金總回 2 倍）
# - 押龍/虎且輸：本金全輸
# - 押龍/虎且平局：退還 50% 本金（這是關鍵）
# - 押平局且中：8:1（含本金總回 9 倍）
# - 押平局且未中：本金全輸

def calculate_dragon_tiger_payout(
    bet_side: str,  # 'dragon', 'tiger', 'tie'
    bet_amount: Decimal,
    result: str     # 'dragon', 'tiger', 'tie'
) -> Decimal:
    """
    計算龍虎鬥賠付金額。

    Returns:
        玩家收到的點數（不含原始押注的損益，純粹返還）
        0 表示全輸
    """
    bet = Decimal(str(bet_amount))

    if result == 'tie':
        if bet_side == 'tie':
            # 押平局且中：8:1 純利 + 本金 = 9 倍
            payout = bet * Decimal('9')
        else:
            # 押龍/虎且開平局：退還 50% 本金
            payout = (bet * Decimal('0.5')).quantize(
                Decimal('1'), rounding=ROUND_HALF_DOWN
            )
    elif bet_side == result:
        # 押對了：1:1（純利）+ 本金 = 2 倍
        payout = bet * Decimal('2')
    else:
        # 輸了：全輸
        payout = Decimal('0')

    return payout


# 驗證測試
def test_dragon_tiger_payout():
    # 案例一：押龍 1000，開龍 → 贏 2000
    assert calculate_dragon_tiger_payout('dragon', Decimal('1000'), 'dragon') == 2000

    # 案例二：押龍 1000，開虎 → 輸 0
    assert calculate_dragon_tiger_payout('dragon', Decimal('1000'), 'tiger') == 0

    # 案例三：押龍 1000，開平局 → 退 500
    assert calculate_dragon_tiger_payout('dragon', Decimal('1000'), 'tie') == 500

    # 案例四：押平局 100，開平局 → 贏 900
    assert calculate_dragon_tiger_payout('tie', Decimal('100'), 'tie') == 900

    # 案例五：押平局 100，開龍 → 輸 0
    assert calculate_dragon_tiger_payout('tie', Decimal('100'), 'dragon') == 0

    print("所有龍虎鬥賠率測試通過")
```

**反哺規則：**
```
RULE-ODDS-002: 龍虎鬥平局賠付必須使用 50% 退款邏輯，不得為 0 或 100%。
  - 測試覆蓋: 必須包含 tie_result_with_dragon_bet 測試案例
  - 嚴重度: HIGH
```

---

### PAT-BET-001：下注時序競態（最大押注超限）

**描述：**
多個並發下注請求同時讀取當前局的總押注量，各自判斷是否超過上限後執行下注，導致最終總押注量超過設定上限。

**觸發特徵：**

```python
# 錯誤：非原子的下注上限校驗
async def place_bet(game_round_id: str, user_id: int, bet_side: str, amount: Decimal):
    game = await GameRound.objects.aget(id=game_round_id)

    # 讀取當前局總押注
    current_total = await Bet.objects.filter(
        game_round_id=game_round_id
    ).aaggregate(total=Sum('amount'))['total'] or 0

    MAX_TOTAL_BET = Decimal('1000000')

    # --- 並發請求在此插入，也讀到相同的 current_total ---
    if current_total + amount > MAX_TOTAL_BET:
        raise BetLimitExceededError()

    # 兩個並發請求都通過了上限校驗，各自下注
    await Bet.objects.acreate(
        game_round_id=game_round_id,
        user_id=user_id,
        bet_side=bet_side,
        amount=amount
    )
```

**危害等級：** P1 HIGH

**修復策略：**

```python
import redis
from decimal import Decimal

redis_client = redis.Redis(host='redis-host', port=6379, db=0)

async def place_bet_safe(
    game_round_id: str,
    user_id: int,
    bet_side: str,
    amount: Decimal
) -> dict:
    """使用 Redis 原子操作確保下注上限不被超越"""
    MAX_TOTAL_BET = Decimal('1000000')
    bet_key = f"game:bet_total:{game_round_id}:{bet_side}"

    # 使用 Redis INCRBYFLOAT + Lua 腳本做原子加減
    # 先嘗試原子增加，再判斷是否超限
    lua_script = """
    local current = redis.call('INCRBYFLOAT', KEYS[1], ARGV[1])
    if tonumber(current) > tonumber(ARGV[2]) then
        redis.call('INCRBYFLOAT', KEYS[1], -ARGV[1])  -- 回滾
        return 0  -- 表示超限
    end
    return 1  -- 表示成功
    """
    result = redis_client.eval(
        lua_script,
        1,
        bet_key,
        str(amount),
        str(MAX_TOTAL_BET)
    )

    if result == 0:
        raise BetLimitExceededError(
            f"本局 {bet_side} 下注已達上限 {MAX_TOTAL_BET}"
        )

    # Redis 計數成功，寫入 DB
    async with transaction.atomic():
        # 最後一道防線：DB 層也做校驗
        await validate_game_round_accepting_bets(game_round_id)

        bet = await Bet.objects.acreate(
            game_round_id=game_round_id,
            user_id=user_id,
            bet_side=bet_side,
            amount=amount,
            status='CONFIRMED'
        )

        # 同步扣除用戶點數
        success = await deduct_points(user_id, amount)
        if not success:
            # 點數不足，回滾 Redis 計數
            redis_client.incrbyfloat(bet_key, -float(amount))
            raise InsufficientPointsError()

    return {"bet_id": str(bet.id), "status": "confirmed"}
```

**反哺規則：**
```
RULE-BET-001: 下注上限校驗必須使用 Redis 原子操作或 DB 行鎖。
  - 觸發條件: place_bet 函式使用讀取後比較的模式
  - 掃描模式: current_total.*amount.*MAX|if.*total.*>.*MAX
  - 嚴重度: HIGH
```

---

### PAT-BET-002：遊戲狀態機違規轉換

**描述：**
遊戲局有明確的狀態機：WAITING → BETTING → DEALING → SETTLED。若未正確實作狀態機，可能在遊戲已進入 DEALING 或 SETTLED 後仍接受新下注，或在 BETTING 期間就觸發結算。

**觸發特徵：**

```python
# 錯誤：無狀態機保護的下注
async def place_bet(game_round_id: str, amount: Decimal):
    game = await GameRound.objects.aget(id=game_round_id)
    # 沒有檢查 game.status！
    await Bet.objects.acreate(game_round_id=game_round_id, amount=amount)

# 錯誤：非原子的狀態轉換
async def start_dealing(game_round_id: str):
    game = await GameRound.objects.aget(id=game_round_id)
    if game.status == 'BETTING':
        game.status = 'DEALING'  # 非原子，並發時可能重複執行
        await game.asave()
```

**危害等級：** P1 HIGH

**修復策略：**

```python
from enum import Enum

class GameRoundStatus(str, Enum):
    WAITING = 'WAITING'       # 等待開始
    BETTING = 'BETTING'       # 接受下注
    DEALING = 'DEALING'       # 發牌中（不接受下注）
    SETTLED = 'SETTLED'       # 已結算
    CANCELLED = 'CANCELLED'   # 已取消

# 合法的狀態轉換
VALID_TRANSITIONS = {
    GameRoundStatus.WAITING:  {GameRoundStatus.BETTING, GameRoundStatus.CANCELLED},
    GameRoundStatus.BETTING:  {GameRoundStatus.DEALING, GameRoundStatus.CANCELLED},
    GameRoundStatus.DEALING:  {GameRoundStatus.SETTLED, GameRoundStatus.CANCELLED},
    GameRoundStatus.SETTLED:  set(),   # 終態
    GameRoundStatus.CANCELLED: set(),  # 終態
}

async def transition_game_status(
    game_round_id: str,
    new_status: GameRoundStatus
) -> bool:
    """原子狀態機轉換（使用 CAS：Compare-And-Swap）"""
    # 取得當前合法的前置狀態
    valid_from_statuses = [
        status for status, targets in VALID_TRANSITIONS.items()
        if new_status in targets
    ]

    if not valid_from_statuses:
        raise InvalidStatusTransitionError(f"無法轉換到 {new_status}")

    # 原子 CAS 更新（只有在狀態符合預期時才更新）
    updated = await GameRound.objects.filter(
        id=game_round_id,
        status__in=valid_from_statuses  # 只有合法前置狀態才能轉換
    ).aupdate(
        status=new_status,
        updated_at=timezone.now()
    )

    return updated > 0  # True 表示轉換成功


async def place_bet(game_round_id: str, user_id: int, amount: Decimal):
    """只有 BETTING 狀態才能下注"""
    game = await GameRound.objects.aget(
        id=game_round_id,
        status=GameRoundStatus.BETTING  # 狀態機守衛
    )
    # ... 後續下注邏輯
```

**反哺規則：**
```
RULE-BET-002: 遊戲狀態轉換必須使用 CAS 原子操作，下注前必須驗證狀態。
  - 觸發條件: place_bet 無 status=BETTING 過濾
  - 嚴重度: HIGH
```

---

### PAT-RESULT-001：結算結果竄改（直播 overlay 注入）

**描述：**
WebSocket 廣播的遊戲結果消息未做簽章保護，中間人或惡意前端可偽造結果消息，使部分玩家看到與實際不同的結果，引發詐騙糾紛。

**觸發特徵：**

```python
# 後端：廣播結果未簽章
async def broadcast_game_result(game_round_id: str, result: dict):
    await websocket_manager.broadcast(
        room_id=result['room_id'],
        message={
            "type": "game_result",
            "round_id": game_round_id,
            "dragon_card": result['dragon_card'],
            "tiger_card": result['tiger_card'],
            "winner": result['winner']
            # 無簽章！可被偽造
        }
    )
```

```javascript
// 前端：直接信任 WebSocket 結果消息
ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.type === 'game_result') {
        displayResult(msg.winner);  // 直接顯示，未驗簽
        if (msg.winner === myBetSide) {
            showWinAnimation();
        }
    }
};
```

**危害等級：** P1 HIGH

**修復策略：**

```python
import hmac
import hashlib
import json

WEBSOCKET_SIGNING_KEY = os.environ['WEBSOCKET_SIGNING_KEY']  # 從環境變數取得

def sign_game_result(payload: dict) -> str:
    """對遊戲結果簽章"""
    # 只對核心欄位簽章，避免欄位順序問題
    canonical = json.dumps({
        "round_id": payload['round_id'],
        "dragon_card": payload['dragon_card'],
        "tiger_card": payload['tiger_card'],
        "winner": payload['winner'],
        "timestamp": payload['timestamp']
    }, sort_keys=True)

    return hmac.new(
        WEBSOCKET_SIGNING_KEY.encode(),
        canonical.encode(),
        hashlib.sha256
    ).hexdigest()

async def broadcast_game_result(game_round_id: str, result: dict):
    import time
    payload = {
        "type": "game_result",
        "round_id": game_round_id,
        "dragon_card": result['dragon_card'],
        "tiger_card": result['tiger_card'],
        "winner": result['winner'],
        "timestamp": int(time.time())
    }
    payload['signature'] = sign_game_result(payload)
    await websocket_manager.broadcast(room_id=result['room_id'], message=payload)
```

```javascript
// 前端驗簽（使用 Web Crypto API）
async function verifyGameResult(msg) {
    const { signature, ...payload } = msg;

    const canonical = JSON.stringify({
        round_id: payload.round_id,
        dragon_card: payload.dragon_card,
        tiger_card: payload.tiger_card,
        winner: payload.winner,
        timestamp: payload.timestamp
    }, Object.keys(payload).sort());

    // 驗簽（需要後端提供公開的 HMAC key，或使用非對稱加密）
    const isValid = await verifyHMAC(canonical, signature, WS_VERIFY_KEY);
    if (!isValid) {
        console.error('遊戲結果簽章驗證失敗，可能遭受攻擊');
        reportSecurityIncident(msg);
        return false;
    }
    return true;
}
```

**反哺規則：**
```
RULE-RESULT-001: WebSocket 遊戲結果消息必須包含服務端簽章。
  - 觸發條件: broadcast 函式發送含 winner/result 的消息無 signature 欄位
  - 嚴重度: HIGH
```

---

### PAT-RESULT-002：結算超時未處理

**描述：**
博弈遊戲依賴外部行情 API（如撲克牌亂數服務、第三方 RNG 服務）。當外部 API 超時時，若代碼靜默返回預設值（如 0 或空字串），將導致以預設值錯誤結算。

**觸發特徵：**

```python
# 錯誤：超時時靜默返回預設值
async def fetch_game_result_from_provider(round_id: str) -> dict:
    try:
        async with aiohttp.ClientSession() as session:
            response = await asyncio.wait_for(
                session.get(f"{RNG_PROVIDER_URL}/result/{round_id}"),
                timeout=5.0
            )
            return await response.json()
    except asyncio.TimeoutError:
        # 危險：靜默返回預設值，用預設值結算！
        return {"winner": "dragon", "card_value": 0}
    except Exception:
        return {}  # 更危險：空字典，後續 KeyError 被吞掉
```

**危害等級：** P1 HIGH

**修復策略：**

```python
import asyncio
import aiohttp
from tenacity import retry, stop_after_attempt, wait_exponential

class GameResultFetchError(Exception):
    """外部 RNG 服務不可用，不應以預設值結算"""
    pass

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10)
)
async def fetch_game_result_from_provider(round_id: str) -> dict:
    """
    從外部 RNG 提供者獲取遊戲結果。
    重試 3 次後仍失敗則拋出例外，絕不返回預設值。
    """
    try:
        async with aiohttp.ClientSession() as session:
            response = await asyncio.wait_for(
                session.get(f"{RNG_PROVIDER_URL}/result/{round_id}"),
                timeout=5.0
            )
            response.raise_for_status()
            data = await response.json()

            # 驗證必填欄位
            required_fields = {'winner', 'dragon_card', 'tiger_card'}
            if not required_fields.issubset(data.keys()):
                raise GameResultFetchError(
                    f"外部 API 回應缺少必填欄位：{required_fields - data.keys()}"
                )
            return data

    except asyncio.TimeoutError:
        raise GameResultFetchError(f"外部 RNG 服務超時，round_id={round_id}")
    except aiohttp.ClientError as e:
        raise GameResultFetchError(f"外部 RNG 服務連線錯誤：{e}")


async def settle_game_round(round_id: str):
    try:
        result = await fetch_game_result_from_provider(round_id)
    except GameResultFetchError as e:
        # 超時時掛起結算，人工介入，絕不用預設值結算
        await GameRound.objects.filter(id=round_id).aupdate(
            status='SETTLEMENT_FAILED',
            error_message=str(e)
        )
        # 發送告警
        await send_alert(
            level='CRITICAL',
            message=f"博弈結算失敗，需人工介入：{e}",
            round_id=round_id
        )
        raise
```

**反哺規則：**
```
RULE-RESULT-002: 外部 RNG 服務超時必須拋出例外，禁止返回預設值繼續結算。
  - 觸發條件: except TimeoutError 中含有 return {} 或 return {"winner":
  - 嚴重度: HIGH
```

---

## 4. 博弈遊戲 QA 測試矩陣

### 4.1 Robot Framework 測試案例清單

```robot
*** Settings ***
Library    RequestsLibrary
Library    Collections
Library    DatabaseLibrary
Resource   ../resources/gambling_keywords.robot

*** Variables ***
${BASE_URL}    https://staging-api.swag.live
${GAME_API}    ${BASE_URL}/api/v1/games

*** Test Cases ***

# ---- RNG 公正性測試 ----

GAM-TC-001 龍虎鬥結果分布統計測試
    [Tags]    rng    fairness    smoke
    [Documentation]    模擬 10000 局，驗證龍/虎/平局比例符合理論值
    ${results}=    Run Game Simulation    game_type=dragon_tiger    rounds=10000
    ${dragon_rate}=    Calculate Rate    ${results}    dragon
    ${tiger_rate}=    Calculate Rate    ${results}    tiger
    ${tie_rate}=    Calculate Rate    ${results}    tie
    Should Be Within Range    ${dragon_rate}    0.44    0.47    # 理論值 45.86%
    Should Be Within Range    ${tiger_rate}    0.44    0.47
    Should Be Within Range    ${tie_rate}    0.07    0.09    # 理論值 7.69%

GAM-TC-002 百家樂結果分布測試
    [Tags]    rng    fairness
    ${results}=    Run Game Simulation    game_type=baccarat    rounds=10000
    ${banker_rate}=    Calculate Rate    ${results}    banker
    ${player_rate}=    Calculate Rate    ${results}    player
    Should Be Within Range    ${banker_rate}    0.50    0.52    # 理論值 50.68%
    Should Be Within Range    ${player_rate}    0.48    0.50    # 理論值 49.32%

# ---- 賠率計算測試 ----

GAM-TC-010 百家樂莊家賠率含5%佣金
    [Tags]    odds    critical
    ${bet_amount}=    Set Variable    1000
    ${result}=    Place Bet And Settle    game_type=baccarat    side=banker
    ...    amount=${bet_amount}    force_result=banker
    Should Be Equal As Integers    ${result['payout']}    1950    # 1000本金 + 950淨利

GAM-TC-011 百家樂和局閒家退本金
    [Tags]    odds    tie
    ${result}=    Place Bet And Settle    game_type=baccarat    side=player
    ...    amount=500    force_result=tie
    Should Be Equal As Integers    ${result['payout']}    500    # 退本金

GAM-TC-012 龍虎鬥平局押龍退50%
    [Tags]    odds    tie    critical
    ${result}=    Place Bet And Settle    game_type=dragon_tiger    side=dragon
    ...    amount=1000    force_result=tie
    Should Be Equal As Integers    ${result['payout']}    500    # 退50%

GAM-TC-013 龍虎鬥押平局贏得8倍
    [Tags]    odds    tie
    ${result}=    Place Bet And Settle    game_type=dragon_tiger    side=tie
    ...    amount=100    force_result=tie
    Should Be Equal As Integers    ${result['payout']}    900    # 8:1純利+本金=9倍

# ---- 並發安全測試 ----

GAM-TC-020 並發下注不超過單局上限
    [Tags]    concurrency    bet_limit
    ${round_id}=    Create New Game Round    game_type=dragon_tiger
    Run Concurrent Bets    round_id=${round_id}    count=50    amount=30000
    ${total}=    Get Round Total Bet    ${round_id}
    Should Be Less Than Or Equal    ${total}    1000000    # 最大下注限制

GAM-TC-021 並發結算不觸發雙重賠付
    [Tags]    concurrency    settlement    critical
    ${round_id}=    Create Game With Bets    game_type=dragon_tiger
    # 同時觸發 5 個結算請求
    Run Parallel Settlement    round_id=${round_id}    worker_count=5
    ${settlement_count}=    Count Settlement Records    ${round_id}
    Should Be Equal As Integers    ${settlement_count}    1    # 只結算一次

# ---- 狀態機測試 ----

GAM-TC-030 DEALING狀態不接受下注
    [Tags]    state_machine    negative
    ${round_id}=    Create Game Round In Status    status=DEALING
    ${response}=    Attempt Place Bet    round_id=${round_id}    amount=100
    Should Be Equal As Strings    ${response['error']}    GAME_NOT_ACCEPTING_BETS

GAM-TC-031 SETTLED狀態不接受結算請求
    [Tags]    state_machine    idempotency
    ${round_id}=    Create Settled Game Round
    ${response}=    Attempt Settle    round_id=${round_id}
    Should Be Equal As Strings    ${response['status']}    already_settled

# ---- 邊界測試 ----

GAM-TC-040 下注金額為零拒絕
    [Tags]    boundary    negative
    ${response}=    Attempt Place Bet    amount=0
    Should Be Equal As Strings    ${response['error']}    INVALID_BET_AMOUNT

GAM-TC-041 下注金額超過個人上限
    [Tags]    boundary    negative
    ${response}=    Attempt Place Bet    amount=999999999
    Should Be Equal As Strings    ${response['error']}    BET_EXCEEDS_PERSONAL_LIMIT

GAM-TC-042 餘額不足下注
    [Tags]    boundary    negative
    Set User Points    ${TEST_USER}    10    # 只有10點
    ${response}=    Attempt Place Bet    amount=100    # 嘗試下100
    Should Be Equal As Strings    ${response['error']}    INSUFFICIENT_POINTS
```

---

## 5. 博弈遊戲不變量列表

| ID | 不變量描述 | 驗證方式 | 違反嚴重度 |
|----|-----------|---------|-----------|
| INV-GAM-001 | 每局遊戲只生成一次隨機結果，且由服務端 secrets 模組生成 | 代碼審查 + 審計日誌 | P0 CRITICAL |
| INV-GAM-002 | 遊戲結果在 BETTING 期間加密儲存，不對外公開 | 滲透測試 | P0 CRITICAL |
| INV-GAM-003 | 每局遊戲只能結算一次，狀態機終態不可逆 | 自動化測試 GAM-TC-031 | P0 CRITICAL |
| INV-GAM-004 | 所有賠率計算使用 Decimal，精確到分 | 單元測試 | P1 HIGH |
| INV-GAM-005 | 總賠付金額不超過 MAX_SINGLE_PAYOUT | 業務守衛 | P1 HIGH |
| INV-GAM-006 | 結算前必須驗證遊戲狀態為 DEALING | 自動化測試 GAM-TC-030 | P1 HIGH |
| INV-GAM-007 | 玩家下注時必須實時鎖定對應點數 | 自動化測試 GAM-TC-042 | P1 HIGH |
| INV-GAM-008 | 下注期間截止後不允許新增或修改下注 | 自動化測試 GAM-TC-030 | P1 HIGH |
| INV-GAM-009 | WebSocket 廣播的結果消息必須含有效簽章 | 安全審查 | P1 HIGH |
| INV-GAM-010 | 外部 RNG 服務不可用時必須掛起結算，不得用預設值 | 故障注入測試 | P1 HIGH |

---

## 版本歷程

| 版本 | 日期 | 說明 |
|------|------|------|
| 1.0.0 | 2026-06-05 | 初版，涵蓋龍虎鬥、百家樂完整 Bug Pattern 與測試矩陣 |
