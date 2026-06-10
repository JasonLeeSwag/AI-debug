---
file_id: rules-registry
kind: registry
status: active
schema_version: 2.0
last_reviewed: 2026-06-05
stale_after_days: 180
owner: swag-qa-team
external_refs: ["semgrep", "bandit", "eslint-security", "robocop"]
---

# SWAG QA 靜態掃描規則登錄

> 檔案路徑：knowledge-base/rules-registry.md
> 用途：將知識庫中的 Bug 模式轉化為可執行的靜態掃描規則，適用於 SWAG 平台（swag.live）QA 部門
> 適用技術：Python、FastAPI/Django、React/JSX、JavaScript、Flutter Web、Robot Framework、Playwright
> 更新時機：每次事後檢視後，由 QA 工程師追加；新規則先標記 candidate，經驗證後改為就緒
> 工具對應：Bandit / Semgrep 自訂規則 / ESLint Security Plugin / Robocop / PR Review Checklist

---

## 規則分類說明

```
RULE-GAM-XXX  → 博弈遊戲相關（RNG、賠率計算、結算並發）
RULE-PAY-XXX  → 支付/金流相關（ECPay、支付寶、微信支付、91app）
RULE-CRED-XXX → 點數/分相關（充值、扣減、餘額、打賞）
RULE-LIVE-XXX → 直播功能相關（打賞、訂閱、主播分潤）
RULE-SEC-XXX  → 安全/舞弊相關（IDOR、竄改、注入、年齡驗證）
RULE-QA-XXX   → QA 自動化品質相關（Robot Framework、Playwright、測試資料管理）
```

---

## 規則清單

---

### RULE-GAM-001：博弈 RNG 必須使用密碼學安全模組

**來源模式**：gambling-game-patterns.md → PAT-GAM-001
**嚴重等級**：CRITICAL
**對應工具**：Bandit（B311）、Semgrep 自訂規則

**違規特徵**：
```python
# 違規：使用 random 模組決定博弈結果
import random
result = random.random()           # B311 警告
result = random.choice(['dragon', 'tiger'])
result = random.randint(1, 13)     # 撲克牌值
```

**Semgrep 規則片段**：
```yaml
rules:
  - id: swag-gambling-insecure-rng
    patterns:
      - pattern: random.$METHOD(...)
    message: "博弈遊戲結果不得使用 random 模組，請改用 secrets 模組"
    languages: [python]
    severity: ERROR
    metadata:
      category: security
      rule_id: RULE-GAM-001
```

**修復範例**：
```python
# 正確：使用密碼學安全的 secrets 模組
import secrets
result = secrets.choice(['dragon', 'tiger'])
card_value = secrets.randbelow(13) + 1
suit = secrets.choice(['spades', 'hearts', 'diamonds', 'clubs'])
```

**PR Review 檢查點**：
```
☑ 博弈遊戲結果生成不使用 random、numpy.random、math.random
☑ 使用 secrets.choice()、secrets.randbelow() 或 os.urandom()
☑ RNG 種子不來自可預測值（時間戳、用戶 ID 等）
☑ 結算日誌記錄亂數種子的 entropy 來源（用於審計）
```

---

### RULE-GAM-002：博弈賠率計算必須使用 Decimal

**來源模式**：gambling-game-patterns.md → PAT-GAM-002
**嚴重等級**：CRITICAL
**對應工具**：Bandit、Semgrep 自訂規則

**違規特徵**：
```python
# 違規：float 參與賠率/賠付計算
bet_amount = float(user_bet)
payout = bet_amount * 1.95        # float 精度誤差
commission = payout * 0.05        # 累積誤差更大

# 另一種常見錯誤
odds = 1.95
result = odds * float(100)        # 應得 195，可能得到 194.99999...
```

**Semgrep 規則片段**：
```yaml
rules:
  - id: swag-gambling-float-payout
    patterns:
      - pattern: float($X) * $ODDS
      - pattern: $AMOUNT * float($ODDS)
    message: "博弈賠付計算不得使用 float，請改用 Decimal"
    languages: [python]
    severity: ERROR
    metadata:
      rule_id: RULE-GAM-002
```

**修復範例**：
```python
from decimal import Decimal, ROUND_HALF_DOWN

bet_amount = Decimal(str(user_bet))
odds = Decimal('1.95')
payout = (bet_amount * odds).quantize(Decimal('0.01'), rounding=ROUND_HALF_DOWN)
commission = (payout * Decimal('0.05')).quantize(Decimal('0.01'), rounding=ROUND_HALF_DOWN)
net_payout = payout - commission
```

**PR Review 檢查點**：
```
☑ 賠率常數使用 Decimal('1.95') 而非 1.95 或 Decimal(1.95)
☑ 所有中間計算結果保留足夠精度（建議 8 位），最終入帳前 quantize
☑ 多方分潤（主播/平台/稅）使用最大餘額法，加總等於原始賠付
☑ 賠付金額上限校驗在 Decimal 計算後執行
```

---

### RULE-GAM-003：博弈結算必須有分散式鎖

**來源模式**：gambling-game-patterns.md → PAT-GAM-003
**嚴重等級**：CRITICAL
**對應工具**：Semgrep 自訂規則（人工輔助）

**違規特徵**：
```python
# 違規：settle() 無分散式鎖保護，高並發下可能雙重結算
def settle_round(round_id: str):
    round_data = db.get_round(round_id)
    if round_data.status == 'pending':
        process_payouts(round_data)           # 無鎖保護，競態條件
        db.update_status(round_id, 'settled')

# 另一種錯誤：使用資料庫行鎖但忘記 Redis 分散式鎖
def settle_round(round_id: str):
    with db.transaction():
        round_data = db.get_round_for_update(round_id)  # 只有 DB 鎖，不夠
        process_payouts(round_data)
```

**Semgrep 規則片段**：
```yaml
rules:
  - id: swag-gambling-settle-no-lock
    patterns:
      - pattern: |
          def settle_$ANYTHING(...):
              ...
              $CREDIT(...)
              ...
        pattern-not: |
          def settle_$ANYTHING(...):
              ...
              with $LOCK.lock(...):
                  ...
    message: "結算函式缺少分散式鎖保護"
    languages: [python]
    severity: ERROR
    metadata:
      rule_id: RULE-GAM-003
```

**修復範例**：
```python
import redis
from redis.lock import Lock

redis_client = redis.Redis(host=REDIS_HOST)

def settle_round(round_id: str):
    lock_key = f"settle_lock:round:{round_id}"
    with redis_client.lock(lock_key, timeout=30, blocking_timeout=5):
        round_data = db.get_round(round_id)
        if round_data.status != 'pending':
            return  # 已被其他 worker 結算，跳過
        process_payouts(round_data)
        db.update_status(round_id, 'settled')
```

**PR Review 檢查點**：
```
☑ settle() 系列方法有 Redis distributed lock（redis-py lock() 上下文管理器）
☑ 鎖的 timeout 設定合理（不超過業務 SLA 的 50%）
☑ 鎖取得前已檢查狀態，避免重複結算
☑ 鎖釋放後有驗證結算狀態的最終確認
```

---

### RULE-GAM-004：賠付前必須有業務合理性校驗

**來源模式**：gambling-game-patterns.md → PAT-GAM-004
**嚴重等級**：CRITICAL
**對應工具**：Semgrep 自訂規則

**違規特徵**：
```python
# 違規：直接 credit_points() 無上限校驗
def process_payout(user_id: int, payout_amount: Decimal):
    credit_points(user_id, payout_amount)   # 無任何上限校驗

# 另一種錯誤：校驗在日誌之後
def process_payout(user_id: int, payout_amount: Decimal):
    log.info(f"Paying out {payout_amount} to {user_id}")
    if payout_amount > MAX_PAYOUT:
        alert("異常大額賠付")
    credit_points(user_id, payout_amount)   # 告警後仍繼續執行
```

**修復範例**：
```python
from decimal import Decimal
from config import settings

MAX_SINGLE_PAYOUT = Decimal(str(settings.MAX_SINGLE_PAYOUT))  # 從設定讀取

class SettlementGuard:
    @staticmethod
    def validate(user_id: int, payout_amount: Decimal, bet_amount: Decimal) -> None:
        if payout_amount <= Decimal('0'):
            raise ValueError(f"賠付金額不得為負或零: {payout_amount}")
        if payout_amount > MAX_SINGLE_PAYOUT:
            alert_ops(f"異常大額賠付: user={user_id}, amount={payout_amount}")
            raise PayoutLimitExceeded(f"超過單筆賠付上限: {payout_amount}")
        max_ratio = Decimal('200')  # 最大賠率倍數
        if bet_amount > Decimal('0') and payout_amount / bet_amount > max_ratio:
            raise PayoutRatioExceeded(f"賠率異常: {payout_amount / bet_amount}")

def process_payout(user_id: int, payout_amount: Decimal, bet_amount: Decimal):
    SettlementGuard.validate(user_id, payout_amount, bet_amount)
    credit_points(user_id, payout_amount)
```

**PR Review 檢查點**：
```
☑ 賠付前呼叫 SettlementGuard.validate()
☑ MAX_SINGLE_PAYOUT 從設定檔讀取（不硬編碼在程式碼中）
☑ 告警在拋出例外前觸發（確保告警不因例外遺失）
☑ 賠率上限校驗（防止賠率計算錯誤導致意外大額賠付）
```

---

### RULE-PAY-001：支付回調必須驗簽

**來源模式**：payment-gateway-patterns.md → PAT-PAY-001
**嚴重等級**：CRITICAL
**對應工具**：Semgrep 自訂規則（taint tracking）

**違規特徵**：
```python
# 違規（綠界 ECPay）：直接解析回調不驗簽
@router.post("/ecpay/callback")
async def ecpay_callback(request: Request):
    body = await request.form()
    order_id = body.get('MerchantTradeNo')
    credit_points(order_id)             # 未驗簽直接充值

# 違規（支付寶）：不驗證 sign 參數
@router.post("/alipay/notify")
async def alipay_notify(request: Request):
    params = await request.form()
    if params.get('trade_status') == 'TRADE_SUCCESS':
        credit_points(params['out_trade_no'])   # 未呼叫 verify_sign()

# 違規（微信支付）：不驗證 XML signature
@router.post("/wxpay/notify")
async def wxpay_notify(request: Request):
    body = await request.body()
    data = parse_xml(body)
    if data['result_code'] == 'SUCCESS':
        credit_points(data['out_trade_no'])     # 未驗簽
```

**Semgrep 規則片段（綠界）**：
```yaml
rules:
  - id: swag-ecpay-callback-no-verify
    patterns:
      - pattern: |
          @router.post("/ecpay/...")
          async def $FUNC(...):
              ...
              credit_$ACTION(...)
        pattern-not: |
          @router.post("/ecpay/...")
          async def $FUNC(...):
              ...
              verify_ecpay_signature(...)
              ...
              credit_$ACTION(...)
    message: "綠界回調未驗簽即充值，CRITICAL 安全漏洞"
    languages: [python]
    severity: ERROR
    metadata:
      rule_id: RULE-PAY-001
      platform: ecpay
```

**修復範例（各平台）**：
```python
# 綠界 ECPay 驗簽
import hashlib
import urllib.parse

def verify_ecpay_signature(params: dict, hash_key: str, hash_iv: str) -> bool:
    check_mac_value = params.pop('CheckMacValue', '')
    sorted_params = sorted(params.items(), key=lambda x: x[0].lower())
    param_str = '&'.join([f"{k}={v}" for k, v in sorted_params])
    raw = f"HashKey={hash_key}&{param_str}&HashIV={hash_iv}"
    encoded = urllib.parse.quote_plus(raw).lower()
    computed = hashlib.sha256(encoded.encode()).hexdigest().upper()
    return computed == check_mac_value

# 支付寶驗簽
from alipay import AliPay
def verify_alipay_signature(params: dict) -> bool:
    alipay = AliPay(appid=ALIPAY_APPID, alipay_public_key_string=ALIPAY_PUBLIC_KEY)
    sign = params.pop('sign', '')
    sign_type = params.pop('sign_type', 'RSA2')
    return alipay.verify(params, sign)

# 微信支付驗簽（v3 API）
import hmac, hashlib
def verify_wxpay_signature(headers: dict, body: bytes, api_v3_key: str) -> bool:
    timestamp = headers.get('Wechatpay-Timestamp')
    nonce = headers.get('Wechatpay-Nonce')
    signature = headers.get('Wechatpay-Signature')
    message = f"{timestamp}\n{nonce}\n{body.decode()}\n"
    # 使用微信公鑰驗證 RSA-SHA256 簽章（從微信平台下載公鑰）
    return wxpay_rsa_verify(message.encode(), signature, WXPAY_PUBLIC_KEY)
```

**PR Review 檢查點**：
```
☑ 綠界回調：CheckMacValue SHA256 驗簽（HashKey + 參數排序 + HashIV）
☑ 支付寶回調：RSA2 公鑰驗簽（sign 欄位），並驗證 app_id 是我方
☑ 微信回調：使用微信公鑰驗簽（v2 HMAC-SHA256 或 v3 RSA-SHA256）
☑ 91app 回調：驗證 HMAC 簽章與來源 Token
☑ 驗簽失敗立即返回錯誤，不繼續處理
```

---

### RULE-PAY-002：回調金額必須與訂單金額比對

**來源模式**：payment-gateway-patterns.md → PAT-PAY-002
**嚴重等級**：CRITICAL
**對應工具**：Semgrep 自訂規則

**違規特徵**：
```python
# 違規：只驗簽不比對金額
@router.post("/ecpay/callback")
async def ecpay_callback(request: Request):
    body = await request.form()
    if not verify_ecpay_signature(dict(body)):
        return Response("0|Verify Failed")
    order_id = body.get('MerchantTradeNo')
    # 危險：未比對金額，攻擊者可用小額支付的合法回調觸發大額充值
    order = db.get_order(order_id)
    credit_points(order.user_id, order.points)   # 點數用訂單金額，但支付金額未驗
```

**修復範例**：
```python
@router.post("/ecpay/callback")
async def ecpay_callback(request: Request):
    body = dict(await request.form())
    if not verify_ecpay_signature(body):
        return Response("0|Verify Failed")

    order_id = body.get('MerchantTradeNo')
    callback_amount = Decimal(body.get('TradeAmt', '0'))

    order = db.get_order(order_id)
    if order is None:
        return Response("0|Order Not Found")

    # 嚴格比對回調金額與訂單金額
    if callback_amount != order.amount:
        log.error(f"金額不符: callback={callback_amount}, order={order.amount}, order_id={order_id}")
        alert_ops("支付回調金額不符，疑似攻擊")
        return Response("0|Amount Mismatch")

    credit_points(order.user_id, order.points)
    return Response("1|OK")
```

**PR Review 檢查點**：
```
☑ 回調金額（TradeAmt / total_amount / total_fee）與訂單金額嚴格相等比對
☑ 金額比對使用 Decimal（不使用 float 比對）
☑ 金額不符時記錄完整日誌並觸發告警
☑ 微信支付金額單位為「分」，比對前需換算（見 RULE-PAY-004）
```

---

### RULE-PAY-003：支付回調必須有冪等保護

**來源模式**：payment-gateway-patterns.md → PAT-PAY-003
**嚴重等級**：CRITICAL
**對應工具**：Semgrep 自訂規則

**違規特徵**：
```python
# 違規：callback handler 無冪等保護
@router.post("/alipay/notify")
async def alipay_notify(request: Request):
    params = dict(await request.form())
    verify_alipay_signature(params)
    trade_no = params.get('trade_no')
    out_trade_no = params.get('out_trade_no')
    # 支付寶會重複發送 notify，無冪等保護會導致重複充值
    order = db.get_order(out_trade_no)
    credit_points(order.user_id, order.points)
    return Response("success")
```

**修復範例**：
```python
import redis
REDIS_CLIENT = redis.Redis(host=REDIS_HOST)

@router.post("/alipay/notify")
async def alipay_notify(request: Request):
    params = dict(await request.form())
    if not verify_alipay_signature(params):
        return Response("fail")

    trade_no = params.get('trade_no')        # 支付寶交易號
    out_trade_no = params.get('out_trade_no')  # 我方訂單號

    # 冪等保護：使用支付寶 trade_no 作為冪等鍵
    idempotent_key = f"pay_callback:alipay:{trade_no}"
    is_first = REDIS_CLIENT.set(idempotent_key, "processing", ex=86400, nx=True)
    if not is_first:
        # 已處理過或正在處理中，檢查訂單狀態
        order = db.get_order(out_trade_no)
        if order.status == 'paid':
            return Response("success")  # 已完成，正常返回
        # 正在處理中，支付寶等待後重試
        return Response("fail")

    try:
        order = db.get_order(out_trade_no)
        if order.status != 'pending':
            return Response("success")

        # 金額比對（此處略去，詳見 RULE-PAY-002）
        credit_points(order.user_id, order.points)
        db.update_order_status(out_trade_no, 'paid')
        REDIS_CLIENT.set(idempotent_key, "completed", ex=86400 * 7)
        return Response("success")
    except Exception as e:
        # 業務失敗：清除 Redis key，允許支付寶重試
        REDIS_CLIENT.delete(idempotent_key)
        log.error(f"支付回調處理失敗: {e}")
        return Response("fail")
```

**PR Review 檢查點**：
```
☑ 使用支付平台的交易號（trade_no / transaction_id）而非我方訂單號作為冪等鍵
☑ Redis setex 冪等鍵（nx=True），TTL 至少 24 小時
☑ 處理成功後延長 TTL 至 7 天（防止舊回調重放）
☑ 業務失敗時刪除 Redis key，允許重試
☑ 同時用資料庫訂單狀態作為第二層冪等保護
```

---

### RULE-PAY-004：微信支付金額必須是整數分（非元）

**來源模式**：payment-gateway-patterns.md → PAT-PAY-004
**嚴重等級**：MAJOR
**對應工具**：Semgrep 自訂規則、單元測試

**違規特徵**：
```python
# 違規：忘記將元轉換為分
order_data = {
    "out_trade_no": order_id,
    "total_fee": amount,          # 錯誤：amount=100 元，微信收到 100 分（1 元）
    "body": "SWAG 點數充值",
}

# 另一種錯誤：使用 float 轉換
total_fee = int(float(amount) * 100)  # float 精度風險
```

**修復範例**：
```python
from decimal import Decimal, ROUND_DOWN

def yuan_to_fen(amount_yuan: Decimal) -> int:
    """
    將元（Decimal）轉換為分（整數），用於微信支付。
    範例：Decimal('99.90') -> 9990
    """
    fen = (amount_yuan * Decimal('100')).to_integral_value(rounding=ROUND_DOWN)
    return int(fen)

order_data = {
    "out_trade_no": order_id,
    "total_fee": yuan_to_fen(order.amount),   # 正確：99.90 元 → 9990 分
    "body": "SWAG 點數充值",
}

# 回調驗證時也需反向換算
callback_fen = int(callback_data.get('total_fee', 0))
callback_yuan = Decimal(callback_fen) / Decimal('100')
assert callback_yuan == order.amount, f"金額不符: {callback_yuan} != {order.amount}"
```

**PR Review 檢查點**：
```
☑ 微信支付下單時 total_fee 為整數（分）
☑ 使用 Decimal 做元轉分，不使用 float
☑ 回調金額比對時將分換算回元再比對
☑ 單元測試覆蓋邊界值（0.01 元、99.90 元等有小數的案例）
```

---

### RULE-CRED-001：點數計算禁止使用 float

**來源模式**：swag-bug-patterns.md → PAT-CRED-001
**嚴重等級**：CRITICAL
**對應工具**：Bandit、Semgrep 自訂規則

**違規特徵**：
```python
# 違規：float 參與點數計算
points = float(purchase_amount) * exchange_rate
balance = user.points - float(deduction)
tip_to_streamer = float(tip_amount) * 0.7   # 主播分潤

# 另一種常見錯誤：混用 Decimal 和 float
from decimal import Decimal
points = Decimal(str(purchase_amount)) * float(rate)  # float 會污染 Decimal 計算
```

**修復範例**：
```python
from decimal import Decimal, ROUND_HALF_DOWN

def calculate_points(purchase_amount: str, exchange_rate: str) -> Decimal:
    amount = Decimal(purchase_amount)
    rate = Decimal(exchange_rate)
    return (amount * rate).quantize(Decimal('1'), rounding=ROUND_HALF_DOWN)

def calculate_tip_split(tip_amount: Decimal) -> tuple[Decimal, Decimal]:
    """計算打賞分潤：主播 70%，平台 30%"""
    streamer_share = (tip_amount * Decimal('0.70')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_DOWN
    )
    platform_share = tip_amount - streamer_share  # 最大餘額法，確保加總守恆
    return streamer_share, platform_share
```

**PR Review 檢查點**：
```
☑ 點數計算全程使用 Decimal，不使用 float
☑ Decimal 初始化使用字串 Decimal('1.95')，不使用 Decimal(1.95)
☑ 分潤計算使用最大餘額法（一方先算，剩餘給另一方）
☑ 最終點數為整數（quantize 到 Decimal('1')）
```

---

### RULE-CRED-002：點數扣減必須原子操作

**來源模式**：swag-bug-patterns.md → PAT-CRED-002
**嚴重等級**：CRITICAL
**對應工具**：Semgrep 自訂規則（模式比對）

**違規特徵**：
```python
# 違規：先 SELECT 後 UPDATE 無鎖（TOCTOU 競態條件）
def debit_points(user_id: int, amount: int) -> bool:
    user = db.get_user(user_id)           # SELECT
    if user.points >= amount:
        user.points -= amount             # 應用層計算
        db.save(user)                     # UPDATE（無 WHERE points >= amount）
        return True
    return False
```

**修復範例**：
```python
# 正確：原子 SQL 操作，確保不超扣
def debit_points(user_id: int, amount: int) -> bool:
    """
    原子扣減點數。只有當 points >= amount 時才更新，防止超扣。
    返回 True 表示扣減成功，False 表示餘額不足。
    """
    rows_updated = db.execute(
        "UPDATE users SET points = points - %s "
        "WHERE id = %s AND points >= %s",
        (amount, user_id, amount)
    )
    return rows_updated > 0

# Django ORM 版本
from django.db.models import F
def debit_points_django(user_id: int, amount: int) -> bool:
    updated = User.objects.filter(
        id=user_id,
        points__gte=amount
    ).update(points=F('points') - amount)
    return updated > 0
```

**PR Review 檢查點**：
```
☑ 點數扣減使用原子 SQL（UPDATE ... WHERE points >= amount）
☑ 返回值檢查（0 rows updated = 餘額不足，拋出 InsufficientPointsError）
☑ 不在應用層進行「先查後改」的兩步驟操作
☑ 高並發場景考慮資料庫行鎖或 Redis 原子操作（DECRBY + 監控）
```

---

### RULE-CRED-003：點數操作必須有冪等保護

**來源模式**：swag-bug-patterns.md → PAT-CRED-003
**嚴重等級**：CRITICAL
**對應工具**：Semgrep 自訂規則

**違規特徵**：
```python
# 違規：充值/扣款無冪等鍵
@router.post("/api/credits/charge")
async def charge_credits(request: ChargeRequest, user: User = Depends(get_current_user)):
    # 網路重試可能導致重複充值
    credit_points(user.id, request.points)
    return {"status": "success"}

# 違規：使用不夠唯一的冪等鍵
idempotent_key = f"charge:{user_id}:{timestamp}"  # timestamp 精度不足，可能碰撞
```

**修復範例**：
```python
import uuid
import redis

REDIS_CLIENT = redis.Redis(host=REDIS_HOST)

class ChargeRequest(BaseModel):
    points: int
    request_id: str  # 前端生成的 UUID v4，作為冪等鍵

@router.post("/api/credits/charge")
async def charge_credits(
    request: ChargeRequest,
    user: User = Depends(get_current_user)
):
    # 冪等保護：request_id 作為冪等鍵
    idempotent_key = f"charge:v1:{user.id}:{request.request_id}"
    is_first = REDIS_CLIENT.set(idempotent_key, "processing", ex=86400, nx=True)

    if not is_first:
        # 重複請求：返回原始結果
        existing_order = db.get_charge_by_request_id(request.request_id)
        if existing_order:
            return {"status": "success", "idempotent": True, "order_id": existing_order.id}
        return {"status": "processing"}  # 首次請求仍在處理中

    try:
        order = db.create_charge_order(user.id, request.points, request.request_id)
        credit_points(user.id, request.points)
        db.complete_order(order.id)
        REDIS_CLIENT.set(idempotent_key, f"done:{order.id}", ex=86400 * 7)
        return {"status": "success", "order_id": order.id}
    except Exception as e:
        REDIS_CLIENT.delete(idempotent_key)
        raise
```

**PR Review 檢查點**：
```
☑ 所有 credit/debit 操作有 request_id 冪等鍵（前端傳入 UUID v4）
☑ Redis setex（nx=True）+ DB 訂單記錄作為雙層冪等保護
☑ 冪等鍵命名包含版本號（如 charge:v1:）方便未來升級
☑ 失敗時清除 Redis key，允許前端重試
```

---

### RULE-CRED-004：點數扣減後餘額不能為負

**來源模式**：swag-bug-patterns.md → PAT-CRED-004
**嚴重等級**：CRITICAL
**對應工具**：資料庫 CHECK 約束、Semgrep 自訂規則

**違規特徵**：
```python
# 違規：未驗證扣減後餘額，依賴應用層檢查
def place_bet(user_id: int, bet_amount: int):
    user = db.get_user(user_id)
    if user.points < bet_amount:
        raise InsufficientPointsError()
    # 競態條件：兩個並發請求都通過了上面的檢查
    db.execute("UPDATE users SET points = points - %s WHERE id = %s",
               (bet_amount, user_id))   # 可能導致負數
```

**修復範例**：
```python
# 應用層：原子 SQL 確保不負
def place_bet(user_id: int, bet_amount: int) -> bool:
    rows = db.execute(
        "UPDATE users SET points = points - %s WHERE id = %s AND points >= %s",
        (bet_amount, user_id, bet_amount)
    )
    if rows == 0:
        raise InsufficientPointsError(f"user={user_id}, amount={bet_amount}")
    return True

# 資料庫層：CHECK 約束作為最後防線（DDL）
# ALTER TABLE users ADD CONSTRAINT chk_points_non_negative CHECK (points >= 0);

# Django Migration 範例
class Migration(migrations.Migration):
    operations = [
        migrations.AddConstraint(
            model_name='user',
            constraint=models.CheckConstraint(
                check=models.Q(points__gte=0),
                name='chk_users_points_non_negative'
            )
        ),
    ]
```

**PR Review 檢查點**：
```
☑ 應用層：原子 SQL WHERE points >= amount 防止超扣
☑ 資料庫層：points 欄位有 CHECK (points >= 0) 約束
☑ 單元測試：並發下注場景，多請求只有一個成功
☑ 整合測試：超扣嘗試返回明確錯誤而非靜默失敗
```

---

### RULE-LIVE-001：打賞操作必須有冪等保護

**來源模式**：streaming-platform-patterns.md → PAT-LIVE-001
**嚴重等級**：CRITICAL
**對應工具**：Semgrep 自訂規則

**違規特徵**：
```python
# 違規：WebSocket 打賞消息無 request_id 冪等鍵
# WebSocket handler
async def handle_gift_message(websocket, user_id: int, data: dict):
    gift_id = data.get('gift_id')
    streamer_id = data.get('streamer_id')
    # WebSocket 斷線重連時，前端可能重送同一條消息
    await send_gift(user_id, streamer_id, gift_id)  # 無冪等保護，可能重複打賞
```

**修復範例**：
```python
import redis
REDIS_CLIENT = redis.Redis(host=REDIS_HOST)

async def handle_gift_message(websocket, user_id: int, data: dict):
    request_id = data.get('request_id')  # 前端為每次打賞生成唯一 UUID
    if not request_id:
        await websocket.send_json({"error": "missing request_id"})
        return

    idempotent_key = f"gift:v1:{user_id}:{request_id}"
    is_first = REDIS_CLIENT.set(idempotent_key, "processing", ex=3600, nx=True)

    if not is_first:
        # 重複打賞消息，返回原始結果
        await websocket.send_json({"status": "success", "idempotent": True})
        return

    try:
        result = await send_gift(user_id, data['streamer_id'], data['gift_id'])
        REDIS_CLIENT.set(idempotent_key, f"done:{result.id}", ex=86400)
        await websocket.send_json({"status": "success", "gift_record_id": result.id})
    except InsufficientPointsError:
        REDIS_CLIENT.delete(idempotent_key)
        await websocket.send_json({"error": "insufficient_points"})
    except Exception as e:
        REDIS_CLIENT.delete(idempotent_key)
        raise
```

**PR Review 檢查點**：
```
☑ 打賞 WebSocket 消息包含前端生成的 request_id（UUID v4）
☑ Redis setex 冪等鍵（nx=True），TTL 1 小時（打賞場景短 TTL 即可）
☑ 送禮動畫僅在首次成功時觸發（冪等重入不重複播放動畫）
☑ 前端在 WebSocket 重連後不自動重發打賞消息（需用戶確認）
```

---

### RULE-LIVE-002：主播分潤計算必須使用 Decimal

**來源模式**：streaming-platform-patterns.md → PAT-LIVE-002
**嚴重等級**：CRITICAL
**對應工具**：Bandit、Semgrep 自訂規則

**違規特徵**：
```python
# 違規：float 計算主播分潤
def calculate_streamer_revenue(tip_total: float, subscription_total: float) -> float:
    streamer_rate = 0.7   # 主播抽成 70%
    return (tip_total + subscription_total) * streamer_rate  # float 精度問題

# 違規：未確保多方加總守恆
def split_revenue(total: Decimal) -> dict:
    streamer = total * Decimal('0.70')
    platform = total * Decimal('0.25')
    tax = total * Decimal('0.05')
    # 三者加總可能因 quantize 不等於 total
    return {"streamer": streamer, "platform": platform, "tax": tax}
```

**修復範例**：
```python
from decimal import Decimal, ROUND_HALF_DOWN

def split_revenue(total: Decimal) -> dict:
    """
    主播分潤計算：主播 70%、平台 25%、稅 5%
    使用最大餘額法確保加總守恆
    """
    tax = (total * Decimal('0.05')).quantize(Decimal('0.01'), rounding=ROUND_HALF_DOWN)
    platform = (total * Decimal('0.25')).quantize(Decimal('0.01'), rounding=ROUND_HALF_DOWN)
    streamer = total - tax - platform   # 最大餘額法：剩餘全給主播

    # 驗證守恆性
    assert streamer + platform + tax == total, \
        f"分潤加總不守恆: {streamer} + {platform} + {tax} != {total}"

    return {"streamer": streamer, "platform": platform, "tax": tax}
```

**PR Review 檢查點**：
```
☑ 分潤計算全程使用 Decimal
☑ 使用最大餘額法（最大比例方拿剩餘），確保加總等於原始金額
☑ 有明確的守恆性斷言（sum of parts == total）
☑ 月結算時批量計算有更嚴格的精度要求（建議保留 8 位後聚合）
```

---

### RULE-LIVE-003：年齡驗證必須在 API 層

**來源模式**：streaming-platform-patterns.md → PAT-LIVE-003
**嚴重等級**：CRITICAL（法規合規）
**對應工具**：Semgrep 自訂規則（人工輔助）

**違規特徵**：
```python
# 違規：年齡驗證只在前端（React/JSX）
// AgeVerification.jsx
const AgeVerification = () => {
  const handleConfirm = () => {
    if (userAge >= 18) {
      navigate('/live');   // 只有前端驗證，後端未驗證
    }
  };
};

# 違規：API 端點缺少年齡驗證中介軟體
@router.get("/api/live/streams")
async def get_streams(user: User = Depends(get_current_user)):
    return db.get_active_streams()   # 未驗證 user.age_verified
```

**修復範例**：
```python
# 年齡驗證 Middleware（FastAPI）
from fastapi import HTTPException, Depends

def require_age_verified(user: User = Depends(get_current_user)) -> User:
    """確保用戶已完成年齡驗證（18+），不通過則拒絕存取成人內容"""
    if not user.age_verified:
        raise HTTPException(
            status_code=403,
            detail="需要完成年齡驗證才能存取成人內容"
        )
    return user

# 所有成人內容端點套用此依賴
@router.get("/api/live/streams")
async def get_streams(user: User = Depends(require_age_verified)):
    return db.get_active_streams()

@router.post("/api/gifts/send")
async def send_gift(
    request: GiftRequest,
    user: User = Depends(require_age_verified)
):
    return await process_gift(user, request)
```

**PR Review 檢查點**：
```
☑ 所有成人內容 API 端點套用 require_age_verified 依賴注入
☑ 年齡驗證狀態儲存於資料庫（users.age_verified），不依賴 Session/Cookie
☑ age_verified 欄位只有 KYC 流程可以設定為 True（不允許 API 直接修改）
☑ 前端年齡驗證僅作為 UX 引導，不作為安全控制
```

---

### RULE-SEC-001：API 必須驗證資源歸屬（IDOR 防護）

**來源模式**：swag-bug-patterns.md → PAT-SEC-001
**嚴重等級**：CRITICAL
**對應工具**：Semgrep 自訂規則（taint tracking）

**違規特徵**：
```python
# 違規：使用請求中的 user_id 而非 JWT 中的 user_id
@router.get("/api/orders/{order_id}")
async def get_order(order_id: int, user_id: int):  # user_id 來自請求參數
    order = db.get_order(order_id)   # 攻擊者可以查詢任意用戶的訂單
    return order

# 違規：只驗證 JWT 但不驗資源歸屬
@router.delete("/api/subscriptions/{sub_id}")
async def cancel_subscription(
    sub_id: int,
    user: User = Depends(get_current_user)
):
    db.delete_subscription(sub_id)  # 未驗證 subscription.user_id == user.id
```

**Semgrep 規則片段**：
```yaml
rules:
  - id: swag-idor-user-id-from-request
    pattern: |
      @router.$METHOD(...)
      async def $FUNC(..., user_id: int, ...):
          ...
    message: "API 端點使用請求參數中的 user_id，可能存在 IDOR 漏洞，應從 JWT 取得"
    languages: [python]
    severity: ERROR
    metadata:
      rule_id: RULE-SEC-001
```

**修復範例**：
```python
# 正確：從 JWT 取得 user_id，並驗證資源歸屬
@router.get("/api/orders/{order_id}")
async def get_order(
    order_id: int,
    user: User = Depends(get_current_user)  # user_id 來自 JWT
):
    order = db.get_order_by_id_and_user(order_id, user.id)  # DB 層強制歸屬
    if order is None:
        raise HTTPException(status_code=404, detail="訂單不存在")
    return order

@router.delete("/api/subscriptions/{sub_id}")
async def cancel_subscription(
    sub_id: int,
    user: User = Depends(get_current_user)
):
    subscription = db.get_subscription(sub_id)
    if subscription is None or subscription.user_id != user.id:
        raise HTTPException(status_code=403, detail="無權存取此訂閱")
    db.delete_subscription(sub_id)
```

**PR Review 檢查點**：
```
☑ API 端點中的 user_id 來自 JWT 解碼（Depends(get_current_user)）
☑ 資源查詢在 SQL 層加入 AND user_id = ? 條件
☑ 找不到資源返回 404（不洩露資源存在性）
☑ 管理員操作有獨立的 admin 驗證，不能用普通 JWT 繞過
```

---

### RULE-SEC-002：敏感欄位禁止寫入日誌

**來源模式**：swag-bug-patterns.md → PAT-SEC-002
**嚴重等級**：CRITICAL
**對應工具**：Semgrep 自訂規則、Bandit（B506）

**違規特徵**：
```python
# 違規：日誌包含支付資訊
log.info(f"Payment request: {payment_info}")
log.debug(f"Card number: {card_number}, CVV: {cvv}")
log.error(f"Alipay callback failed: {json.dumps(callback_body)}")  # callback_body 可能含帳號密碼
```

**Semgrep 規則片段**：
```yaml
rules:
  - id: swag-sensitive-field-in-log
    patterns:
      - pattern: log.$LEVEL(..., $MSG, ...)
        metavariable-regex:
          metavar: $MSG
          regex: ".*(card_number|cvv|password|secret|private_key|payment_info|bank_account).*"
    message: "日誌中可能包含敏感欄位，請使用遮罩函式"
    languages: [python]
    severity: ERROR
    metadata:
      rule_id: RULE-SEC-002
```

**修復範例**：
```python
import re

SENSITIVE_FIELDS = {'card_number', 'cvv', 'password', 'secret', 'private_key',
                    'bank_account', 'id_number', 'phone'}

def mask_sensitive(data: dict) -> dict:
    """遮罩字典中的敏感欄位"""
    masked = {}
    for key, value in data.items():
        if any(sensitive in key.lower() for sensitive in SENSITIVE_FIELDS):
            if isinstance(value, str) and len(value) > 4:
                masked[key] = f"{'*' * (len(value) - 4)}{value[-4:]}"
            else:
                masked[key] = "****"
        else:
            masked[key] = value
    return masked

# 正確使用
log.info(f"支付回調: {mask_sensitive(callback_body)}")
# 輸出：支付回調: {'out_trade_no': 'ORDER123', 'card_number': '************1234', 'amount': '99.90'}
```

**PR Review 檢查點**：
```
☑ 所有 log.info/debug/error 呼叫，含支付相關資料時套用 mask_sensitive()
☑ CVV、完整卡號永不記錄（即使遮罩後也不建議記錄 CVV）
☑ 支付回調完整 body 記錄時遮罩敏感欄位
☑ 日誌系統有 PII 掃描（防止遮罩被繞過）
```

---

### RULE-SEC-003：SQL 注入防護

**來源模式**：swag-bug-patterns.md → PAT-SEC-003
**嚴重等級**：CRITICAL
**對應工具**：Bandit（B608）、Semgrep（python.lang.security.audit.formatted-sql-query）

**違規特徵**：
```python
# 違規：f-string 拼接 SQL
user_id = request.query_params.get('user_id')
query = f"SELECT * FROM orders WHERE user_id = {user_id}"  # SQL 注入風險
db.execute(query)

# 違規：.format() 拼接
query = "SELECT * FROM users WHERE username = '{}'".format(username)

# 違規：字串加法
query = "SELECT * FROM transactions WHERE streamer_id = " + str(streamer_id)
```

**修復範例**：
```python
# 正確：ORM 參數化查詢（Django）
orders = Order.objects.filter(user_id=user_id)

# 正確：FastAPI + SQLAlchemy 參數化
from sqlalchemy import text
result = db.execute(
    text("SELECT * FROM orders WHERE user_id = :user_id"),
    {"user_id": user_id}
)

# 正確：Raw SQL 參數化（注意使用 %s 佔位符，不是 f-string）
db.execute(
    "SELECT * FROM users WHERE username = %s AND status = %s",
    (username, 'active')
)
```

**PR Review 檢查點**：
```
☑ 所有 SQL 查詢使用 ORM 或參數化查詢
☑ 沒有 f-string、.format()、字串加法拼接 SQL
☑ 動態 ORDER BY 欄位名稱使用白名單驗證
☑ Bandit B608 規則無忽略標記（# nosec）
```

---

### RULE-QA-001：Robot Framework 禁用 Sleep 等待

**來源模式**：qa-automation-patterns.md → PAT-QA-001
**嚴重等級**：MAJOR
**對應工具**：Robocop（W0501）

**違規特徵**：
```robotframework
*** Test Cases ***
充值點數後確認餘額
    點擊充值按鈕
    Sleep    5s              # 違規：固定等待時間，脆弱且浪費時間
    確認餘額已更新

*** Keywords ***
等待支付完成
    Click Button    確認支付
    Sleep    3s              # 違規：應使用動態等待
    Page Should Contain    支付成功
```

**修復範例**：
```robotframework
*** Test Cases ***
充值點數後確認餘額
    點擊充值按鈕
    Wait Until Keyword Succeeds    30s    2s    確認餘額已更新

*** Keywords ***
確認餘額已更新
    ${balance}=    Get Text    data-testid=point-balance
    Should Be True    ${balance} > 0

等待支付完成
    Click Button    確認支付
    # Playwright 內建 auto-wait，不需要 Sleep
    Wait For Elements State    data-testid=payment-success    visible    timeout=30s
    Page Should Contain    支付成功
```

**PR Review 檢查點**：
```
☑ 測試腳本中沒有 Sleep（使用 Robocop 掃描）
☑ 使用 Wait Until Keyword Succeeds 設定重試間隔和超時
☑ Playwright 關鍵字使用 Wait For Elements State 而非 Sleep
☑ 特殊場景（如動畫等待）需在 PR 說明中說明 Sleep 的合理性
```

---

### RULE-QA-002：Playwright Selector 不得耦合 CSS 類名

**來源模式**：qa-automation-patterns.md → PAT-QA-002
**嚴重等級**：MAJOR
**對應工具**：ESLint 自訂規則、Semgrep（JS）

**違規特徵**：
```python
# 違規：使用 CSS 類名（前端改版即失效）
page.click('.btn.primary')
page.fill('.input-field.amount', '100')
page.wait_for_selector('.modal-dialog.payment')

# 違規：使用 XPath 耦合 DOM 結構
page.click('//div[@class="payment-panel"]/button[1]')
```

**修復範例**：
```python
# 正確：使用 data-testid（穩定，不受樣式重構影響）
page.click('[data-testid="charge-button"]')
page.fill('[data-testid="charge-amount-input"]', '100')
page.wait_for_selector('[data-testid="payment-modal"]')

# 正確（Robot Framework + Playwright）
Click    [data-testid=charge-button]
Fill Text    [data-testid=charge-amount-input]    100
Wait For Elements State    [data-testid=payment-modal]    visible
```

```jsx
// 前端 React 元件需加 data-testid
// 正確
<Button
  className="btn primary"
  data-testid="charge-button"   // QA 測試用穩定識別符
  onClick={handleCharge}
>
  充值
</Button>
```

**PR Review 檢查點**：
```
☑ 所有 Playwright 選擇器使用 data-testid
☑ 新增的 React 元件關鍵互動元素有 data-testid 屬性
☑ data-testid 命名規則：kebab-case，如 charge-button、point-balance
☑ 沒有使用 CSS 類名或脆弱的 XPath 選擇器
```

---

### RULE-QA-003：測試結束必須清理測試資料

**來源模式**：qa-automation-patterns.md → PAT-QA-003
**嚴重等級**：MAJOR
**對應工具**：Robocop（W0601）、人工審查

**違規特徵**：
```robotframework
*** Settings ***
# 違規：缺少 Suite Teardown
Library    RequestsLibrary

*** Test Cases ***
測試充值點數
    ${user}=    建立測試用戶
    充值點數    ${user}    1000
    確認點數餘額    ${user}    1000
    # 沒有清理：測試用戶和充值記錄留在資料庫
```

**修復範例**：
```robotframework
*** Settings ***
Library    RequestsLibrary
Suite Setup       建立測試環境
Suite Teardown    清理測試環境      # 必須有 Suite Teardown

*** Variables ***
${TEST_USER_ID}    ${EMPTY}
${TEST_ORDER_IDS}    @{EMPTY}

*** Test Cases ***
測試充值點數
    [Teardown]    清理本測試資料    # 每個測試也有個別 Teardown
    ${user}=    建立測試用戶
    Set Suite Variable    ${TEST_USER_ID}    ${user.id}
    充值點數    ${user}    1000
    確認點數餘額    ${user}    1000

*** Keywords ***
建立測試環境
    Log    初始化測試環境

清理測試環境
    Run Keyword If    '${TEST_USER_ID}' != '${EMPTY}'
    ...    刪除測試用戶    ${TEST_USER_ID}

清理本測試資料
    Run Keyword If    len(${TEST_ORDER_IDS}) > 0
    ...    批量刪除測試訂單    ${TEST_ORDER_IDS}
```

**PR Review 檢查點**：
```
☑ 所有 Test Suite 有 Suite Teardown
☑ 測試用戶、訂單、點數記錄在 Teardown 中清理
☑ Teardown 使用 Run Keyword If 防止空變數導致錯誤
☑ 失敗的測試也能正確觸發 Teardown（Robot Framework 預設行為）
```

---

## 規則健康度追蹤表

| 規則代碼 | 規則摘要 | 最後觸發 | 觸發次數 | 攔截 Bug | 狀態 |
|---------|---------|---------|---------|---------|------|
| RULE-GAM-001 | 博弈 RNG 必須使用密碼學安全模組 | — | 0 | 0 | 就緒 |
| RULE-GAM-002 | 博弈賠率計算必須使用 Decimal | — | 0 | 0 | 就緒 |
| RULE-GAM-003 | 博弈結算必須有分散式鎖 | — | 0 | 0 | 就緒 |
| RULE-GAM-004 | 賠付前必須有業務合理性校驗 | — | 0 | 0 | 就緒 |
| RULE-PAY-001 | 支付回調必須驗簽（各平台） | — | 0 | 0 | 就緒 |
| RULE-PAY-002 | 回調金額必須與訂單金額比對 | — | 0 | 0 | 就緒 |
| RULE-PAY-003 | 支付回調必須有冪等保護 | — | 0 | 0 | 就緒 |
| RULE-PAY-004 | 微信支付金額必須是整數分（非元） | — | 0 | 0 | 就緒 |
| RULE-CRED-001 | 點數計算禁止使用 float | — | 0 | 0 | 就緒 |
| RULE-CRED-002 | 點數扣減必須原子操作 | — | 0 | 0 | 就緒 |
| RULE-CRED-003 | 點數操作必須有冪等保護 | — | 0 | 0 | 就緒 |
| RULE-CRED-004 | 點數扣減後餘額不能為負 | — | 0 | 0 | 就緒 |
| RULE-LIVE-001 | 打賞操作必須有冪等保護 | — | 0 | 0 | 就緒 |
| RULE-LIVE-002 | 主播分潤計算必須使用 Decimal | — | 0 | 0 | 就緒 |
| RULE-LIVE-003 | 年齡驗證必須在 API 層 | — | 0 | 0 | 就緒 |
| RULE-SEC-001 | API 必須驗證資源歸屬（IDOR 防護） | — | 0 | 0 | 就緒 |
| RULE-SEC-002 | 敏感欄位禁止寫入日誌 | — | 0 | 0 | 就緒 |
| RULE-SEC-003 | SQL 注入防護 | — | 0 | 0 | 就緒 |
| RULE-QA-001 | Robot Framework 禁用 Sleep 等待 | — | 0 | 0 | 就緒 |
| RULE-QA-002 | Playwright Selector 不得耦合 CSS 類名 | — | 0 | 0 | 就緒 |
| RULE-QA-003 | 測試結束必須清理測試資料 | — | 0 | 0 | 就緒 |

> 版本：2.0（SWAG QA 版）· 更新日期：2026-06-05
> 規則覆蓋：博弈（4）、支付（4）、點數（4）、直播（3）、安全（3）、QA（3），共 21 條
> 技術堆疊：Python + FastAPI/Django + React/JSX + Robot Framework + Playwright
