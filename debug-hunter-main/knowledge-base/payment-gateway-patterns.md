# SWAG 金流支付整合 Bug 模式知識庫
# payment-gateway-patterns.md
# 版本：1.0.0 | 維護團隊：SWAG QA 部門
# 適用範圍：綠界 ECPay、91app、支付寶、微信支付

---

## 1. 概述

SWAG 平台目前整合以下四個支付平台，服務台灣及大陸用戶的點數購買需求：

| 平台 | 主要用戶群 | 支付方式 | 回調機制 |
|------|-----------|---------|---------|
| 綠界 ECPay | 台灣用戶 | 信用卡、ATM、超商 | HTTP POST 回調 |
| 91app | 台灣用戶 | 整合電商結帳 | Webhook + 主動查詢 |
| 支付寶 | 大陸/海外用戶 | 支付寶 APP、掃碼 | 非同步 notify_url |
| 微信支付 | 大陸/海外用戶 | 微信 APP、掃碼 | 非同步 notify_url |

---

## 2. 各支付平台特性說明

### 2.1 綠界 ECPay

- **簽章算法**：SHA256，需對參數按 ASCII 排序後拼接，前後加 HashKey/HashIV，URL Encode 後轉小寫
- **回調特性**：支付完成後發送一次回調；不保證送達，但不會重複（與支付寶/微信不同）
- **金額單位**：新台幣整數（元），無小數點
- **測試環境**：stage.ecpay.com.tw，需申請測試商家帳號
- **重要限制**：回調必須在 30 秒內回傳 `1|OK`，否則視為失敗

### 2.2 91app

- **整合方式**：OAuth2 + REST API，訂單狀態需主動輪詢 + 接收 Webhook
- **特殊設計**：訂單完成需同時滿足「Webhook 通知」與「主動查詢確認」才算可信
- **金額單位**：新台幣整數
- **測試環境**：sandbox.91app.io

### 2.3 支付寶

- **簽章算法**：RSA2（SHA256WithRSA），使用非對稱加密
- **回調特性**：直到收到 `"success"` 字串才停止重發，間隔為 2m、10m、10m、1h、2h、6h、15h（共 7 次）
- **金額單位**：人民幣，支援小數點後 2 位
- **IP 白名單**：支付寶 notify_url 只從特定 IP 範圍發送，需設定白名單
- **測試環境**：sandbox.alipaydev.com

### 2.4 微信支付

- **簽章算法**：V3 版本使用 RSA + AEAD_AES_256_GCM 加密回調
- **回調特性**：同支付寶，重試直到收到 HTTP 200 + `{"code":"SUCCESS"}`
- **prepay_id 有效期**：統一下單返回的 prepay_id 有效期為 **2 小時**
- **金額單位**：人民幣分（整數，即 100 = 1 元）—— 與支付寶不同！
- **退款特性**：退款非即時，需接收退款回調或主動查詢退款狀態

---

## 3. Bug 模式

### PAT-ECPAY-001：綠界簽章驗證缺失

**描述：**
未驗證綠界回調的 `CheckMacValue` 簽章，直接處理回調內容。攻擊者知道回調 URL 後可偽造任意金額的支付成功通知。

**觸發特徵：**

```python
# 錯誤：直接處理回調，無驗簽
@router.post("/payment/callback/ecpay")
async def ecpay_callback(request: Request):
    data = dict(await request.form())
    order_id = data['MerchantTradeNo']
    # 直接相信回調，完全沒有驗簽步驟
    await process_payment(order_id, data['TradeAmt'])
    return "1|OK"
```

**危害等級：** P0 CRITICAL

**修復策略：**

```python
import hashlib
import urllib.parse
from fastapi import Request, HTTPException
import os

ECPAY_HASH_KEY = os.environ['ECPAY_HASH_KEY']
ECPAY_HASH_IV = os.environ['ECPAY_HASH_IV']

def verify_ecpay_checksum(params: dict, hash_key: str, hash_iv: str) -> bool:
    """
    綠界 ECPay CheckMacValue 驗證。

    算法步驟：
    1. 移除 CheckMacValue 欄位
    2. 依參數名稱 ASCII 不分大小寫排序
    3. 拼接為 key=value&key=value 格式
    4. 前後分別加上 HashKey= 和 &HashIV=
    5. URL Encode（使用 %XX 格式，空格為 +）
    6. 全部轉為小寫
    7. 計算 SHA256，結果轉大寫
    """
    # 複製一份避免修改原始字典
    params_copy = dict(params)
    received_mac = params_copy.pop('CheckMacValue', None)
    if not received_mac:
        return False

    # 步驟 2：ASCII 排序（不分大小寫）
    sorted_params = sorted(params_copy.items(), key=lambda x: x[0].lower())

    # 步驟 3：拼接
    raw = '&'.join([f"{k}={v}" for k, v in sorted_params])

    # 步驟 4：前後加 HashKey/HashIV
    raw = f"HashKey={hash_key}&{raw}&HashIV={hash_iv}"

    # 步驟 5：URL Encode
    # 注意：使用 urllib.parse.quote_plus，空格轉 +，其他特殊字元轉 %XX
    encoded = urllib.parse.quote_plus(raw)

    # 步驟 6：轉小寫
    encoded = encoded.lower()

    # 步驟 7：SHA256 後轉大寫
    computed_mac = hashlib.sha256(encoded.encode('utf-8')).hexdigest().upper()

    # 使用 hmac.compare_digest 防時序攻擊
    import hmac as hmac_module
    return hmac_module.compare_digest(computed_mac, received_mac.upper())


@router.post("/payment/callback/ecpay")
async def ecpay_callback(request: Request):
    data = dict(await request.form())

    # 第一步：驗證簽章
    if not verify_ecpay_checksum(data, ECPAY_HASH_KEY, ECPAY_HASH_IV):
        # 注意：即使驗簽失敗也要回傳 200，避免綠界持續重試
        # 但不處理業務邏輯
        return "0|Signature verification failed"

    # 第二步：檢查交易狀態
    if data.get('RtnCode') != '1':
        # 非成功狀態（如用戶取消支付）
        return "1|OK"

    # 第三步：處理業務邏輯（含冪等保護）
    order_id = data['MerchantTradeNo']
    trade_no = data['TradeNo']
    callback_amount = int(data['TradeAmt'])

    await process_ecpay_payment(order_id, trade_no, callback_amount)
    return "1|OK"  # 綠界要求回傳 "1|OK"
```

**反哺規則：**
```
RULE-ECPAY-001: 所有綠界回調端點必須呼叫 verify_ecpay_checksum。
  - 掃描模式: @router.post.*ecpay 且函式體內無 verify_ecpay_checksum
  - 嚴重度: CRITICAL
```

---

### PAT-ECPAY-002：綠界回調金額單位混淆

**描述：**
綠界 `TradeAmt` 欄位為新台幣整數（元），若當作浮點數處理或誤以為有小數位，會造成點數換算錯誤（通常是多給或少給 100 倍）。

**觸發特徵：**

```python
# 錯誤一：當作浮點數處理
amount = float(data['TradeAmt'])  # TradeAmt 是整數，不需要 float

# 錯誤二：誤用其他平台的解析邏輯（微信是「分」，綠界是「元」）
# 把綠界金額除以 100（誤以為是分）
amount_in_yuan = int(data['TradeAmt']) / 100  # 錯誤！綠界本來就是元

# 錯誤三：混用 Decimal 和原始字串
amount = Decimal(data['TradeAmt']) / Decimal('100')  # 同上，錯誤
```

**危害等級：** P1 HIGH

**修復策略：**

```python
from decimal import Decimal

def parse_ecpay_amount(trade_amt: str) -> Decimal:
    """
    解析綠界 TradeAmt 欄位。
    TradeAmt：新台幣整數，單位為「元」（不是分！）
    範例：TradeAmt="1000" 代表 1000 元整
    """
    amount = int(trade_amt)  # 必須是整數
    if amount <= 0:
        raise ValueError(f"無效的綠界金額：{trade_amt}")
    return Decimal(str(amount))

# 各平台金額解析彙整（避免混淆）
def parse_payment_amount(platform: str, raw_amount: str) -> Decimal:
    """
    統一解析各平台金額，處理單位差異。
    """
    if platform == 'ecpay':
        # 綠界：新台幣整數，單位：元
        return Decimal(str(int(raw_amount)))

    elif platform == 'alipay':
        # 支付寶：人民幣，支援小數點後 2 位，單位：元
        # 範例：'10.00' 代表 10 元
        return Decimal(raw_amount)

    elif platform == 'wechat':
        # 微信支付：人民幣分，整數，單位：分（需除以 100 轉為元）
        # 範例：1000 代表 10 元
        return Decimal(str(int(raw_amount))) / Decimal('100')

    elif platform == '91app':
        # 91app：新台幣整數，單位：元
        return Decimal(str(int(raw_amount)))

    else:
        raise ValueError(f"未知的支付平台：{platform}")
```

**反哺規則：**
```
RULE-ECPAY-002: 解析綠界金額必須使用 int()，禁止除以 100。
  - 掃描模式: TradeAmt.*\/.*100|ecpay.*amount.*0\.01
  - 嚴重度: HIGH
```

---

### PAT-ALIPAY-001：支付寶非同步通知重複處理

**描述：**
支付寶在未收到 `"success"` 回應時會按固定間隔重發 notify_url，共重試 7 次（橫跨約 25 小時）。若後端未實作冪等保護，每次重試都會觸發充值。

**觸發特徵：**

```python
# 錯誤：無冪等保護
@router.post("/payment/notify/alipay")
async def alipay_notify(request: Request):
    params = dict(await request.form())
    if not verify_alipay_signature(params):
        return "fail"

    if params.get('trade_status') == 'TRADE_SUCCESS':
        out_trade_no = params['out_trade_no']
        total_amount = params['total_amount']
        # 每次回調都執行！支付寶會重試 7 次，等於充值 7 次
        await add_points(out_trade_no, Decimal(total_amount))

    return "success"
```

**危害等級：** P0 CRITICAL

**修復策略：**

```python
import redis
from decimal import Decimal

redis_client = redis.Redis(host='redis-host', port=6379, db=0)

# 支付寶重試間隔：2m, 10m, 10m, 1h, 2h, 6h, 15h ≈ 24.5 小時
# TTL 設定為 48 小時，確保覆蓋所有重試窗口
ALIPAY_IDEMPOTENCY_TTL = 172800  # 48 小時（秒）

@router.post("/payment/notify/alipay")
async def alipay_notify(request: Request):
    params = dict(await request.form())

    # 步驟一：驗簽
    if not verify_alipay_signature(params):
        return "fail"

    # 步驟二：僅處理最終成功狀態
    trade_status = params.get('trade_status')
    if trade_status not in ('TRADE_SUCCESS', 'TRADE_FINISHED'):
        return "success"  # 非最終狀態，告知支付寶已收到但不處理

    trade_no = params['trade_no']              # 支付寶交易號
    out_trade_no = params['out_trade_no']      # 我方訂單號

    # 步驟三：Redis 冪等鍵（使用支付寶交易號，更可靠）
    idempotency_key = f"alipay:notify:{trade_no}"
    is_new = redis_client.set(
        idempotency_key,
        "processing",
        nx=True,
        ex=ALIPAY_IDEMPOTENCY_TTL
    )

    if not is_new:
        # 已處理或正在處理，直接回傳 success
        # 讓支付寶停止重試（重要！）
        return "success"

    try:
        total_amount = Decimal(params['total_amount'])

        await process_alipay_payment(
            order_id=out_trade_no,
            trade_no=trade_no,
            amount=total_amount
        )

        redis_client.set(idempotency_key, "completed", ex=ALIPAY_IDEMPOTENCY_TTL)
        return "success"

    except Exception as e:
        # 處理失敗，刪除冪等鍵允許支付寶重試
        redis_client.delete(idempotency_key)
        # 注意：不能回傳 "success"，讓支付寶繼續重試
        return "fail"
```

**反哺規則：**
```
RULE-ALIPAY-001: 支付寶通知端點必須使用 trade_no 作為冪等鍵，TTL >= 48 小時。
  - 掃描模式: /notify/alipay 端點無 redis.*nx=True
  - 嚴重度: CRITICAL
```

---

### PAT-ALIPAY-002：支付寶回調 IP 白名單缺失

**描述：**
支付寶 notify_url 理論上只從其官方 IP 段發送請求。若未設定 IP 白名單，攻擊者知道 notify_url 後可構造偽造請求（即使結合 PAT-PAY-001 的簽章驗證，也應增加 IP 白名單作為縱深防禦）。

**觸發特徵：**

```python
# 錯誤：無 IP 白名單
@router.post("/payment/notify/alipay")
async def alipay_notify(request: Request):
    # 只驗簽，不驗 IP
    params = dict(await request.form())
    if not verify_alipay_signature(params):
        return "fail"
    # ...
```

**危害等級：** P1 HIGH

**修復策略：**

```python
from fastapi import Request, HTTPException
import ipaddress

# 支付寶官方 IP 段（定期從支付寶文件更新）
# 參考：https://opendocs.alipay.com/open/270/105899
ALIPAY_IP_WHITELIST = [
    ipaddress.ip_network('110.75.132.0/24'),
    ipaddress.ip_network('110.75.137.0/24'),
    ipaddress.ip_network('120.55.244.0/24'),
    ipaddress.ip_network('121.204.211.0/24'),
    ipaddress.ip_network('101.36.96.0/24'),
    # ... 完整清單見支付寶文件
]

def is_alipay_ip(client_ip: str) -> bool:
    """驗證請求來源 IP 是否在支付寶白名單內"""
    try:
        ip = ipaddress.ip_address(client_ip)
        return any(ip in network for network in ALIPAY_IP_WHITELIST)
    except ValueError:
        return False

def get_client_ip(request: Request) -> str:
    """取得客戶端真實 IP（考慮負載均衡器）"""
    # 如果有 X-Forwarded-For（Nginx/CDN 轉發）
    forwarded_for = request.headers.get('X-Forwarded-For')
    if forwarded_for:
        # 取最左邊的 IP（最原始的客戶端）
        return forwarded_for.split(',')[0].strip()
    return request.client.host

@router.post("/payment/notify/alipay")
async def alipay_notify(request: Request):
    client_ip = get_client_ip(request)

    # 雙重防禦：IP 白名單 + 簽章驗證
    if not is_alipay_ip(client_ip):
        # 記錄可疑請求，但不回傳錯誤（避免暴露安全策略）
        await log_security_event(
            event_type='ALIPAY_INVALID_IP',
            client_ip=client_ip,
            path=str(request.url)
        )
        # 回傳 200 但不處理（讓攻擊者以為成功，實際上沒有）
        return "success"

    params = dict(await request.form())
    if not verify_alipay_signature(params):
        return "fail"

    # ... 後續業務邏輯
```

**反哺規則：**
```
RULE-ALIPAY-002: 支付寶通知端點必須實作 IP 白名單驗證。
  - 觸發條件: /notify/alipay 端點無 is_alipay_ip 呼叫
  - 嚴重度: HIGH
```

---

### PAT-WECHAT-001：微信支付 prepay_id 重用

**描述：**
微信統一下單（`/v3/pay/transactions/native` 等）返回的 `prepay_id` 有效期為 **2 小時**。前端若緩存此 ID 並在 2 小時後使用，會導致支付失敗；若服務端未處理過期情況，可能陷入靜默失敗。

**觸發特徵：**

```javascript
// 前端錯誤：無限期緩存 prepay_id
const checkoutCache = {};

async function startWechatPayment(orderId) {
    // 用 orderId 作為緩存 key，但 prepay_id 會過期！
    if (checkoutCache[orderId]) {
        launchWechatPay(checkoutCache[orderId]);  // 2 小時後必然失敗
        return;
    }
    const result = await api.post('/payment/wechat/create', { orderId });
    checkoutCache[orderId] = result.prepay_id;  // 危險：沒有過期機制
    launchWechatPay(result.prepay_id);
}
```

```python
# 後端錯誤：不處理 prepay_id 過期
async def get_or_create_prepay_id(order_id: str) -> str:
    order = await Order.objects.aget(id=order_id)
    if order.wechat_prepay_id:
        return order.wechat_prepay_id  # 直接返回，不檢查是否過期！
    # ...
```

**危害等級：** P1 HIGH

**危害說明：**
- 用戶無法完成支付，轉換率下降
- 支付失敗後用戶反覆重試，造成支援壓力
- 多個過期訂單堆積，對帳困難

**修復策略：**

```python
from datetime import datetime, timedelta
import aiohttp

WECHAT_PREPAY_ID_TTL = timedelta(hours=1, minutes=50)  # 提前 10 分鐘過期

async def get_valid_prepay_id(order_id: str) -> str:
    """
    取得有效的 prepay_id，如果已過期則重新下單。
    prepay_id 有效期 2 小時，提前 10 分鐘視為過期。
    """
    order = await Order.objects.aget(id=order_id)

    if (
        order.wechat_prepay_id
        and order.wechat_prepay_created_at
        and timezone.now() - order.wechat_prepay_created_at < WECHAT_PREPAY_ID_TTL
    ):
        return order.wechat_prepay_id

    # 重新向微信下單
    prepay_id = await create_wechat_order(order)

    # 更新 DB 記錄
    await Order.objects.filter(id=order_id).aupdate(
        wechat_prepay_id=prepay_id,
        wechat_prepay_created_at=timezone.now()
    )

    return prepay_id


async def create_wechat_order(order) -> str:
    """向微信統一下單 API 下單"""
    payload = {
        "appid": WECHAT_APP_ID,
        "mchid": WECHAT_MCH_ID,
        "description": f"SWAG 點數購買 - {order.points_to_add} 點",
        "out_trade_no": str(order.id),
        "notify_url": f"{BASE_URL}/payment/notify/wechat",
        "amount": {
            "total": int(order.amount_cny * 100),  # 轉換為分
            "currency": "CNY"
        }
    }

    async with aiohttp.ClientSession() as session:
        response = await session.post(
            "https://api.mch.weixin.qq.com/v3/pay/transactions/native",
            json=payload,
            headers=get_wechat_auth_headers(payload)
        )
        data = await response.json()

    if 'prepay_id' not in data:
        raise WechatPayError(f"微信下單失敗：{data}")

    return data['prepay_id']
```

```javascript
// 前端正確：帶過期時間的緩存
const checkoutCache = {};
const PREPAY_ID_CACHE_TTL = 90 * 60 * 1000; // 90 分鐘（毫秒）

async function startWechatPayment(orderId) {
    const cached = checkoutCache[orderId];
    const now = Date.now();

    // 有緩存且未過期（90分鐘內）
    if (cached && (now - cached.timestamp) < PREPAY_ID_CACHE_TTL) {
        launchWechatPay(cached.prepayId);
        return;
    }

    // 重新向服務端取得 prepay_id（服務端負責判斷是否重新下單）
    const result = await api.post('/payment/wechat/prepay', { orderId });
    checkoutCache[orderId] = {
        prepayId: result.prepay_id,
        timestamp: now
    };
    launchWechatPay(result.prepay_id);
}
```

**反哺規則：**
```
RULE-WECHAT-001: prepay_id 使用前必須驗證是否在 2 小時有效期內。
  - 觸發條件: 直接使用 order.wechat_prepay_id 無過期時間校驗
  - 嚴重度: HIGH
```

---

### PAT-WECHAT-002：微信支付退款非同步問題

**描述：**
微信支付退款操作發起後，退款結果是非同步的（可能需要數分鐘到數小時）。若前端等待即時退款確認，或後端未監聽退款回調，退款狀態將永遠停在「退款中」。

**觸發特徵：**

```python
# 錯誤：同步等待退款結果
async def refund_payment(order_id: str, refund_amount: Decimal):
    # 發起退款請求
    refund_result = await wechat_api.create_refund(order_id, refund_amount)

    # 錯誤：立即認為退款成功
    if refund_result['status'] == 'PROCESSING':
        await mark_order_refunded(order_id)  # 退款還在處理中就標記成功！
        await add_points_back_to_user(order_id)  # 過早歸還點數
```

**危害等級：** P1 HIGH

**修復策略：**

```python
from enum import Enum

class RefundStatus(str, Enum):
    PENDING = 'PENDING'       # 退款申請已提交
    PROCESSING = 'PROCESSING' # 微信處理中
    SUCCESS = 'SUCCESS'       # 退款成功
    FAILED = 'FAILED'         # 退款失敗
    CLOSED = 'CLOSED'         # 退款關閉

# 步驟一：發起退款，狀態設為 PENDING
async def initiate_refund(order_id: str, refund_amount: Decimal) -> str:
    """
    發起微信退款申請。
    注意：此時退款尚未完成，不能立即歸還點數！
    """
    refund_result = await wechat_api.create_refund(
        out_trade_no=order_id,
        refund_amount=int(refund_amount * 100)  # 轉為分
    )

    refund_id = refund_result['refund_id']

    await RefundRecord.objects.acreate(
        order_id=order_id,
        refund_id=refund_id,
        amount=refund_amount,
        status=RefundStatus.PENDING,  # 等待回調
        platform='wechat'
    )

    return refund_id
    # 注意：此處不歸還點數，等退款回調確認後才歸還


# 步驟二：接收微信退款回調
@router.post("/payment/notify/wechat/refund")
async def wechat_refund_notify(request: Request):
    body = await request.body()
    # 解密回調（微信 V3 回調加密）
    callback_data = decrypt_wechat_callback(body, WECHAT_API_V3_KEY)

    if callback_data['refund_status'] == 'SUCCESS':
        refund_id = callback_data['refund_id']

        async with transaction.atomic():
            # 更新退款狀態
            updated = await RefundRecord.objects.filter(
                refund_id=refund_id,
                status__in=[RefundStatus.PENDING, RefundStatus.PROCESSING]
            ).aupdate(
                status=RefundStatus.SUCCESS,
                completed_at=timezone.now()
            )

            if updated > 0:
                # 退款確認後才歸還點數
                refund = await RefundRecord.objects.aget(refund_id=refund_id)
                await return_points_to_user(refund.order_id, refund.amount)

    return {"code": "SUCCESS", "message": "成功"}


# 步驟三：定時查詢（防止回調遺失）
@celery_app.task
def sync_pending_refund_status():
    """定時查詢微信退款狀態，處理回調遺失的情況"""
    pending_refunds = RefundRecord.objects.filter(
        platform='wechat',
        status__in=[RefundStatus.PENDING, RefundStatus.PROCESSING],
        created_at__lt=timezone.now() - timedelta(minutes=30)
    )

    for refund in pending_refunds:
        status = wechat_api.query_refund(refund.refund_id)
        if status == 'SUCCESS' and refund.status != RefundStatus.SUCCESS:
            # 回調遺失，手動觸發退款完成
            complete_refund(refund.id)
```

**反哺規則：**
```
RULE-WECHAT-002: 微信退款後必須等待退款回調，不得同步認為退款成功。
  - 觸發條件: create_refund 呼叫後立即呼叫 add_points 或 return_points
  - 嚴重度: HIGH
```

---

### PAT-91APP-001：91app 訂單狀態同步問題

**描述：**
91app 的訂單狀態更新既有 Webhook 推送，也可能因網路問題導致 Webhook 遺失。若只依賴 Webhook 而不實作主動查詢（polling），部分訂單將永遠停留在「付款中」狀態。

**觸發特徵：**

```python
# 錯誤：只靠 Webhook，無主動查詢
@router.post("/payment/webhook/91app")
async def app91_webhook(request: Request):
    data = await request.json()
    if data['event'] == 'order.paid':
        await process_payment(data['order_id'])
    # 沒有 polling 機制，Webhook 遺失就無法完成
```

**危害等級：** P1 HIGH

**修復策略：**

```python
import aiohttp

# 91app 訂單狀態主動查詢 + Webhook 雙軌機制

@router.post("/payment/webhook/91app")
async def app91_webhook(request: Request):
    """Webhook 接收（主動推送）"""
    data = await request.json()

    if not verify_91app_signature(data, APP91_SECRET):
        return {"status": "invalid_signature"}

    if data['event'] == 'order.paid':
        await handle_91app_order_paid(
            order_id=data['order_id'],
            source='webhook'
        )

    return {"status": "ok"}


@celery_app.task
async def sync_pending_91app_orders():
    """
    定時主動查詢 91app 訂單狀態（每 5 分鐘執行一次）。
    處理 Webhook 未送達的訂單。
    """
    # 查詢超過 10 分鐘仍在待付款狀態的訂單
    pending_orders = await Order.objects.filter(
        platform='91app',
        status='PENDING',
        created_at__lt=timezone.now() - timedelta(minutes=10)
    ).aall()

    async with aiohttp.ClientSession() as session:
        for order in pending_orders:
            try:
                response = await session.get(
                    f"{APP91_API_URL}/orders/{order.platform_order_id}",
                    headers={"Authorization": f"Bearer {APP91_API_TOKEN}"}
                )
                order_data = await response.json()

                if order_data['payment_status'] == 'paid':
                    await handle_91app_order_paid(
                        order_id=str(order.id),
                        source='polling'  # 區分來源，方便除錯
                    )
                elif order_data['payment_status'] in ('cancelled', 'failed'):
                    await Order.objects.filter(id=order.id).aupdate(
                        status='FAILED',
                        failure_reason=order_data.get('failure_reason')
                    )
            except Exception as e:
                await log_error(f"91app 訂單查詢失敗 {order.id}: {e}")


async def handle_91app_order_paid(order_id: str, source: str):
    """
    91app 訂單付款成功處理（含冪等保護）。
    無論來自 webhook 或 polling 都走此函式。
    """
    idempotency_key = f"91app:paid:{order_id}"
    is_new = redis_client.set(idempotency_key, source, nx=True, ex=86400)
    if not is_new:
        return  # 已處理

    try:
        await process_payment_for_order(order_id)
    except Exception:
        redis_client.delete(idempotency_key)
        raise
```

**反哺規則：**
```
RULE-91APP-001: 91app 支付必須同時實作 Webhook 接收和定時主動查詢。
  - 觸發條件: 無 sync_pending_91app_orders celery 任務
  - 嚴重度: HIGH
```

---

### PAT-PAY-COMMON-001：支付超時訂單未清理

**描述：**
用戶進入支付頁面後放棄支付，訂單長期停留在 `PENDING` 狀態。後續用戶想重新購買相同商品時，舊的 PENDING 訂單可能造成點數重複下單或訂單 ID 衝突。

**觸發特徵：**

```python
# 錯誤：創建訂單後無過期機制
async def create_payment_order(user_id: int, amount: Decimal) -> Order:
    order = await Order.objects.acreate(
        user_id=user_id,
        amount=amount,
        status='PENDING'
        # 沒有過期時間！訂單永久存活
    )
    return order
```

**危害等級：** P2 MEDIUM

**修復策略：**

```python
from datetime import timedelta

# 各平台支付超時設定
PAYMENT_TIMEOUT = {
    'ecpay': timedelta(minutes=30),    # 綠界：30 分鐘
    'alipay': timedelta(hours=2),      # 支付寶：2 小時
    'wechat': timedelta(hours=2),      # 微信：2 小時（prepay_id 有效期）
    '91app': timedelta(hours=24),      # 91app：24 小時
}

async def create_payment_order(
    user_id: int,
    amount: Decimal,
    platform: str
) -> Order:
    timeout = PAYMENT_TIMEOUT.get(platform, timedelta(hours=1))

    order = await Order.objects.acreate(
        user_id=user_id,
        amount=amount,
        platform=platform,
        status='PENDING',
        expires_at=timezone.now() + timeout  # 設定過期時間
    )
    return order


@celery_app.task
def cleanup_expired_orders():
    """定時清理超時的 PENDING 訂單"""
    expired_count = Order.objects.filter(
        status='PENDING',
        expires_at__lt=timezone.now()
    ).update(
        status='EXPIRED',
        updated_at=timezone.now()
    )

    if expired_count > 0:
        logger.info(f"已清理 {expired_count} 筆超時訂單")


# 新建訂單前清理舊的 PENDING 訂單
async def ensure_no_duplicate_pending(user_id: int, platform: str):
    """確保用戶沒有重複的 PENDING 訂單"""
    await Order.objects.filter(
        user_id=user_id,
        platform=platform,
        status='PENDING',
        expires_at__lt=timezone.now()
    ).aupdate(status='EXPIRED')
```

**反哺規則：**
```
RULE-PAY-COMMON-001: 訂單創建時必須設定 expires_at，並有定時清理任務。
  - 觸發條件: Order.objects.create 無 expires_at 欄位
  - 嚴重度: MEDIUM
```

---

### PAT-PAY-COMMON-002：退款金額超過原始支付金額

**描述：**
退款時未校驗退款金額上限，允許退款金額超過原始支付金額，造成平台財務損失。

**觸發特徵：**

```python
# 錯誤：未校驗退款上限
async def process_refund(order_id: str, refund_amount: Decimal):
    # 直接退款，不管退款金額是否超過原始金額
    await payment_gateway.refund(order_id, refund_amount)
    await add_points_back(order_id, refund_amount)
```

**危害等級：** P0 CRITICAL

**修復策略：**

```python
from decimal import Decimal

async def process_refund(order_id: str, refund_amount: Decimal) -> bool:
    """
    退款前完整驗證。
    """
    order = await Order.objects.aget(id=order_id, status='PAID')

    # 校驗一：退款金額必須為正數
    if refund_amount <= 0:
        raise ValueError(f"退款金額必須為正數：{refund_amount}")

    # 校驗二：退款金額不得超過原始支付金額
    if refund_amount > order.amount:
        raise RefundExceedsOriginalError(
            f"退款金額 {refund_amount} 超過原始支付金額 {order.amount}"
        )

    # 校驗三：累計退款不得超過原始金額
    total_refunded = await RefundRecord.objects.filter(
        order_id=order_id,
        status='SUCCESS'
    ).aaggregate(total=Sum('amount'))
    already_refunded = total_refunded.get('total') or Decimal('0')

    if already_refunded + refund_amount > order.amount:
        raise RefundExceedsOriginalError(
            f"累計退款 {already_refunded + refund_amount} "
            f"將超過原始金額 {order.amount}"
        )

    # 通過所有校驗，執行退款
    await initiate_refund_on_platform(order, refund_amount)
    return True
```

**反哺規則：**
```
RULE-PAY-COMMON-002: 退款前必須校驗退款金額不超過原始支付金額（含累計退款）。
  - 掃描模式: refund.*amount 函式無 order.amount 比較
  - 嚴重度: CRITICAL
```

---

### PAT-PAY-COMMON-003：跨境匯率未鎖定

**描述：**
SWAG 台灣用戶以新台幣購買，大陸用戶以人民幣購買，系統需處理匯率換算。若訂單創建時未鎖定匯率，在用戶支付的幾分鐘內匯率波動可能導致實際收款金額與訂單金額不符。

**觸發特徵：**

```python
# 錯誤：每次計算都即時查詢匯率
async def calculate_points_for_cny_payment(cny_amount: Decimal) -> int:
    # 每次都即時取匯率，從創建訂單到支付完成期間匯率可能變化
    exchange_rate = await get_current_exchange_rate('CNY', 'TWD')
    twd_amount = cny_amount * exchange_rate
    return int(twd_amount / POINT_PRICE_TWD)
```

**危害等級：** P2 MEDIUM

**修復策略：**

```python
from decimal import Decimal

async def create_cny_payment_order(
    user_id: int,
    cny_amount: Decimal,
    points_requested: int
) -> Order:
    """
    創建人民幣支付訂單，在訂單創建時鎖定匯率。
    """
    # 訂單創建時鎖定當下匯率
    current_rate = await get_current_exchange_rate('CNY', 'TWD')

    # 計算預期點數（基於鎖定匯率）
    locked_twd_amount = cny_amount * current_rate

    order = await Order.objects.acreate(
        user_id=user_id,
        amount_cny=cny_amount,
        amount_twd=locked_twd_amount,
        exchange_rate=current_rate,        # 鎖定匯率存入訂單
        exchange_rate_locked_at=timezone.now(),
        points_to_add=points_requested,    # 鎖定點數數量
        status='PENDING',
        expires_at=timezone.now() + timedelta(hours=2)
    )

    return order


async def complete_payment(order_id: str, actual_cny_received: Decimal):
    """
    支付完成時，使用訂單中鎖定的匯率，不重新計算。
    """
    order = await Order.objects.aget(id=order_id)

    # 允許 1% 匯率浮動容忍範圍（支付平台手續費等因素）
    TOLERANCE = Decimal('0.01')
    min_acceptable = order.amount_cny * (1 - TOLERANCE)

    if actual_cny_received < min_acceptable:
        raise PaymentAmountMismatchError(
            f"實際收款 {actual_cny_received} CNY 低於訂單金額 "
            f"{order.amount_cny} CNY（容忍 {TOLERANCE * 100}%）"
        )

    # 使用訂單記錄的點數（創建時已鎖定），不重新換算
    await add_points_to_user(order.user_id, order.points_to_add)
    await Order.objects.filter(id=order_id).aupdate(status='PAID')
```

**反哺規則：**
```
RULE-PAY-COMMON-003: 跨境支付訂單必須在創建時鎖定匯率，存入 exchange_rate 欄位。
  - 觸發條件: 人民幣訂單無 exchange_rate 欄位
  - 嚴重度: MEDIUM
```

---

## 4. 金流 QA 測試矩陣

### 4.1 Robot Framework 測試案例清單

```robot
*** Settings ***
Library    RequestsLibrary
Library    Collections
Library    DatabaseLibrary
Resource   ../resources/payment_keywords.robot

*** Variables ***
${BASE_URL}    https://staging-api.swag.live
${PAY_API}    ${BASE_URL}/api/v1/payment

*** Test Cases ***

# ---- 綠界 ECPay 測試 ----

PAY-TC-001 綠界簽章驗證阻擋偽造回調
    [Tags]    ecpay    security    critical
    ${fake_callback}=    Create ECPay Callback    order_id=TEST-001    amount=9999
    ${fake_callback}=    Tamper Signature    ${fake_callback}    # 竄改簽章
    ${response}=    POST    ${PAY_API}/callback/ecpay    data=${fake_callback}
    Should Not Equal    ${response.text}    1|OK
    ${points_added}=    Get User Points Change    user_id=${TEST_USER}
    Should Be Equal As Integers    ${points_added}    0    # 不應充值

PAY-TC-002 綠界回調金額比對攔截異常
    [Tags]    ecpay    amount_validation    critical
    # 訂單金額 100 元，但偽造回調金額 9999 元
    ${order_id}=    Create Order    platform=ecpay    amount=100
    ${callback}=    Create Valid ECPay Callback    order_id=${order_id}    amount=9999
    POST    ${PAY_API}/callback/ecpay    data=${callback}
    ${order}=    Get Order    ${order_id}
    Should Be Equal As Strings    ${order['status']}    PENDING    # 不應更新為已付款

PAY-TC-003 綠界重複回調冪等保護
    [Tags]    ecpay    idempotency
    ${order_id}=    Create Order    platform=ecpay    amount=100
    ${callback}=    Create Valid ECPay Callback    order_id=${order_id}    amount=100
    # 連續發送 3 次相同回調
    POST    ${PAY_API}/callback/ecpay    data=${callback}
    POST    ${PAY_API}/callback/ecpay    data=${callback}
    POST    ${PAY_API}/callback/ecpay    data=${callback}
    ${points_added}=    Get User Points Change    user_id=${TEST_USER}
    Should Be Equal    ${points_added}    ${EXPECTED_POINTS}    # 只充值一次

# ---- 支付寶測試 ----

PAY-TC-010 支付寶重複通知冪等保護
    [Tags]    alipay    idempotency    critical
    ${order_id}=    Create Order    platform=alipay    amount_cny=10
    ${notify}=    Create Valid Alipay Notify    order_id=${order_id}
    # 模擬支付寶重發 7 次
    FOR    ${i}    IN RANGE    7
        POST    ${PAY_API}/notify/alipay    data=${notify}
    END
    ${points_added}=    Get User Points Change    user_id=${TEST_USER}
    Should Be Equal    ${points_added}    ${EXPECTED_POINTS}    # 只充值一次

PAY-TC-011 支付寶非白名單IP回調被拒
    [Tags]    alipay    security
    ${notify}=    Create Valid Alipay Notify    order_id=TEST-ALIPAY-001
    ${response}=    POST With Custom IP    ${PAY_API}/notify/alipay
    ...    data=${notify}    ip=1.2.3.4    # 非支付寶IP
    ${points_added}=    Get User Points Change    user_id=${TEST_USER}
    Should Be Equal As Integers    ${points_added}    0

# ---- 微信支付測試 ----

PAY-TC-020 微信prepay_id過期後重新下單
    [Tags]    wechat    prepay_id
    ${order_id}=    Create Order    platform=wechat    amount_cny=10
    ${prepay_id_1}=    Get Prepay Id    order_id=${order_id}
    # 模擬 2 小時後
    Advance Time    hours=2
    ${prepay_id_2}=    Get Prepay Id    order_id=${order_id}
    Should Not Be Equal    ${prepay_id_1}    ${prepay_id_2}    # 應重新下單

PAY-TC-021 微信退款等待回調後才歸還點數
    [Tags]    wechat    refund
    ${order_id}=    Create Paid Order    platform=wechat    amount_cny=10
    Initiate Refund    order_id=${order_id}
    # 退款剛發起，點數不應立即歸還
    ${points}=    Get User Points    user_id=${TEST_USER}
    Should Be Equal    ${points}    ${POINTS_BEFORE_REFUND}    # 點數未變
    # 模擬微信退款回調
    Simulate Wechat Refund Callback    order_id=${order_id}
    ${points_after}=    Get User Points    user_id=${TEST_USER}
    Should Be Equal    ${points_after}    ${POINTS_BEFORE_PURCHASE}    # 點數歸還

# ---- 通用金流測試 ----

PAY-TC-030 退款金額超過原始支付金額被拒
    [Tags]    refund    boundary    critical
    ${order_id}=    Create Paid Order    platform=ecpay    amount=100
    ${response}=    Attempt Refund    order_id=${order_id}    amount=999
    Should Be Equal As Strings    ${response['error']}    REFUND_EXCEEDS_ORIGINAL

PAY-TC-031 超時訂單自動清理
    [Tags]    order_expiry
    ${order_id}=    Create Order    platform=ecpay    amount=100
    Advance Time    minutes=31    # 超過綠界 30 分鐘超時
    Run Celery Task    cleanup_expired_orders
    ${order}=    Get Order    ${order_id}
    Should Be Equal As Strings    ${order['status']}    EXPIRED
```

---

## 5. 金流不變量列表

| ID | 不變量描述 | 適用平台 | 違反嚴重度 |
|----|-----------|---------|-----------|
| INV-PAY-001 | 所有回調必須先驗簽才處理業務邏輯 | 全部 | P0 CRITICAL |
| INV-PAY-002 | 回調金額必須與訂單金額完全一致 | 全部 | P0 CRITICAL |
| INV-PAY-003 | 同一支付交易號只能觸發一次充值 | 全部 | P0 CRITICAL |
| INV-PAY-004 | 退款金額不得超過原始支付金額（含累計） | 全部 | P0 CRITICAL |
| INV-PAY-005 | 所有金額計算使用 Decimal，禁止 float | 全部 | P1 HIGH |
| INV-PAY-006 | 訂單創建後必須設定 expires_at | 全部 | P2 MEDIUM |
| INV-PAY-007 | 支付寶/微信通知冪等 TTL >= 48 小時 | 支付寶、微信 | P0 CRITICAL |
| INV-PAY-008 | 綠界金額為整數元，禁止除以 100 | 綠界 | P1 HIGH |
| INV-PAY-009 | 微信 prepay_id 使用前驗證有效期 | 微信 | P1 HIGH |
| INV-PAY-010 | 微信退款需等退款回調才歸還點數 | 微信 | P1 HIGH |
| INV-PAY-011 | 支付寶回調需驗證來源 IP | 支付寶 | P1 HIGH |
| INV-PAY-012 | 跨境訂單創建時鎖定匯率 | 支付寶、微信 | P2 MEDIUM |

---

## 6. 各平台沙箱環境設定指南

### 6.1 綠界 ECPay 沙箱

**沙箱網址：** https://vendor.ecpay.com.tw（測試環境申請）

**API 端點：**
```
正式：https://payment.ecpay.com.tw/Cashier/AioCheckOut/V5
測試：https://payment-stage.ecpay.com.tw/Cashier/AioCheckOut/V5
```

**測試商家帳號：**
```
MerchantID: 2000132
HashKey:    5294y06JbISpM5x9
HashIV:     v77hoKGq4kWxNNIS
```

**測試信用卡號碼：**
```
Visa:       4311-9522-2222-2222  有效期: 任意未來日期  CVV: 222
Mastercard: 5232-6500-0000-0033  有效期: 任意未來日期  CVV: 033
```

**測試金額限制：** 1 ～ 20,000 元（測試環境不收費）

**回調測試：** 使用 ngrok 或 localtunnel 將本機端口暴露為公開 URL

```bash
# 使用 ngrok 進行本機回調測試
ngrok http 8000
# 取得 URL 如 https://abc123.ngrok.io
# 設定 ECPAY_CALLBACK_URL=https://abc123.ngrok.io/payment/callback/ecpay
```

---

### 6.2 支付寶沙箱

**沙箱網址：** https://sandbox.alipaydev.com

**API 端點：**
```
正式：https://openapi.alipay.com/gateway.do
沙箱：https://openapi.alipaydev.com/gateway.do
```

**沙箱帳號：** 登入 https://openhome.alipay.com 後在「沙箱應用」取得

**Python SDK 設定：**

```python
from alipay import AliPay

# 沙箱環境設定
alipay = AliPay(
    appid="你的沙箱 App ID",
    app_notify_url=None,  # 回調 URL
    app_private_key_string=open("app_private_key.pem").read(),
    alipay_public_key_string=open("alipay_public_key.pem").read(),
    sign_type="RSA2",
    debug=True  # True = 沙箱環境
)
```

**測試金額限制：** 沙箱環境不限金額，但建議用小額（如 0.01 元）

**重要：** 沙箱的 notify_url 必須是公開可訪問的 URL，支付寶沙箱環境也會發送回調。

---

### 6.3 微信支付沙箱

**沙箱網址：** https://pay.weixin.qq.com/wiki/doc/api/tools/simulator.shtml

**API 端點：**
```
正式：https://api.mch.weixin.qq.com
沙箱：https://api.mch.weixin.qq.com/sandboxnew（V2）
      https://api.mch.weixin.qq.com（V3，需特殊 key）
```

**取得沙箱 API key（V2）：**

```python
import requests
import hashlib

def get_sandbox_sign_key(mch_id: str, api_key: str) -> str:
    """取得微信支付沙箱簽章 key"""
    nonce_str = "test1234567"
    raw = f"mch_id={mch_id}&nonce_str={nonce_str}&key={api_key}"
    sign = hashlib.md5(raw.encode()).hexdigest().upper()

    xml_data = f"""
    <xml>
        <mch_id>{mch_id}</mch_id>
        <nonce_str>{nonce_str}</nonce_str>
        <sign>{sign}</sign>
    </xml>"""

    response = requests.post(
        "https://api.mch.weixin.qq.com/sandboxnew/pay/getsignkey",
        data=xml_data.encode('utf-8')
    )
    # 解析返回的沙箱 key
    return parse_sandbox_sign_key(response.text)
```

**測試金額：** 微信支付沙箱測試金額有固定限制，常用測試金額：
- 101 分（1.01 元）：預期支付成功
- 102 分（1.02 元）：預期支付失敗

---

### 6.4 91app 沙箱

**沙箱網址：** https://sandbox.91app.io

**API 端點：**
```
正式：https://api.91app.com
沙箱：https://sandbox-api.91app.io
```

**設定方式：**

```python
# 環境變數設定
APP91_ENV = os.environ.get('APP91_ENV', 'sandbox')
APP91_API_URL = (
    'https://api.91app.com'
    if APP91_ENV == 'production'
    else 'https://sandbox-api.91app.io'
)

# Django settings.py
PAYMENT_GATEWAYS = {
    '91app': {
        'api_url': APP91_API_URL,
        'client_id': os.environ['APP91_CLIENT_ID'],
        'client_secret': os.environ['APP91_CLIENT_SECRET'],
        'shop_id': os.environ['APP91_SHOP_ID'],
    }
}
```

**測試帳號限制：** 需向 91app 業務申請測試商家帳號，沙箱環境不收取任何費用。

---

### 6.5 沙箱環境注意事項

```python
# 環境隔離檢查（防止沙箱設定流入正式環境）
import os

def validate_payment_environment():
    """啟動時驗證支付環境設定正確"""
    env = os.environ.get('APP_ENV', 'development')

    if env == 'production':
        # 正式環境不應有任何沙箱設定
        assert 'sandbox' not in os.environ.get('ECPAY_API_URL', ''), \
            "正式環境不可使用綠界沙箱 URL！"
        assert os.environ.get('ALIPAY_DEBUG', 'false') == 'false', \
            "正式環境不可開啟支付寶 Debug 模式！"
        assert 'sandboxnew' not in os.environ.get('WECHAT_API_URL', ''), \
            "正式環境不可使用微信沙箱 API！"

    elif env in ('development', 'staging'):
        # 測試環境不應使用正式 API
        assert 'payment.ecpay.com.tw' not in os.environ.get('ECPAY_API_URL', ''), \
            "測試環境不可連到綠界正式 API！"
```

---

## 版本歷程

| 版本 | 日期 | 說明 |
|------|------|------|
| 1.0.0 | 2026-06-05 | 初版，涵蓋綠界、91app、支付寶、微信支付完整 Bug Pattern、測試矩陣與沙箱指南 |
