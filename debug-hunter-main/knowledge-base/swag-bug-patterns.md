# SWAG 主要 Bug 模式知識庫
# swag-bug-patterns.md
# 版本：1.0.0 | 維護團隊：SWAG QA 部門
# 適用範圍：點數/分系統、打賞、訂閱、博弈遊戲、金流支付

---

## 概述

本知識庫彙整 SWAG 平台（swag.live）各核心業務模組的已知 Bug 模式，供 QA 工程師在測試、代碼審查與事故分析時快速比對。每個 Pattern 包含觸發特徵、危害等級、修復策略與反哺規則。

**業務範圍：**
- 點數/分系統（購買、打賞、訂閱、退款）
- 博弈遊戲（龍虎鬥、百家樂）
- 金流支付（綠界 ECPay、91app、支付寶、微信支付）
- API 買分後台
- Robot Framework / Playwright / Appium 自動化測試

**危害等級定義：**

| 等級 | 標籤 | 說明 |
|------|------|------|
| P0 | CRITICAL | 直接財務損失、資安漏洞，必須當天修復 |
| P1 | HIGH | 功能嚴重異常，影響用戶核心流程，24 小時內修復 |
| P2 | MEDIUM | 功能部分異常，有 workaround，72 小時內修復 |
| P3 | LOW | 體驗問題或邊界案例，排期修復 |

---

## 模組一：點數系統（CRED）

### PAT-CRED-001：Python Decimal 精度問題（點數計算）

**描述：**
使用 Python 原生 `float` 進行點數計算，導致浮點精度誤差累積。在高頻打賞或批量訂閱場景下，累積誤差可能導致用戶帳戶點數與實際扣款金額不符。

**觸發特徵：**

```python
# 錯誤：使用 float 計算點數
def calculate_points(purchase_amount: float, exchange_rate: float) -> float:
    points = float(purchase_amount) * exchange_rate
    return points

# 典型觸發場景
points = float(99.9) * 10.1  # 結果：1008.9899999999999（非預期 1008.99）

# 另一種常見錯誤：累積計算
total_deduction = 0.0
for gift in gifts:
    total_deduction += float(gift['points'])  # 每次都在累積誤差
```

**危害等級：** P1 HIGH

**危害說明：**
- 用戶餘額顯示不準確
- 批量結算時累積誤差可能達數十點
- 財務對帳時數字無法平衡
- 法規合規風險（台灣電子遊戲場業管理條例）

**修復策略：**

```python
from decimal import Decimal, ROUND_HALF_DOWN, ROUND_HALF_UP
from typing import Union

# 正確：使用 Decimal 進行點數計算
def calculate_points(
    purchase_amount: Union[str, int, Decimal],
    exchange_rate: Union[str, Decimal]
) -> Decimal:
    """
    計算購買點數。
    重要：所有輸入必須先轉為 str 再轉 Decimal，避免 float 引入誤差。
    """
    amount = Decimal(str(purchase_amount))
    rate = Decimal(str(exchange_rate))
    points = amount * rate
    # 點數無條件捨去小數（對平台有利）
    return points.quantize(Decimal('1'), rounding=ROUND_HALF_DOWN)


# 正確：累積計算
def calculate_total_deduction(gifts: list) -> Decimal:
    total = Decimal('0')
    for gift in gifts:
        total += Decimal(str(gift['points']))
    return total


# Django model 層設定
class UserWallet(models.Model):
    # 使用 DecimalField，精度設定：最多 12 位整數，2 位小數
    points = models.DecimalField(max_digits=14, decimal_places=2, default=Decimal('0'))
```

**反哺規則：**
```
RULE-CRED-001: 所有點數計算必須使用 Decimal，禁止 float。
  - 觸發條件: 偵測到 float() 用於金額或點數變數
  - 掃描模式: `float\s*\([^)]*(?:amount|point|price|fee|rate)[^)]*\)`
  - 嚴重度: HIGH
  - 自動修復: 將 float() 替換為 Decimal(str())
```

---

### PAT-CRED-002：點數重複充值（冪等性缺失）

**描述：**
支付平台回調（callback）在網路不穩定時會重複觸發，若後端未實作冪等保護，同一筆支付訂單將造成點數重複充值。

**觸發特徵：**

```python
# 錯誤：無冪等保護的支付回調處理器
@router.post("/payment/callback/ecpay")
async def ecpay_callback(request: Request):
    data = await request.json()
    order_id = data['MerchantTradeNo']
    amount = data['TradeAmt']

    # 直接充值，無任何冪等保護
    order = await Order.objects.get(id=order_id)
    user = await User.objects.get(id=order.user_id)
    user.points += amount * EXCHANGE_RATE  # 危險：可能重複執行
    await user.save()
    return {"status": "success"}
```

**危害等級：** P0 CRITICAL

**危害說明：**
- 直接造成平台財務損失（點數白給）
- 難以事後追溯（需對帳所有重複回調）
- 支付寶、微信支付設計上就會重複發送直到收到成功回應

**修復策略：**

```python
import redis
from django.db import transaction

redis_client = redis.Redis(host='redis-host', port=6379, db=0)

@router.post("/payment/callback/ecpay")
async def ecpay_callback(request: Request):
    data = await request.json()
    order_id = data['MerchantTradeNo']
    payment_id = data['TradeNo']  # 支付平台的交易流水號

    # 第一道防線：Redis 冪等鍵（TTL 24 小時）
    idempotency_key = f"payment:callback:{payment_id}"
    is_new = redis_client.set(idempotency_key, "processing", nx=True, ex=86400)

    if not is_new:
        # 已處理過，直接回傳成功（避免支付平台繼續重試）
        return {"status": "success", "message": "already_processed"}

    try:
        async with transaction.atomic():
            # 第二道防線：DB 狀態機（訂單狀態只能從 PENDING 轉為 PAID）
            updated = await Order.objects.filter(
                id=order_id,
                status='PENDING'  # 只有待付款訂單才能轉換
            ).aupdate(
                status='PAID',
                paid_at=timezone.now(),
                payment_reference=payment_id
            )

            if updated == 0:
                # 訂單已是 PAID 或不存在，屬於重複回調
                redis_client.set(idempotency_key, "duplicate", ex=86400)
                return {"status": "success", "message": "order_already_paid"}

            # 充值點數（使用 F() 表達式，見 PAT-CRED-003）
            order = await Order.objects.aget(id=order_id)
            await UserWallet.objects.filter(user_id=order.user_id).aupdate(
                points=F('points') + order.points_to_add
            )

        redis_client.set(idempotency_key, "completed", ex=86400)
        return {"status": "success"}

    except Exception as e:
        # 處理失敗，刪除冪等鍵允許重試
        redis_client.delete(idempotency_key)
        raise
```

**反哺規則：**
```
RULE-CRED-002: 所有支付回調處理器必須實作冪等保護。
  - 觸發條件: 偵測到 @router.post 包含 "callback" 且無 redis setex/set nx 呼叫
  - 掃描模式: def.*callback.*\n(?:(?!redis)[\s\S]){0,20}user\.points
  - 嚴重度: CRITICAL
```

---

### PAT-CRED-003：點數餘額並發覆蓋（競態條件）

**描述：**
多個並發請求同時讀取用戶餘額後各自修改，後者的寫入覆蓋前者，導致點數實際扣減量少於預期（Lost Update 問題）。

**觸發特徵：**

```python
# 錯誤：讀取-修改-寫入模式（Read-Modify-Write）
async def deduct_points_for_gift(user_id: int, gift_cost: int):
    user = await User.objects.aget(id=user_id)  # T1: 讀取 balance=1000
    # --- 此處 T2 也讀取到 balance=1000 ---
    user.points = user.points - gift_cost  # T1: 1000 - 50 = 950
    await user.save()  # T1: 寫入 950
    # T2 也寫入 1000 - 80 = 920
    # 最終 balance=920，但實際應扣 130（50+80），正確餘額應為 870
```

**危害等級：** P0 CRITICAL

**危害說明：**
- 用戶可用超出實際餘額的點數
- 直播間高頻打賞場景下必現（多人同時送禮）
- 財務漏洞，難以事後追溯

**修復策略：**

```python
from django.db.models import F
from django.db import transaction

# 方案一：Django F() 表達式（推薦，無需加鎖）
async def deduct_points_for_gift(user_id: int, gift_cost: Decimal) -> bool:
    """
    使用 F() 表達式原子扣減點數。
    F() 在資料庫層執行 UPDATE ... SET points = points - %s WHERE points >= %s
    """
    updated = await UserWallet.objects.filter(
        user_id=user_id,
        points__gte=gift_cost  # 同時校驗餘額充足（見 PAT-CRED-004）
    ).aupdate(
        points=F('points') - gift_cost
    )
    return updated > 0  # True 表示扣減成功，False 表示餘額不足


# 方案二：SELECT FOR UPDATE（需要完整交易保護）
async def deduct_points_with_lock(user_id: int, gift_cost: Decimal) -> bool:
    async with transaction.atomic():
        try:
            wallet = await UserWallet.objects.select_for_update().aget(
                user_id=user_id
            )
            if wallet.points < gift_cost:
                return False
            wallet.points -= gift_cost
            await wallet.asave(update_fields=['points'])
            return True
        except UserWallet.DoesNotExist:
            return False
```

**反哺規則：**
```
RULE-CRED-003: 禁止在不使用 F() 或 select_for_update() 的情況下修改點數餘額。
  - 觸發條件: user.points = user.points +/- 且無 F() 包裝
  - 掃描模式: \.points\s*=\s*\w+\.points\s*[+-]
  - 嚴重度: CRITICAL
```

---

### PAT-CRED-004：負點數允許（邊界缺失）

**描述：**
扣減點數時未校驗當前餘額是否充足，允許點數變為負數。惡意用戶可持續消費至負數餘額，造成平台損失。

**觸發特徵：**

```python
# 錯誤：直接扣減無餘額校驗
async def spend_points(user_id: int, amount: int):
    await UserWallet.objects.filter(user_id=user_id).aupdate(
        points=F('points') - amount  # 沒有 points__gte=amount 條件！
    )
    # 如果 points=10 而 amount=100，結果 points=-90

# 另一種錯誤：應用層校驗但有 TOCTOU 漏洞
async def spend_points_unsafe(user_id: int, amount: int):
    wallet = await UserWallet.objects.aget(user_id=user_id)
    if wallet.points < amount:  # 校驗時點數足夠
        raise InsufficientPointsError()
    # --- 並發請求在此插入，也通過了校驗 ---
    wallet.points -= amount  # 兩個請求都執行到這裡
    await wallet.asave()
```

**危害等級：** P0 CRITICAL

**危害說明：**
- 用戶可以無限透支點數
- 結合並發攻擊可放大損失
- 系統最終需要手動沖正大量帳目

**修復策略：**

```python
from django.db.models import F

# 正確：原子 SQL 含餘額校驗
async def spend_points(user_id: int, amount: Decimal) -> bool:
    """
    原子扣減點數，同時校驗餘額充足。
    等效 SQL: UPDATE wallet SET points = points - amount
              WHERE user_id = %s AND points >= amount
    """
    if amount <= 0:
        raise ValueError(f"扣減點數必須為正數，收到: {amount}")

    updated_rows = await UserWallet.objects.filter(
        user_id=user_id,
        points__gte=amount  # 關鍵：確保餘額充足才扣減
    ).aupdate(
        points=F('points') - amount
    )

    if updated_rows == 0:
        # 可能是用戶不存在或餘額不足，需區分
        wallet = await UserWallet.objects.filter(user_id=user_id).afirst()
        if wallet is None:
            raise UserNotFoundError(f"用戶 {user_id} 錢包不存在")
        raise InsufficientPointsError(
            f"點數不足：需要 {amount}，現有 {wallet.points}"
        )

    return True


# DB 層防護（Django migration）
class UserWallet(models.Model):
    points = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0'),
        validators=[MinValueValidator(Decimal('0'))]  # 應用層校驗
    )

    class Meta:
        constraints = [
            # 資料庫層約束，最後一道防線
            models.CheckConstraint(
                check=models.Q(points__gte=0),
                name='wallet_points_non_negative'
            )
        ]
```

**反哺規則：**
```
RULE-CRED-004: F() 扣減點數時必須加上 points__gte 條件。
  - 觸發條件: F('points') - 且無 points__gte
  - 嚴重度: CRITICAL
```

---

## 模組二：博弈遊戲（GAM）

### PAT-GAM-001：博弈 RNG 種子可預測

**描述：**
使用 Python 標準庫 `random` 模組（Mersenne Twister 算法）作為博弈遊戲的隨機數來源。MT 是偽隨機數生成器，在連續觀察 624 個 32-bit 輸出後可完全重建內部狀態，進而預測所有後續結果。

**觸發特徵：**

```python
import random

# 錯誤：使用 random 模組
def determine_game_result() -> str:
    result = random.choice(['龍', '虎', '平局'])
    return result

def shuffle_deck() -> list:
    deck = list(range(52))
    random.shuffle(deck)  # 可被預測
    return deck

# 更危險的模式：使用固定種子（測試程式碼流入正式環境）
random.seed(12345)
result = random.random()
```

**危害等級：** P0 CRITICAL

**危害說明：**
- 玩家可透過統計分析預測遊戲結果
- 平台面臨被「算牌」攻擊的風險
- 涉及博弈公正性法規合規問題

**修復策略：**

```python
import secrets
import os

# 正確：使用密碼學安全的隨機數
def determine_game_result() -> str:
    outcomes = ['龍', '虎', '平局']
    result = secrets.choice(outcomes)
    return result

def shuffle_deck() -> list:
    deck = list(range(52))
    # secrets 模組沒有 shuffle，使用 Fisher-Yates with secrets
    for i in range(len(deck) - 1, 0, -1):
        j = secrets.randbelow(i + 1)
        deck[i], deck[j] = deck[j], deck[i]
    return deck

# 需要浮點數時
def secure_random_float() -> float:
    """生成 [0.0, 1.0) 的密碼學安全浮點數"""
    return int.from_bytes(os.urandom(8), 'big') / (2**64)
```

**反哺規則：**
```
RULE-GAM-001: 博弈相關代碼禁止使用 random 模組。
  - 觸發條件: import random 出現在 game/ gambling/ 目錄下
  - 掃描模式: ^import random|^from random import
  - 嚴重度: CRITICAL
  - 例外: 測試代碼（test_*.py）中用於 mock
```

---

### PAT-GAM-002：賠率計算浮點誤差

**描述：**
使用 Python float 計算賠付金額，在乘以賠率時產生精度損失，導致玩家實際獲得的點數與理論值有偏差。

**觸發特徵：**

```python
# 錯誤：float 賠率計算
def calculate_payout(bet_amount: float, odds: float) -> float:
    payout = bet_amount * odds  # float 乘法，精度損失
    return payout

# 典型案例：百家樂賠率
bet = 1000
payout = bet * 1.95  # 結果：1950.0000000000002（非預期 1950）

# 龍虎鬥賠率
payout = 500 * 0.95  # 結果：475.00000000000006
```

**危害等級：** P1 HIGH

**危害說明：**
- 玩家賠付金額與顯示值不一致，引發客訴
- 大量交易累積後財務對帳出現差異
- 監管審計時無法核對帳目

**修復策略：**

```python
from decimal import Decimal, ROUND_HALF_DOWN

# 賠率常數定義（使用字串初始化避免 float 誤差）
BACCARAT_PLAYER_ODDS = Decimal('1.0')    # 閒家 1:1
BACCARAT_BANKER_ODDS = Decimal('0.95')  # 莊家 1:1 扣 5% 佣金
BACCARAT_TIE_ODDS = Decimal('8.0')      # 平局 8:1
DRAGON_TIGER_ODDS = Decimal('1.0')      # 龍/虎 1:1
DRAGON_TIGER_TIE_ODDS = Decimal('8.0')  # 平局 8:1

def calculate_payout(bet_amount: Decimal, odds: Decimal) -> Decimal:
    """
    計算賠付金額。
    賠付 = 下注金額 * 賠率（含本金）
    點數取整，採用 ROUND_HALF_DOWN
    """
    payout = Decimal(str(bet_amount)) * odds
    return payout.quantize(Decimal('1'), rounding=ROUND_HALF_DOWN)

# 使用範例
bet = Decimal('1000')
payout = calculate_payout(bet, BACCARAT_BANKER_ODDS)  # 準確結果：950
```

**反哢規則：**
```
RULE-GAM-002: 賠率計算必須使用 Decimal，賠率常數必須用字串初始化。
  - 觸發條件: 偵測到 float * odds 或 bet_amount * float_literal
  - 嚴重度: HIGH
```

---

### PAT-GAM-003：博弈結果並發競態（雙重結算）

**描述：**
Celery worker 或多個服務實例同時處理同一局博弈的結算任務，導致同一局遊戲被結算兩次，玩家獲得雙倍賠付。

**觸發特徵：**

```python
# 錯誤：無分散式鎖保護的結算任務
@celery_app.task
def settle_game(game_round_id: str):
    game = GameRound.objects.get(id=game_round_id)
    # --- 兩個 worker 同時執行到這裡 ---
    if game.status == 'PENDING_SETTLEMENT':
        # 兩個 worker 都通過了這個檢查
        results = calculate_all_payouts(game)
        for result in results:
            pay_winner(result)  # 雙重賠付！
        game.status = 'SETTLED'
        game.save()
```

**危害等級：** P0 CRITICAL

**危害說明：**
- 直接財務損失（玩家獲得雙倍賠付）
- 在 Celery 高並發場景下必現
- 事後沖正複雜，用戶體驗差

**修復策略：**

```python
import redis
from contextlib import contextmanager

redis_client = redis.Redis(host='redis-host', port=6379, db=0)

@contextmanager
def distributed_lock(lock_name: str, timeout: int = 30):
    """分散式鎖上下文管理器"""
    lock_key = f"lock:{lock_name}"
    lock_acquired = redis_client.set(lock_key, "1", nx=True, ex=timeout)
    try:
        if not lock_acquired:
            raise LockAcquisitionError(f"無法獲取鎖：{lock_name}")
        yield
    finally:
        if lock_acquired:
            redis_client.delete(lock_key)

@celery_app.task(bind=True, max_retries=3)
def settle_game(self, game_round_id: str):
    lock_name = f"game:settle:{game_round_id}"

    try:
        with distributed_lock(lock_name, timeout=60):
            with transaction.atomic():
                # 使用 select_for_update 確保同一時間只有一個事務處理
                game = GameRound.objects.select_for_update().get(
                    id=game_round_id,
                    status='PENDING_SETTLEMENT'  # 狀態過濾，冪等保護
                )
                results = calculate_all_payouts(game)
                for result in results:
                    pay_winner(result)
                game.status = 'SETTLED'
                game.settled_at = timezone.now()
                game.save()

    except GameRound.DoesNotExist:
        # 已結算或不存在，忽略
        pass
    except LockAcquisitionError:
        # 另一個 worker 正在處理，稍後重試
        raise self.retry(countdown=5)
```

**反哺規則：**
```
RULE-GAM-003: 結算任務必須使用分散式鎖 + DB 冪等狀態保護。
  - 觸發條件: @celery_app.task 函式中包含 settle/payout/結算 且無 distributed_lock
  - 嚴重度: CRITICAL
```

---

### PAT-GAM-004：最大賠付限制缺失

**描述：**
單局博弈的賠付金額無上限，極端押注（如超大金額押注命中高賠率）可造成平台單局鉅額虧損。

**觸發特徵：**

```python
# 錯誤：計算賠付後直接入帳，無上限校驗
def pay_winner(user_id: int, payout_amount: Decimal):
    UserWallet.objects.filter(user_id=user_id).update(
        points=F('points') + payout_amount
        # 沒有上限檢查！
    )
```

**危害等級：** P1 HIGH

**危害說明：**
- 極端下注可造成平台單局損失超過風控閾值
- 可能被配合系統 bug 放大損失
- 缺乏業務合理性守衛

**修復策略：**

```python
from decimal import Decimal

# 業務常數（依實際業務規則設定）
MAX_SINGLE_BET = Decimal('50000')      # 單注上限：50,000 點
MAX_SINGLE_PAYOUT = Decimal('500000')  # 單局最大賠付：500,000 點
MAX_TIE_PAYOUT = Decimal('400000')     # 平局最大賠付（賠率高，上限更嚴）

def validate_and_pay_winner(
    user_id: int,
    payout_amount: Decimal,
    game_type: str,
    bet_type: str
) -> bool:
    """賠付前業務合理性守衛"""
    # 上限校驗
    limit = MAX_TIE_PAYOUT if bet_type == 'tie' else MAX_SINGLE_PAYOUT
    if payout_amount > limit:
        # 觸發人工審核，不自動賠付
        create_manual_review_ticket(
            user_id=user_id,
            payout_amount=payout_amount,
            reason=f"賠付金額 {payout_amount} 超過上限 {limit}"
        )
        raise PayoutExceedsLimitError(
            f"單局賠付 {payout_amount} 超過最大限制 {limit}"
        )

    # 正賠付
    UserWallet.objects.filter(user_id=user_id).update(
        points=F('points') + payout_amount
    )
    return True
```

**反哺規則：**
```
RULE-GAM-004: 賠付入帳前必須校驗最大賠付上限。
  - 觸發條件: pay_winner 或 payout 相關函式無 MAX_SINGLE_PAYOUT 校驗
  - 嚴重度: HIGH
```

---

## 模組三：支付金流（PAY）

### PAT-PAY-001：支付回調簽章未驗證

**描述：**
直接信任支付平台的回調請求，未驗證請求簽章。攻擊者只需知道回調 URL，即可偽造支付成功通知，免費獲得點數。

**觸發特徵：**

```python
# 錯誤：直接解析回調 JSON，無任何驗證
@router.post("/payment/callback/ecpay")
async def ecpay_callback(request: Request):
    data = await request.json()
    # 直接相信回調內容，危險！
    order_id = data['MerchantTradeNo']
    amount = data['TradeAmt']
    process_payment(order_id, amount)
```

**危害等級：** P0 CRITICAL

**修復策略：**

```python
import hashlib
import urllib.parse
from fastapi import Request, HTTPException

# 綠界 ECPay 簽章驗證
def verify_ecpay_signature(params: dict, hash_key: str, hash_iv: str) -> bool:
    """
    ECPay 簽章驗證：
    1. 移除 CheckMacValue
    2. 依參數名稱 ASCII 排序
    3. 拼接字串
    4. URL Encode 後轉小寫
    5. 前後加 HashKey/HashIV
    6. SHA256
    """
    received_mac = params.pop('CheckMacValue', None)
    if not received_mac:
        return False

    # 依 ASCII 排序
    sorted_params = sorted(params.items(), key=lambda x: x[0].lower())
    raw = '&'.join([f"{k}={v}" for k, v in sorted_params])
    raw = f"HashKey={hash_key}&{raw}&HashIV={hash_iv}"

    # URL Encode 後轉小寫
    encoded = urllib.parse.quote_plus(raw).lower()

    # SHA256
    computed = hashlib.sha256(encoded.encode('utf-8')).hexdigest().upper()
    return computed == received_mac.upper()


# 支付寶簽章驗證（RSA2）
from Crypto.Signature import pkcs1_15
from Crypto.Hash import SHA256
from Crypto.PublicKey import RSA
import base64

def verify_alipay_signature(params: dict, alipay_public_key: str) -> bool:
    """支付寶 RSA2 簽章驗證"""
    sign = params.pop('sign', None)
    params.pop('sign_type', None)
    if not sign:
        return False

    sorted_params = sorted(params.items())
    message = '&'.join([f"{k}={v}" for k, v in sorted_params if v])

    try:
        key = RSA.import_key(alipay_public_key)
        h = SHA256.new(message.encode('utf-8'))
        pkcs1_15.new(key).verify(h, base64.b64decode(sign))
        return True
    except (ValueError, TypeError):
        return False


# 微信支付簽章驗證
import hmac

def verify_wechat_signature(
    body: bytes,
    timestamp: str,
    nonce: str,
    signature: str,
    api_v3_key: str
) -> bool:
    """微信支付 V3 簽章驗證"""
    message = f"{timestamp}\n{nonce}\n{body.decode('utf-8')}\n"
    computed = hmac.new(
        api_v3_key.encode('utf-8'),
        message.encode('utf-8'),
        hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(computed, signature)
```

**反哺規則：**
```
RULE-PAY-001: 所有支付回調端點必須實作簽章驗證。
  - 觸發條件: @router.post 包含 callback/notify/ipn 無 verify_*_signature 呼叫
  - 嚴重度: CRITICAL
```

---

### PAT-PAY-002：回調金額未與訂單金額比對

**描述：**
即使通過了簽章驗證，回調中的金額仍可能與原始訂單不符（竄改或支付平台 bug）。若直接按回調金額充值，可能造成充入不符實際支付的點數。

**觸發特徵：**

```python
# 錯誤：只驗簽，不比對金額
async def process_payment_callback(data: dict):
    if not verify_signature(data):
        raise InvalidSignatureError()

    # 使用回調金額直接充值，危險！
    amount = Decimal(data['TradeAmt'])
    add_points_to_user(user_id, amount * EXCHANGE_RATE)
```

**危害等級：** P0 CRITICAL

**修復策略：**

```python
from decimal import Decimal

async def process_payment_callback(data: dict):
    # 第一道：驗簽
    if not verify_signature(data):
        raise InvalidSignatureError("簽章驗證失敗")

    order_id = data['MerchantTradeNo']
    callback_amount = Decimal(str(data['TradeAmt']))

    # 第二道：從資料庫取原始訂單金額
    order = await Order.objects.aget(id=order_id)

    # 比對金額（使用 Decimal 精確比較）
    if callback_amount != order.amount:
        raise InvalidPaymentError(
            f"金額不符：回調金額 {callback_amount}，"
            f"訂單金額 {order.amount}，訂單 ID: {order_id}"
        )

    # 使用訂單記錄的點數，而非回調中的金額換算
    await add_points_to_user(order.user_id, order.points_to_add)
```

**反哺規則：**
```
RULE-PAY-002: 回調處理必須比對回調金額與訂單金額。
  - 觸發條件: process_payment 中直接使用 data['TradeAmt'] 或 callback['amount'] 無比對
  - 嚴重度: CRITICAL
```

---

### PAT-PAY-003：支付回調重複處理

**描述：**
支付平台（尤其是支付寶、微信支付）在未收到成功回應時會持續重發回調。若後端未處理冪等性，將重複充值。

**觸發特徵：**

```python
# 錯誤：回調處理器無冪等保護
@router.post("/payment/notify/alipay")
async def alipay_notify(request: Request):
    data = await request.form()
    if not verify_alipay_signature(dict(data)):
        return "fail"

    out_trade_no = data['out_trade_no']
    trade_no = data['trade_no']  # 支付寶交易號

    # 直接充值，無冪等保護
    await process_payment(out_trade_no, data['total_amount'])
    return "success"  # 支付寶收到 success 才停止重試
```

**危害等級：** P0 CRITICAL

**修復策略：**

```python
@router.post("/payment/notify/alipay")
async def alipay_notify(request: Request):
    data = dict(await request.form())
    if not verify_alipay_signature(data):
        return "fail"

    trade_no = data['trade_no']  # 使用支付平台交易號作為冪等鍵
    idempotency_key = f"alipay:notify:{trade_no}"

    # Redis 冪等保護（TTL 72 小時，覆蓋支付寶重試窗口）
    is_new = redis_client.set(idempotency_key, "1", nx=True, ex=259200)
    if not is_new:
        return "success"  # 已處理，回傳 success 讓支付寶停止重試

    try:
        await process_payment_with_idempotency(
            order_id=data['out_trade_no'],
            payment_id=trade_no,
            amount=Decimal(data['total_amount'])
        )
        return "success"
    except Exception:
        redis_client.delete(idempotency_key)  # 失敗時允許重試
        return "fail"
```

**反哺規則：**
```
RULE-PAY-003: 所有支付通知端點必須使用交易流水號作為冪等鍵。
  - 觸發條件: /notify/ 或 /callback/ 端點無 redis setex/set nx 保護
  - 嚴重度: CRITICAL
```

---

## 模組四：直播功能（LIVE）

### PAT-LIVE-001：打賞/禮物送出重複扣款

**描述：**
WebSocket 連線不穩定時，前端的重試機制會重發打賞請求，若後端無冪等保護，同一筆打賞動作將重複扣款並重複給主播打賞計數。

**觸發特徵：**

```javascript
// 前端錯誤：重試時未帶冪等標識
async function sendGift(giftId, hostId) {
    try {
        await ws.send(JSON.stringify({
            type: 'send_gift',
            gift_id: giftId,
            host_id: hostId
            // 沒有唯一 request_id！
        }));
    } catch (e) {
        // 網路錯誤時直接重試，可能重複送出
        await sendGift(giftId, hostId);
    }
}
```

```python
# 後端錯誤：無冪等保護的打賞處理器
async def handle_send_gift(user_id: int, gift_id: int, host_id: int):
    gift = await Gift.objects.aget(id=gift_id)
    # 直接扣款，無冪等保護
    await deduct_points(user_id, gift.cost)
    await increment_host_earnings(host_id, gift.cost)
```

**危害等級：** P1 HIGH

**危害說明：**
- 用戶被多次扣款，引發大量客訴
- 主播收益計算不準確
- 在網路不穩定地區（部分東南亞市場）高頻觸發

**修復策略：**

```javascript
// 前端：每次打賞生成唯一 request_id
import { v4 as uuidv4 } from 'uuid';

async function sendGift(giftId, hostId) {
    const requestId = uuidv4();  // 每次操作產生唯一 ID
    const payload = {
        type: 'send_gift',
        gift_id: giftId,
        host_id: hostId,
        request_id: requestId  // 帶入冪等鍵
    };

    // 重試時使用相同 requestId
    for (let attempt = 0; attempt < 3; attempt++) {
        try {
            await ws.send(JSON.stringify(payload));
            return;
        } catch (e) {
            if (attempt === 2) throw e;
            await new Promise(r => setTimeout(r, 1000 * (attempt + 1)));
        }
    }
}
```

```python
# 後端：使用 request_id 冪等保護
async def handle_send_gift(
    user_id: int,
    gift_id: int,
    host_id: int,
    request_id: str  # 必填
):
    idempotency_key = f"gift:send:{user_id}:{request_id}"

    # TTL 5 分鐘（打賞操作的合理重試窗口）
    is_new = redis_client.set(idempotency_key, "1", nx=True, ex=300)
    if not is_new:
        return {"status": "already_sent"}

    try:
        async with transaction.atomic():
            gift = await Gift.objects.aget(id=gift_id)
            success = await deduct_points(user_id, gift.cost)
            if not success:
                raise InsufficientPointsError()
            await increment_host_earnings(host_id, gift.cost)
            await create_gift_record(user_id, host_id, gift_id, request_id)
        return {"status": "success"}
    except Exception:
        redis_client.delete(idempotency_key)
        raise
```

**反哺規則：**
```
RULE-LIVE-001: 打賞/送禮操作必須實作 request_id 冪等機制。
  - 觸發條件: WebSocket 打賞處理器無 request_id 參數
  - 嚴重度: HIGH
```

---

## 模組五：QA 測試（QA）

### PAT-QA-001：Robot Framework 測試資料未隔離

**描述：**
Robot Framework 測試腳本直接對正式環境資料庫操作，或使用與正式用戶相同的帳號進行測試，導致測試資料污染正式資料，或測試打賞/充值影響真實財務報表。

**觸發特徵：**

```robot
# 錯誤：測試直接使用正式帳號
*** Settings ***
Library    DatabaseLibrary

*** Variables ***
${DB_HOST}    production-db.swag.live  # 連到正式環境！
${TEST_USER}  real_user@example.com    # 使用真實用戶

*** Test Cases ***
測試打賞功能
    Connect To Database    pymysql    swag_prod    ${DB_HOST}
    # 直接在正式DB充值測試點數
    Execute Sql String    UPDATE wallets SET points=10000 WHERE email='${TEST_USER}'
```

**危害等級：** P1 HIGH

**危害說明：**
- 測試充值/扣款影響財務報表準確性
- 測試資料出現在正式報告中
- 誤刪/修改真實用戶資料
- 難以追溯測試造成的資料異常

**修復策略：**

```robot
# 正確：測試帳號隔離策略
*** Settings ***
Library    DatabaseLibrary
Library    Collections
Suite Setup      初始化測試環境
Suite Teardown   清理測試資料

*** Variables ***
${DB_HOST}        staging-db.swag.live   # 使用測試環境
${TEST_USER_PREFIX}    qa_autotest_        # 測試帳號前綴
${TEST_RUN_ID}    ${EMPTY}               # 由 Suite Setup 動態生成

*** Keywords ***
初始化測試環境
    ${timestamp}=    Get Current Date    result_format=%Y%m%d%H%M%S
    Set Suite Variable    ${TEST_RUN_ID}    ${timestamp}
    # 創建本次測試專用帳號
    ${test_user}=    Create Test Account    ${TEST_USER_PREFIX}${TEST_RUN_ID}
    Set Suite Variable    ${TEST_USER}    ${test_user}
    # 充值測試點數（標記為測試充值，不計入財務報表）
    Add Test Points    ${TEST_USER}    10000    reason=automation_test

清理測試資料
    # 清除本次測試產生的所有資料
    Delete Test Account    ${TEST_USER}
    Log    測試帳號 ${TEST_USER} 已清理

*** Test Cases ***
測試打賞功能
    [Tags]    gift    automation    isolated
    [Documentation]    使用隔離的測試帳號測試打賞功能
    ${balance_before}=    Get User Points    ${TEST_USER}
    Send Gift To Host    ${TEST_USER}    host_id=test_host_001    gift_id=1
    ${balance_after}=    Get User Points    ${TEST_USER}
    Should Be Less Than    ${balance_after}    ${balance_before}
```

```python
# 測試帳號管理工具
class TestAccountManager:
    TEST_USER_PREFIX = "qa_autotest_"

    @classmethod
    def create_test_account(cls, run_id: str) -> dict:
        """創建測試帳號，所有相關交易標記 is_test=True"""
        user = User.objects.create(
            email=f"{cls.TEST_USER_PREFIX}{run_id}@qa.internal",
            is_test_account=True,  # 財務報表過濾此標記
            created_by='automation'
        )
        return user

    @classmethod
    def cleanup_test_accounts(cls, max_age_hours: int = 24):
        """清理超過指定時間的測試帳號"""
        cutoff = timezone.now() - timedelta(hours=max_age_hours)
        User.objects.filter(
            email__startswith=cls.TEST_USER_PREFIX,
            created_at__lt=cutoff
        ).delete()
```

**反哺規則：**
```
RULE-QA-001: Robot Framework 測試不得連接正式環境資料庫。
  - 觸發條件: 測試檔案中出現 production/prod DB 連線字串
  - 掃描模式: DB_HOST.*production|DB_HOST.*prod(?!uct)
  - 嚴重度: HIGH
```

---

## 不變量速查表（Invariants）

| ID | 描述 | 違反後果 |
|----|------|---------|
| INV-CRED-001 | 用戶點數餘額永遠 >= 0 | 財務漏洞 |
| INV-CRED-002 | 每筆點數變動必有對應交易記錄 | 無法對帳 |
| INV-CRED-003 | 充值點數 = 支付金額 * 匯率（Decimal 精確） | 財務誤差 |
| INV-GAM-001 | 賠付 = 下注 * 賠率（不超過最大賠付限制） | 財務損失 |
| INV-GAM-002 | 每局博弈只能結算一次 | 雙重賠付 |
| INV-GAM-003 | 遊戲結果必須由服務端 secrets 模組生成 | 可被預測 |
| INV-PAY-001 | 回調必須驗簽且金額與訂單一致 | 免費充值攻擊 |
| INV-PAY-002 | 同一支付流水號只能處理一次 | 重複充值 |

---

## 版本歷程

| 版本 | 日期 | 說明 |
|------|------|------|
| 1.0.0 | 2026-06-05 | 初版，整合點數、博弈、金流、直播、QA 五大模組 |

*本文件取代 `financial-bug-patterns.md`，請更新相關參考連結。*
