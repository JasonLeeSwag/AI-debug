# 直播平台 Bug 模式知識庫
# SWAG 成人直播平台（swag.live）專用

version: 1.0.0
domain: streaming-platform
platform: swag.live
language: zh-TW

---

## 一、直播平台架構說明

### 1.1 核心功能模組

SWAG 直播平台的核心功能由以下幾個主要模組組成：

**直播串流模組**
- 協議：RTMP（推流）/ HLS（拉流）/ WebRTC（低延遲互動）
- 主播使用 OBS 或手機 App 推流至 RTMP 伺服器
- 觀眾透過 HLS 或 WebRTC 收看直播
- 直播狀態管理：開播、下播、暫停、封禁

**聊天室模組**
- 技術：WebSocket 長連線（FastAPI + asyncio）
- 功能：文字聊天、打賞通知、系統公告、禁言/踢人
- 每個直播間（房間）維護獨立的 WebSocket 連線池

**打賞（送禮物/點數）模組**
- 觸發：用戶選擇禮物 → 前端送出 WebSocket 或 HTTP POST 請求
- 流程：驗證點數餘額 → 扣款 → 通知主播 → 顯示禮物動畫 → 更新分潤帳本
- 禮物種類：虛擬禮物（玫瑰、跑車等），各有不同點數面額與動畫

**訂閱主播模組**
- 月費制：用戶以點數訂閱特定主播，可存取訂閱限定內容
- 自動續訂：訂閱到期前自動扣款，若點數不足則取消訂閱
- 訂閱狀態同步：訂閱開通、到期、取消需即時更新快取

**私密聊天模組**
- 一對一付費視訊聊天，按分鐘計費
- 技術：WebRTC P2P 連線，後端透過 STUN/TURN 中繼
- 計費：每分鐘從用戶帳戶扣除點數

### 1.2 點數（分）系統說明

```
用戶購買點數（法幣 → 點數）
    ↓ 透過綠界/支付寶/微信支付
用戶消費點數
    ├── 打賞（送禮物給主播）
    ├── 訂閱（月費制）
    ├── 私密內容解鎖（單次購買）
    └── 私密聊天（按分計費）
         ↓
主播獲得分潤
    ├── 平台抽成（依等級 30%~50%）
    ├── 主播所得（50%~70%）
    └── 代理商佣金（若透過代理加入）
         ↓
主播出金（點數 → 法幣 → 銀行帳戶）
```

**點數兌換率**：依當前匯率及平台政策，台幣對點數有固定兌換比例。

### 1.3 主播分潤制度

| 主播等級 | 分潤比例 | 晉升條件 |
|---------|---------|---------|
| V1（新人） | 50% | 剛加入 |
| V2（活躍） | 55% | 月收入達門檻 A |
| V3（優質） | 60% | 月收入達門檻 B |
| V4（頂級） | 65% | 月收入達門檻 C + 合約主播 |
| 簽約主播 | 最高 70% | 平台特別合約 |

平台抽成剩餘部分依序分配給代理商（若有）及平台自留。

---

## 二、Bug 模式（Patterns）

### PAT-LIVE-001：打賞 WebSocket 重試導致重複扣款

**類別**：金流安全 / 冪等性  
**危害等級**：P0（用戶多扣款，平台信譽損失）  
**觸發頻率**：網路不穩定環境（東南亞用戶、手機網路切換）  

**問題描述**  
前端 WebSocket 連線因網路波動斷線後，重連邏輯會自動重發上次未收到 ACK 的訊息（包含打賞請求）。若後端未做冪等保護，同一筆打賞會被執行兩次以上。

**觸發特徵**

```javascript
// 前端錯誤範例：重連後直接重送最後一筆訊息
class WebSocketClient {
  constructor(url) {
    this.pendingMessages = [];
    this.connect(url);
  }

  onDisconnect() {
    setTimeout(() => {
      this.connect(this.url);
      // 危險：重發所有 pending 訊息，未檢查是否已成功
      this.pendingMessages.forEach(msg => this.socket.send(msg));
    }, 1000);
  }

  sendGift(giftId, amount) {
    const message = JSON.stringify({ type: 'gift', giftId, amount });
    this.pendingMessages.push(message);  // 加入 pending 佇列
    this.socket.send(message);
  }
}
```

```python
# 後端錯誤範例：無冪等保護
@app.websocket("/ws/room/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: int):
    await websocket.accept()
    async for data in websocket.iter_json():
        if data['type'] == 'gift':
            # 危險：直接扣款，無重複請求檢查
            await deduct_points(user_id, data['amount'])
            await credit_streamer(streamer_id, data['amount'])
```

**修復策略**

```javascript
// 前端正確範例：每次打賞產生唯一 request_id
import { v4 as uuidv4 } from 'uuid';

class WebSocketClient {
  sendGift(giftId, amount) {
    const requestId = uuidv4();  // 唯一識別碼
    const message = JSON.stringify({
      type: 'gift',
      giftId,
      amount,
      requestId,        // 帶入 request_id
      timestamp: Date.now()
    });
    // pending 佇列以 requestId 為鍵，避免重複
    this.pendingMessages.set(requestId, message);
    this.socket.send(message);
  }

  onAck(requestId) {
    // 收到 ACK 後從 pending 移除
    this.pendingMessages.delete(requestId);
  }
}
```

```python
# 後端正確範例：Redis 冪等鍵保護
import redis
import json
from fastapi import WebSocket

redis_client = redis.Redis(host='localhost', port=6379, db=0)
IDEMPOTENCY_TTL = 300  # 5 分鐘內的重複請求視為重複

@app.websocket("/ws/room/{room_id}")
async def websocket_endpoint(websocket: WebSocket, room_id: int):
    await websocket.accept()
    async for data in websocket.iter_json():
        if data['type'] == 'gift':
            request_id = data.get('requestId')
            if not request_id:
                await websocket.send_json({'error': 'missing requestId'})
                continue

            # 冪等鍵檢查
            idempotency_key = f"gift_req:{request_id}"
            if redis_client.exists(idempotency_key):
                # 重複請求，直接回傳上次結果
                cached = redis_client.get(idempotency_key)
                await websocket.send_json(json.loads(cached))
                continue

            # 設定冪等鍵（先設定，避免 TOCTOU 問題）
            redis_client.setex(idempotency_key, IDEMPOTENCY_TTL, 'processing')

            try:
                result = await process_gift(user_id, data['giftId'], data['amount'])
                redis_client.setex(idempotency_key, IDEMPOTENCY_TTL, json.dumps(result))
                await websocket.send_json(result)
            except Exception as e:
                redis_client.delete(idempotency_key)  # 失敗時刪除鍵，允許重試
                raise
```

---

### PAT-LIVE-002：訂閱到期後仍可存取付費內容

**類別**：授權控制 / 快取失效  
**危害等級**：P1（免費存取付費內容，主播收益受損）  
**觸發場景**：訂閱到期瞬間、快取尚未失效期間  

**問題描述**  
FastAPI middleware 快取訂閱狀態以減輕 DB 查詢壓力，但快取未設定足夠短的 TTL，導致訂閱到期後短暫時間內用戶仍可存取付費內容。

**觸發特徵**

```python
# 錯誤範例：快取 TTL 過長，到期後仍有存取權
from functools import lru_cache
import time

# 危險：使用 lru_cache 快取訂閱狀態，沒有時間限制
@lru_cache(maxsize=1000)
def check_subscription(user_id: int, streamer_id: int) -> bool:
    subscription = db.query(Subscription).filter(
        Subscription.user_id == user_id,
        Subscription.streamer_id == streamer_id,
        Subscription.expires_at > datetime.now()
    ).first()
    return subscription is not None

# middleware 中使用快取結果，不重新查詢
@app.middleware("http")
async def subscription_middleware(request: Request, call_next):
    if is_premium_content(request.url.path):
        user_id = get_current_user_id(request)
        streamer_id = get_streamer_id(request.url.path)
        # 危險：快取可能已過期
        if not check_subscription(user_id, streamer_id):
            return JSONResponse(status_code=403, content={'error': 'subscription required'})
    return await call_next(request)
```

**修復策略**

```python
# 正確範例：短 TTL Redis 快取 + 強制重新驗證機制
import redis
import json
from datetime import datetime, timezone

redis_client = redis.Redis(host='localhost', port=6379, db=0)
SUBSCRIPTION_CACHE_TTL = 60  # 最多快取 60 秒

async def check_subscription_with_cache(user_id: int, streamer_id: int) -> dict:
    cache_key = f"sub:{user_id}:{streamer_id}"
    cached = redis_client.get(cache_key)

    if cached:
        data = json.loads(cached)
        # 即使有快取，也要檢查 expires_at 是否已過期
        if datetime.fromisoformat(data['expires_at']) < datetime.now(timezone.utc):
            redis_client.delete(cache_key)  # 主動清除過期快取
            return {'active': False}
        return data

    # 快取不存在，查詢 DB
    subscription = await db.fetch_one(
        "SELECT * FROM subscriptions WHERE user_id=:uid AND streamer_id=:sid",
        {'uid': user_id, 'sid': streamer_id}
    )

    if not subscription:
        result = {'active': False}
    else:
        is_active = subscription.expires_at > datetime.now(timezone.utc)
        result = {
            'active': is_active,
            'expires_at': subscription.expires_at.isoformat()
        }

    redis_client.setex(cache_key, SUBSCRIPTION_CACHE_TTL, json.dumps(result))
    return result

# 強制重新驗證接口（供主播或管理員呼叫）
@app.post("/admin/subscriptions/{user_id}/invalidate-cache")
async def invalidate_subscription_cache(user_id: int):
    pattern = f"sub:{user_id}:*"
    keys = redis_client.keys(pattern)
    if keys:
        redis_client.delete(*keys)
    return {'invalidated': len(keys)}
```

---

### PAT-LIVE-003：主播分潤計算精度問題（Python Decimal）

**類別**：金融計算精度  
**危害等級**：P1（長期積累誤差，可能導致財務對帳差異）  
**觸發場景**：高頻打賞場景、月結算時  

**問題描述**  
主播分潤計算使用 Python `float` 型別，浮點數的二進位表示方式導致累積計算誤差，在月結算時對帳出現差異。

**觸發特徵**

```python
# 錯誤範例：使用 float 計算分潤
def calculate_commission(total_revenue: float, rate: float) -> float:
    commission = total_revenue * rate  # float 乘法，有精度損失
    return round(commission, 2)

# 積累誤差示範
>>> 0.1 + 0.2
0.30000000000000004
>>> 100.0 * 0.6
59.99999999999999  # 應為 60.0
>>> sum(0.1 for _ in range(10))
0.9999999999999999  # 應為 1.0
```

**修復策略**

```python
# 正確範例：使用 Decimal 精確計算
from decimal import Decimal, ROUND_HALF_UP, ROUND_DOWN

def calculate_commission(total_revenue: int, rate: str) -> Decimal:
    """
    計算主播分潤
    :param total_revenue: 總收入（點數，整數）
    :param rate: 分潤比例字串，如 '0.60'
    :return: 分潤金額（Decimal）
    """
    # 金融計算一律使用 Decimal，且從字串建立以避免浮點數轉換問題
    revenue = Decimal(str(total_revenue))
    commission_rate = Decimal(rate)
    commission = revenue * commission_rate

    # 四捨五入至小數點後 2 位（點數通常為整數，依業務需求調整）
    return commission.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP)

# 批次結算時的正確做法
def calculate_monthly_settlement(transactions: list[dict]) -> dict:
    total_revenue = Decimal('0')
    for tx in transactions:
        total_revenue += Decimal(str(tx['amount']))

    platform_rate = Decimal('0.40')  # 平台 40%
    streamer_rate = Decimal('0.60')  # 主播 60%

    platform_cut = total_revenue * platform_rate
    streamer_cut = total_revenue * streamer_rate

    # 驗證：分配總和應等於原始總額
    assert platform_cut + streamer_cut == total_revenue, "分潤加總不等於總額"

    return {
        'total_revenue': total_revenue,
        'platform_cut': platform_cut.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
        'streamer_cut': streamer_cut.quantize(Decimal('0.01'), rounding=ROUND_HALF_UP),
    }
```

---

### PAT-LIVE-004：分潤殘差未處理（Salami 問題）

**類別**：金融計算精度 / 捨入誤差  
**危害等級**：P1（財務對帳差異，長期積累可能超過容許範圍）  
**觸發場景**：三方分潤計算（平台 + 主播 + 代理商）  

**問題描述**  
當一筆金額需分配給三方時，各方分別計算自己的比例並四捨五入，三方金額加總後可能不等於原始總額，產生殘差（Salami 問題）。

**觸發特徵**

```python
# 錯誤範例：各方各自四捨五入，總和不等於原始金額
total = Decimal('100.00')
platform_rate = Decimal('0.35')
streamer_rate = Decimal('0.60')
agent_rate = Decimal('0.05')

platform_cut = round(total * platform_rate, 2)  # 35.00
streamer_cut = round(total * streamer_rate, 2)   # 60.00
agent_cut = round(total * agent_rate, 2)          # 5.00

# 看起來沒問題，但換個數字：
total2 = Decimal('100.01')
platform_cut2 = round(total2 * platform_rate, 2)  # 35.00 (35.0035)
streamer_cut2 = round(total2 * streamer_rate, 2)   # 60.01 (60.006)
agent_cut2 = round(total2 * agent_rate, 2)          # 5.00 (5.0005)
# 35.00 + 60.01 + 5.00 = 100.01 ✓ 這次對了

# 但某些數字組合下：
total3 = Decimal('10.00')
# platform=3.50, streamer=6.00, agent=0.50 → 10.00 ✓
# 換成 9.99：
total4 = Decimal('9.99')
# platform=3.50 (3.4965), streamer=5.99 (5.994), agent=0.50 (0.4995)
# 3.50 + 5.99 + 0.50 = 9.99 ✓
# 但 3.4965 → 3.50（無條件進位），5.994 → 5.99（捨去），0.4995 → 0.50（進位）
# 3.50 + 5.99 + 0.50 = 9.99 ✓ 恰好對了

# 問題在大量交易累積時：殘差 ±0.01 在百萬筆交易後可能累積成可觀金額
```

**修復策略（最大餘額法）**

```python
# 正確範例：最後一方吃殘差
from decimal import Decimal, ROUND_DOWN

def distribute_revenue(total: Decimal, rates: list[dict]) -> list[dict]:
    """
    三方分潤計算（最大餘額法）
    :param total: 總金額
    :param rates: [{'party': 'platform', 'rate': '0.35'}, ...]
    :return: 每方分配金額列表
    """
    results = []
    allocated = Decimal('0')

    # 前 N-1 方：無條件捨去（保守計算）
    for rate_info in rates[:-1]:
        rate = Decimal(rate_info['rate'])
        # 無條件捨去，避免超額分配
        amount = (total * rate).quantize(Decimal('0.01'), rounding=ROUND_DOWN)
        results.append({
            'party': rate_info['party'],
            'amount': amount
        })
        allocated += amount

    # 最後一方：吃掉所有殘差（總額減去已分配金額）
    last_party = rates[-1]
    last_amount = total - allocated  # 確保加總等於 total
    results.append({
        'party': last_party['party'],
        'amount': last_amount
    })

    # 驗算
    total_distributed = sum(r['amount'] for r in results)
    assert total_distributed == total, f"分潤加總 {total_distributed} ≠ 總額 {total}"

    return results

# 使用範例
rates = [
    {'party': 'platform', 'rate': '0.35'},
    {'party': 'agent', 'rate': '0.05'},
    {'party': 'streamer', 'rate': '0.60'},  # 最後一方吃殘差
]
result = distribute_revenue(Decimal('100.01'), rates)
```

---

### PAT-LIVE-005：直播觀看人數竄改

**類別**：資料完整性 / 用戶端信任問題  
**危害等級**：P2（影響主播排行榜公平性，可能造成廣告費用計算錯誤）  
**觸發場景**：惡意主播或競爭對手刷人氣  

**問題描述**  
若服務端接受客戶端提交的觀看人數更新，惡意用戶可透過 WebSocket 偽造高觀看人數，影響主播排行榜與廣告收費計算。

**觸發特徵**

```python
# 錯誤範例：後端直接信任客戶端傳來的人數
@app.websocket("/ws/room/{room_id}")
async def room_ws(websocket: WebSocket, room_id: int):
    await websocket.accept()
    async for data in websocket.iter_json():
        if data['type'] == 'update_viewers':
            # 危險：直接使用客戶端提供的人數
            await redis_client.set(f"room:{room_id}:viewers", data['count'])
```

**修復策略**

```python
# 正確範例：服務端主導人數統計
import asyncio
from collections import defaultdict

# 服務端自行追蹤連線數
room_connections: dict[int, set] = defaultdict(set)

@app.websocket("/ws/room/{room_id}")
async def room_ws(websocket: WebSocket, room_id: int, user_id: int):
    await websocket.accept()

    # 加入房間，服務端自行計數
    room_connections[room_id].add(user_id)
    viewer_count = len(room_connections[room_id])
    await redis_client.set(f"room:{room_id}:viewers", viewer_count)
    await broadcast_viewer_count(room_id, viewer_count)

    try:
        async for data in websocket.iter_json():
            if data['type'] == 'update_viewers':
                # 拒絕客戶端自行更新人數
                await websocket.send_json({
                    'error': 'viewer_count is managed by server'
                })
            # 其他合法訊息處理...
    finally:
        # 離開房間，自動扣減計數
        room_connections[room_id].discard(user_id)
        viewer_count = len(room_connections[room_id])
        await redis_client.set(f"room:{room_id}:viewers", viewer_count)
        await broadcast_viewer_count(room_id, viewer_count)

async def broadcast_viewer_count(room_id: int, count: int):
    """廣播正確的觀看人數給所有連線用戶"""
    message = json.dumps({'type': 'viewer_count', 'count': count})
    for connection in room_connections[room_id]:
        # 透過 connection manager 發送...
        pass
```

---

### PAT-LIVE-006：私密聊天/付費內容 URL 預測

**類別**：內容存取控制 / URL 安全  
**危害等級**：P1（付費內容洩漏，主播收益損失）  
**觸發場景**：媒體 CDN URL 被爬取或分享  

**問題描述**  
付費影片或圖片使用可預測的序號 URL（如 `/content/123`），任何人猜到 URL 即可免費存取付費內容。

**觸發特徵**

```python
# 錯誤範例：使用可預測的媒體 URL
@app.get("/content/{content_id}")
async def get_content(content_id: int):
    content = db.query(Content).filter(Content.id == content_id).first()
    # 危險：未驗證用戶是否有存取權限
    return FileResponse(content.file_path)

# URL 形如：https://cdn.swag.live/content/123
# 攻擊者可直接嘗試 /content/124, /content/125...
```

**修復策略**

```python
# 正確範例：簽章 URL + 存取驗證
import hmac
import hashlib
import time
from urllib.parse import urlencode

SECRET_KEY = "your-secret-key-from-env"
URL_EXPIRY_SECONDS = 3600  # 1 小時有效

def generate_signed_url(content_id: int, user_id: int) -> str:
    """產生含簽章的媒體存取 URL"""
    expires = int(time.time()) + URL_EXPIRY_SECONDS
    params = {
        'content_id': content_id,
        'user_id': user_id,
        'expires': expires,
    }

    # 計算 HMAC 簽章
    message = urlencode(sorted(params.items()))
    signature = hmac.new(
        SECRET_KEY.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()

    params['sig'] = signature
    return f"https://cdn.swag.live/media?{urlencode(params)}"

@app.get("/api/content/{content_id}/access-url")
async def get_content_access_url(
    content_id: int,
    current_user: User = Depends(get_current_user)
):
    # 驗證用戶是否有存取此內容的權限
    has_access = await verify_content_access(current_user.id, content_id)
    if not has_access:
        raise HTTPException(status_code=403, detail="付費內容，請先訂閱")

    signed_url = generate_signed_url(content_id, current_user.id)
    return {'url': signed_url, 'expires_in': URL_EXPIRY_SECONDS}

# 媒體伺服器驗證簽章（或 CloudFront signed URL）
@app.get("/media")
async def serve_media(content_id: int, user_id: int, expires: int, sig: str):
    # 驗證是否過期
    if int(time.time()) > expires:
        raise HTTPException(status_code=403, detail="連結已過期，請重新取得")

    # 驗證簽章
    params = {'content_id': content_id, 'user_id': user_id, 'expires': expires}
    message = urlencode(sorted(params.items()))
    expected_sig = hmac.new(SECRET_KEY.encode(), message.encode(), hashlib.sha256).hexdigest()

    if not hmac.compare_digest(sig, expected_sig):
        raise HTTPException(status_code=403, detail="無效的存取連結")

    # 返回媒體內容...
```

---

### PAT-LIVE-007：點數送禮後主播未入帳（事務邊界問題）

**類別**：資料庫事務 / 資料一致性  
**危害等級**：P0（用戶點數被扣，主播未收到分潤，財務資料不一致）  
**觸發場景**：送禮時資料庫分區、主播 DB 短暫不可用  

**問題描述**  
Django ORM 在兩個不同的資料庫操作（扣用戶點數、入主播分潤帳）未在同一事務中執行，若第二個操作失敗，用戶點數已扣但主播未入帳。

**觸發特徵**

```python
# 錯誤範例：兩個 DB 操作不在同一事務中
def process_gift(user_id: int, streamer_id: int, gift_amount: int):
    # 步驟 1：扣除用戶點數
    user = User.objects.get(id=user_id)
    user.points -= gift_amount
    user.save()  # 已提交

    # 危險：如果這裡失敗，用戶點數已扣但主播未入帳
    notification_service.send_gift_alert(streamer_id, gift_amount)  # 可能超時

    # 步驟 2：增加主播分潤
    commission = gift_amount * 0.6
    streamer_wallet = StreamerWallet.objects.get(streamer_id=streamer_id)
    streamer_wallet.balance += commission
    streamer_wallet.save()  # 可能失敗
```

**修復策略**

```python
# 正確範例：使用 Django 事務裝飾器 + 補償機制
from django.db import transaction
from django.db.models import F
import logging

logger = logging.getLogger(__name__)

@transaction.atomic
def process_gift(user_id: int, streamer_id: int, gift_amount: int) -> dict:
    """
    處理送禮流程，確保原子性
    使用 F() 表達式避免競態條件
    """
    try:
        # 在事務中，使用 select_for_update() 加行鎖
        user = User.objects.select_for_update().get(id=user_id)

        if user.points < gift_amount:
            raise ValueError(f"點數不足：現有 {user.points}，需要 {gift_amount}")

        # 步驟 1：扣除用戶點數（使用 F() 避免競態條件）
        User.objects.filter(id=user_id).update(points=F('points') - gift_amount)

        # 步驟 2：計算並入帳主播分潤（同一事務）
        commission = int(gift_amount * 0.6)
        StreamerWallet.objects.filter(streamer_id=streamer_id).update(
            balance=F('balance') + commission
        )

        # 步驟 3：記錄點數流水（同一事務）
        PointTransaction.objects.create(
            user_id=user_id,
            amount=-gift_amount,
            type='gift',
            reference_id=f"gift:{user_id}:{streamer_id}:{gift_amount}"
        )

        CommissionRecord.objects.create(
            streamer_id=streamer_id,
            amount=commission,
            source_type='gift',
            user_id=user_id
        )

        return {'success': True, 'commission': commission}

    except Exception as e:
        logger.error(f"送禮失敗 user={user_id} streamer={streamer_id} amount={gift_amount}: {e}")
        # transaction.atomic 會自動回滾
        raise

# 補償機制：若事務外的非核心操作失敗，記錄至重試佇列
def process_gift_with_compensation(user_id: int, streamer_id: int, gift_amount: int):
    result = process_gift(user_id, streamer_id, gift_amount)

    # 事務成功後，發送非核心通知（失敗不影響金流）
    try:
        notification_service.send_gift_alert(streamer_id, gift_amount)
    except Exception as e:
        logger.warning(f"送禮通知發送失敗（金流已完成）: {e}")
        # 加入重試佇列（Celery task）
        retry_notification.delay(streamer_id, gift_amount)

    return result
```

---

### PAT-LIVE-008：NSFW 內容年齡驗證繞過

**類別**：法規合規 / 存取控制  
**危害等級**：P0（法規違規，可能導致平台被迫下架）  
**觸發場景**：直接呼叫 API 繞過前端年齡驗證頁面  

**問題描述**  
成人內容的年齡驗證（18+）僅在前端頁面進行，後端 API 未做驗證，攻擊者可直接呼叫 API 繞過年齡限制存取 NSFW 內容。

**觸發特徵**

```javascript
// 前端錯誤範例：僅前端做年齡驗證
function AgeGate() {
  const [verified, setVerified] = useState(false);

  if (!verified) {
    return (
      <div>
        <button onClick={() => setVerified(true)}>我已滿18歲</button>
      </div>
    );
  }
  // 驗證通過後顯示內容
  return <NSFWContent />;
}

// 攻擊者直接呼叫 API：curl https://api.swag.live/streams/live
// 完全繞過前端年齡驗證
```

**修復策略**

```python
# 正確範例：後端中介軟體強制年齡驗證
from fastapi import Depends, HTTPException, Request
from fastapi.security import HTTPBearer

security = HTTPBearer()

async def verify_age_confirmed(
    request: Request,
    token: str = Depends(security)
) -> User:
    """
    後端年齡驗證中介軟體
    - 檢查 JWT token 中的 age_verified 欄位
    - 或查詢用戶資料庫中的年齡驗證狀態
    """
    current_user = await get_current_user(token)

    if not current_user.age_verified:
        raise HTTPException(
            status_code=403,
            detail={
                'error': 'age_verification_required',
                'message': '請先完成年齡驗證（18+）',
                'verification_url': '/api/auth/age-verify'
            }
        )

    return current_user

# 所有 NSFW 路由都必須依賴 verify_age_confirmed
@app.get("/api/streams/live", dependencies=[Depends(verify_age_confirmed)])
async def get_live_streams():
    return await fetch_live_streams()

@app.get("/api/content/{content_id}", dependencies=[Depends(verify_age_confirmed)])
async def get_nsfw_content(content_id: int):
    return await fetch_content(content_id)

# 年齡驗證流程（需實名驗證或信用卡驗證）
@app.post("/api/auth/age-verify")
async def verify_age(
    verification_data: AgeVerificationRequest,
    current_user: User = Depends(get_current_user)
):
    # 1. 驗證身分證字號（台灣居民）或護照
    # 2. 或透過信用卡驗證（僅台灣金融機構發行的信用卡）
    # 3. 記錄驗證時間戳與方法
    result = await age_verification_service.verify(
        user_id=current_user.id,
        method=verification_data.method,
        data=verification_data.data
    )

    if result.success:
        await User.objects.filter(id=current_user.id).update(
            age_verified=True,
            age_verified_at=datetime.now(timezone.utc),
            age_verification_method=verification_data.method
        )

    return result
```

---

## 三、直播平台 QA 測試矩陣

### Robot Framework 測試案例

```robot
*** Settings ***
Library          RequestsLibrary
Library          WebSocketClient
Library          Collections
Library          DateTime
Resource         ../resources/swag-common.resource
Suite Setup      Initialize Test Environment
Suite Teardown   Cleanup Test Data

*** Variables ***
${BASE_URL}      %{SWAG_API_BASE_URL}
${WS_URL}        %{SWAG_WS_URL}
${TEST_USER_ID}  %{TEST_USER_ID}
${TEST_STREAMER} %{TEST_STREAMER_ID}

*** Test Cases ***

# ---- TC-LIVE-001：打賞正常路徑 ----
TC-LIVE-001 用戶成功打賞主播並扣除點數
    [Documentation]    驗證打賞流程完整性：扣款、主播入帳、流水記錄
    [Tags]    gift    p0    smoke
    ${initial_points}=    Get User Points    ${TEST_USER_ID}
    ${initial_balance}=   Get Streamer Balance    ${TEST_STREAMER}
    ${gift_amount}=       Set Variable    100

    Send Gift Via WebSocket    ${TEST_USER_ID}    ${TEST_STREAMER}    ${gift_amount}
    Wait Until Keyword Succeeds    10s    1s    Verify Gift Processed    ${TEST_USER_ID}

    ${final_points}=    Get User Points    ${TEST_USER_ID}
    ${final_balance}=   Get Streamer Balance    ${TEST_STREAMER}

    Should Be Equal As Numbers    ${final_points}    ${initial_points - ${gift_amount}}
    Should Be Equal As Numbers    ${final_balance}    ${initial_balance + ${gift_amount * 0.6}}
    Verify Transaction Record Exists    ${TEST_USER_ID}    gift    ${gift_amount}

# ---- TC-LIVE-002：打賞點數不足 ----
TC-LIVE-002 點數不足時打賞應失敗並提示
    [Documentation]    驗證點數不足時打賞被拒絕，且用戶點數未變動
    [Tags]    gift    negative    p0
    Set User Points    ${TEST_USER_ID}    10    # 設定點數為 10
    ${initial_points}=    Get User Points    ${TEST_USER_ID}

    ${response}=    Send Gift Request    ${TEST_USER_ID}    ${TEST_STREAMER}    100
    Should Be Equal As Strings    ${response['error']}    insufficient_points
    ${final_points}=    Get User Points    ${TEST_USER_ID}
    Should Be Equal As Numbers    ${final_points}    ${initial_points}    # 點數未變動

# ---- TC-LIVE-003：WebSocket 重連冪等性 ----
TC-LIVE-003 WebSocket 斷線重連後重送打賞不重複扣款
    [Documentation]    驗證重連後重送相同 request_id 的打賞不會重複扣款
    [Tags]    gift    websocket    idempotency    p0
    ${initial_points}=    Get User Points    ${TEST_USER_ID}
    ${request_id}=    Generate UUID

    # 第一次送出
    Send Gift With Request ID    ${TEST_USER_ID}    ${TEST_STREAMER}    100    ${request_id}
    Wait Until Gift Processed    ${request_id}

    # 模擬重連後重送相同 request_id
    Send Gift With Request ID    ${TEST_USER_ID}    ${TEST_STREAMER}    100    ${request_id}
    Sleep    2s    # 等待可能的重複處理

    ${final_points}=    Get User Points    ${TEST_USER_ID}
    # 點數只扣一次（冪等性驗證）
    Should Be Equal As Numbers    ${final_points}    ${initial_points - 100}

# ---- TC-LIVE-004：訂閱開通正常路徑 ----
TC-LIVE-004 用戶成功訂閱主播並開通付費內容存取
    [Documentation]    驗證訂閱開通後可存取訂閱限定內容
    [Tags]    subscription    p0    smoke
    ${points_before}=    Get User Points    ${TEST_USER_ID}
    ${sub_price}=        Get Subscription Price    ${TEST_STREAMER}

    Subscribe To Streamer    ${TEST_USER_ID}    ${TEST_STREAMER}
    Wait Until Subscription Active    ${TEST_USER_ID}    ${TEST_STREAMER}

    ${points_after}=    Get User Points    ${TEST_USER_ID}
    Should Be Equal As Numbers    ${points_after}    ${points_before - ${sub_price}}

    # 驗證可存取訂閱內容
    ${response}=    Access Premium Content    ${TEST_USER_ID}    ${TEST_STREAMER}
    Should Be Equal As Integers    ${response.status_code}    200

# ---- TC-LIVE-005：訂閱到期後無法存取付費內容 ----
TC-LIVE-005 訂閱到期後應無法存取訂閱限定內容
    [Documentation]    驗證訂閱到期後內容存取被拒絕
    [Tags]    subscription    p1    expiry
    # 建立已過期訂閱（直接寫入 DB 設定過期時間）
    Create Expired Subscription    ${TEST_USER_ID}    ${TEST_STREAMER}

    ${response}=    Access Premium Content    ${TEST_USER_ID}    ${TEST_STREAMER}
    Should Be Equal As Integers    ${response.status_code}    403
    Should Contain    ${response.json()['error']}    subscription required

# ---- TC-LIVE-006：主播分潤驗算 ----
TC-LIVE-006 主播分潤計算正確性驗算
    [Documentation]    驗證打賞後主播分潤金額計算正確，無浮點精度問題
    [Tags]    commission    p1    calculation
    ${test_amounts}=    Create List    100    99    333    1000    7
    FOR    ${amount}    IN    @{test_amounts}
        ${before_balance}=    Get Streamer Balance    ${TEST_STREAMER}
        Send Gift    ${TEST_USER_ID}    ${TEST_STREAMER}    ${amount}
        Wait Until Gift Processed
        ${after_balance}=    Get Streamer Balance    ${TEST_STREAMER}

        ${expected_commission}=    Calculate Expected Commission    ${amount}    0.6
        ${actual_increment}=    Evaluate    ${after_balance} - ${before_balance}
        Should Be Equal As Numbers    ${actual_increment}    ${expected_commission}
    END

# ---- TC-LIVE-007：年齡驗證繞過防護 ----
TC-LIVE-007 未完成年齡驗證的用戶無法存取 NSFW 內容
    [Documentation]    驗證 API 層年齡驗證，防止前端繞過
    [Tags]    age-verification    compliance    p0
    ${unverified_token}=    Get Unverified User Token

    # 直接呼叫 API（繞過前端）
    ${headers}=    Create Dictionary    Authorization=Bearer ${unverified_token}
    ${response}=    GET    ${BASE_URL}/api/streams/live    headers=${headers}
    Should Be Equal As Integers    ${response.status_code}    403
    Should Be Equal As Strings    ${response.json()['error']}    age_verification_required

# ---- TC-LIVE-008：私密聊天計費 ----
TC-LIVE-008 私密聊天按分鐘正確扣款
    [Documentation]    驗證私密聊天每分鐘扣款正確
    [Tags]    private-chat    billing    p0
    ${initial_points}=    Get User Points    ${TEST_USER_ID}
    ${rate_per_minute}=    Get Private Chat Rate    ${TEST_STREAMER}

    Start Private Chat    ${TEST_USER_ID}    ${TEST_STREAMER}
    Sleep    65s    # 等待超過 1 分鐘
    End Private Chat    ${TEST_USER_ID}    ${TEST_STREAMER}

    ${final_points}=    Get User Points    ${TEST_USER_ID}
    ${deducted}=    Evaluate    ${initial_points} - ${final_points}
    Should Be True    ${deducted} >= ${rate_per_minute}    # 至少扣一分鐘費用

# ---- TC-LIVE-009：直播觀看人數服務端統計 ----
TC-LIVE-009 觀看人數不可被客戶端竄改
    [Documentation]    驗證服務端拒絕客戶端提交的觀看人數更新
    [Tags]    viewer-count    security    p2
    Connect To Room WebSocket    ${TEST_USER_ID}    ${TEST_STREAMER}
    ${initial_count}=    Get Room Viewer Count    ${TEST_STREAMER}

    # 嘗試透過 WebSocket 偽造觀看人數
    Send WebSocket Message    {"type": "update_viewers", "count": 99999}
    Sleep    2s

    ${current_count}=    Get Room Viewer Count    ${TEST_STREAMER}
    Should Not Be Equal As Numbers    ${current_count}    99999
    # 驗證收到錯誤回應
    ${last_message}=    Get Last WebSocket Message
    Should Contain    ${last_message}    viewer_count is managed by server

# ---- TC-LIVE-010：付費內容 URL 安全性 ----
TC-LIVE-010 付費內容 URL 需有效簽章才可存取
    [Documentation]    驗證未簽章或過期簽章的媒體 URL 被拒絕
    [Tags]    content-security    p1
    # 嘗試直接存取可預測的 URL
    ${response}=    GET    ${BASE_URL}/content/1
    Should Not Be Equal As Integers    ${response.status_code}    200

    # 嘗試使用過期簽章
    ${expired_url}=    Generate Expired Signed URL    1    ${TEST_USER_ID}
    ${response2}=    GET    ${expired_url}
    Should Be Equal As Integers    ${response2.status_code}    403

    # 正常取得簽章 URL 並存取
    ${valid_url}=    Get Content Access URL    ${TEST_USER_ID}    1
    ${response3}=    GET    ${valid_url}
    Should Be Equal As Integers    ${response3.status_code}    200
```

---

## 四、直播平台不變量列表（INV-LIVE 系列）

| 不變量 ID | 描述 | 觸發條件 | 驗證方式 |
|----------|------|---------|---------|
| INV-LIVE-001 | 用戶點數餘額不可為負數 | 任何扣款操作後 | DB 約束 CHECK (points >= 0) |
| INV-LIVE-002 | 打賞後用戶點數減少量 = 禮物面額（分文不差） | 每次送禮後 | 事務後讀取驗算 |
| INV-LIVE-003 | 打賞後主播分潤增加量 = 禮物面額 × 分潤比例（無浮點誤差） | 每次送禮後 | Decimal 精確計算 |
| INV-LIVE-004 | 三方分潤加總 = 禮物面額（殘差由最後一方吸收） | 分潤分配計算時 | assert sum(parts) == total |
| INV-LIVE-005 | 訂閱到期後 60 秒內必須無法存取訂閱限定內容 | 訂閱到期後 | 定時監控 + 快取 TTL 上限 60 秒 |
| INV-LIVE-006 | 每個打賞請求的 request_id 在 5 分鐘內只能被處理一次 | WebSocket 重連重送時 | Redis 冪等鍵 |
| INV-LIVE-007 | 未完成年齡驗證的用戶 API 呼叫必須回傳 403 | 所有 NSFW 路由 | 中介軟體強制檢查 |
| INV-LIVE-008 | 直播觀看人數只由服務端統計，不接受客戶端提交 | 任何人數相關請求 | 服務端連線數計算 |
| INV-LIVE-009 | 付費媒體 URL 必須包含有效簽章且未過期 | 媒體存取請求 | HMAC 驗證 + 過期時間檢查 |
| INV-LIVE-010 | 同一筆點數流水記錄的借貸方必須平衡（雙式記帳） | 點數異動時 | 事務後驗算 debit == credit |

---

*最後更新：2026-06-05*  
*適用版本：SWAG 直播平台 v2.x+*
