---
file_id: payment-checklist
kind: reference
status: active
schema_version: 1.0
last_reviewed: 2026-06-05
stale_after_days: 180
owner: swag-qa-team
external_refs: ["ecpay", "alipay", "wxpay", "91app"]
---

# SWAG 支付與點數系統 PR 檢查清單

> 適用範圍：所有涉及點數充值、扣減、支付回調、打賞、出金的程式碼變更
> 每次相關 PR 合併前，提交者自檢、審查者複核，兩方都須完成標記
> 通過基準：第 1～15 項（核心安全）全部通過方可合併；其餘不通過須說明

---

## 一、點數計算（Decimal 精度）

```
[ ] 1. 所有點數計算使用 Python Decimal，不使用 float 或 int 轉換的中間步驟
        → 違規：float(amount) * rate、amount * 1.95
        → 正確：Decimal(str(amount)) * Decimal('1.95')

[ ] 2. Decimal 除法指定 quantize() 和 ROUND_HALF_DOWN（或明確的 RoundingMode）
        → 違規：Decimal('100') / Decimal('3')（無 quantize，可能引發 InvalidOperation）
        → 正確：(Decimal('100') / Decimal('3')).quantize(Decimal('0.01'), rounding=ROUND_HALF_DOWN)

[ ] 3. 多方分潤（主播/平台/稅）使用最大餘額法，確保加總守恆
        → 違規：每方都乘以比例再 quantize（加總可能差 0.01）
        → 正確：先算次要方，最大方拿剩餘（streamer = total - platform - tax）

[ ] 4. 點數與法幣的匯率轉換有明確的精度規則
        → 文件化：1 元 = ? 點數，精度到哪一位，無法整除時如何取整
        → 測試覆蓋：0.01 元、99.99 元等邊界值的轉換結果
```

---

## 二、支付回調安全（綠界/支付寶/微信支付/91app）

```
[ ] 5. 回調入口驗證簽章（各平台各自的驗簽邏輯）
        → 綠界 ECPay：SHA256（HashKey + ASCII 排序參數 + HashIV + URL Encode 轉小寫）
        → 支付寶：RSA2 公鑰驗簽（sign 欄位），驗後還需確認 app_id 是我方 APP
        → 微信支付 v2：HMAC-SHA256 + API_KEY；v3：RSA-SHA256 + 微信平台公鑰
        → 91app：HMAC 簽章 + Token 驗證
        → 驗簽失敗立即 return，不繼續執行任何業務邏輯

[ ] 6. 回調金額與訂單金額嚴格比對（Decimal 精度比對）
        → 違規：只驗簽不比對金額
        → 正確：assert Decimal(str(callback_amount)) == order.amount
        → 金額不符：記錄完整日誌、觸發告警、返回失敗、不充值

[ ] 7. 微信支付金額單位為「分」（整數），非「元」
        → 下單時：total_fee = yuan_to_fen(order.amount)（Decimal 轉換，非 float * 100）
        → 回調時：callback_yuan = Decimal(callback_fen) / Decimal('100') 後再比對

[ ] 8. 支付寶回調來源 IP 在白名單內
        → 支付寶官方 IP 段需定期更新（目前正式環境：103.0.96.0/24 等）
        → IP 白名單驗證在簽章驗證之前執行（快速拒絕非法來源）
        → 白名單 IP 段儲存於設定檔，不硬編碼在程式碼中

[ ] 9. 回調使用冪等保護（使用支付平台的交易號作為冪等鍵）
        → 冪等鍵：pay_callback:{platform}:{platform_trade_no}
        → Redis setex（nx=True），TTL 24 小時（成功後延長至 7 天）
        → 同時以資料庫訂單狀態作為第二層冪等保護
        → 業務失敗時刪除 Redis key，允許支付平台重試

[ ] 10. 回調返回正確格式（各平台期望的格式）
        → 綠界 ECPay：成功返回字串 "1|OK"（30 秒內回傳）
        → 支付寶：成功返回字串 "success"，失敗返回 "fail"
        → 微信支付 v2：成功返回 XML {"return_code": "SUCCESS", "return_msg": "OK"}
        → 微信支付 v3：成功返回 HTTP 200，body 為 {"code": "SUCCESS"}
        → 逾時或錯誤格式：支付寶/微信會重試，確保冪等保護到位
```

---

## 三、並發安全與冪等性

```
[ ] 11. 點數充值操作有 Redis setex 冪等鍵（key 包含 transaction_id 或 request_id）
        → key 格式：charge:v1:{user_id}:{request_id}（包含版本號，方便升級）
        → nx=True（setex 必須是原子操作），TTL 建議 24 小時
        → 冪等鍵的 request_id 由前端生成 UUID v4，不由後端生成

[ ] 12. 點數扣減使用原子 SQL（UPDATE ... WHERE points >= amount）
        → 違規：先 SELECT 查餘額，再 UPDATE 扣款（兩步非原子）
        → 正確：UPDATE users SET points = points - %s WHERE id = %s AND points >= %s
        → 更新 0 rows = 餘額不足，拋出 InsufficientPointsError

[ ] 13. 博弈結算使用分散式鎖（Redis lock）
        → lock key：settle_lock:round:{round_id}
        → timeout = 30 秒（不超過業務 SLA 的 50%）
        → 取鎖後再次確認 round 狀態，防止重複結算

[ ] 14. 打賞/送禮操作有 request_id 冪等保護
        → WebSocket 打賞消息必須包含前端生成的 request_id
        → key 格式：gift:v1:{user_id}:{request_id}，TTL 1 小時
        → 前端 WebSocket 重連後不自動重送打賞消息

[ ] 15. 冪等鍵失敗清理：業務失敗時清除 Redis key，允許重試
        → try/except 結構：except 塊中 REDIS_CLIENT.delete(idempotent_key)
        → 成功後更新 key value 為 "done:{order_id}"，延長 TTL 至 7 天
        → 不允許永久殘留的 "processing" 狀態（需有超時機制）
```

---

## 四、業務合理性守衛

```
[ ] 16. 博弈賠付前校驗最大賠付上限（MAX_SINGLE_PAYOUT）
        → 上限從設定檔讀取（不硬編碼），設定檔有預設安全值
        → 超過上限：先觸發告警（ops alert），再拋出 PayoutLimitExceeded
        → 同時校驗賠率倍數上限（防止賠率計算錯誤）

[ ] 17. 單次充值金額在合理範圍內（最小/最大限制）
        → 最小充值金額：防止微額攻擊（如 0.01 元）
        → 最大充值金額：符合反洗錢（AML）規定
        → 範圍值從設定檔讀取，有對應的設定文件

[ ] 18. 單次購買點數在合理範圍內
        → 最小點數包：配合最小充值金額
        → 最大點數包：防止異常大額單次購買
        → 點數換算比例有版本控制（價格調整時舊訂單不受影響）

[ ] 19. 主播出金前校驗最低出金門檻
        → 最低出金金額：防止頻繁小額出金造成手續費損失
        → 出金前校驗帳戶狀態（未被封停、已完成 KYC）
        → 出金額度校驗：不超過帳戶可用餘額（扣除凍結金額）

[ ] 20. 異常情況觸發告警後才拋出例外
        → 告警先於例外：alert_ops(msg) 然後 raise Exception(msg)
        → 防止例外吞掉告警（特別注意 try/except 吞例外的情況）
        → 告警訊息包含業務上下文（user_id、amount、order_id）
```

---

## 五、日誌與可觀測性

```
[ ] 21. 點數充值：記錄 user_id, amount, transaction_id, 狀態, 耗時
        → 格式：{"event": "charge", "user_id": 123, "amount": "100.00",
                  "transaction_id": "xxx", "status": "success", "duration_ms": 45}
        → 充值完成和失敗都要記錄（便於對帳）

[ ] 22. 支付回調：記錄完整的回調 body（遮罩敏感欄位後）
        → 遮罩：卡號、CVV、帳號、手機號
        → 保留：訂單號、金額、交易號、支付狀態
        → 格式化存儲，方便後續查詢和對帳

[ ] 23. 博弈結算：記錄 game_id, round_id, result, payout, user_id, duration_ms
        → 結算成功和失敗都要記錄
        → 高額賠付觸發額外的業務日誌（方便審計）

[ ] 24. 敏感欄位（卡號/CVV/密碼/API Secret）不得寫入日誌
        → 使用 mask_sensitive() 函式處理支付相關資料
        → CVV 永不記錄（即使遮罩也不記）
        → API Secret Key 不得出現在任何日誌中

[ ] 25. 流水號：每個點數操作有全域唯一流水號（UUID v4 或雪花 ID）
        → 充值流水號、扣款流水號、打賞流水號相互獨立
        → 流水號記錄在資料庫，方便跨系統對帳
        → 流水號在 API 回應和日誌中都記錄（方便客服查詢）
```

---

## 六、QA 自動化測試覆蓋

```
[ ] 26. 正向測試：正常充值流程
        → 支付回調 → 點數到帳 → 餘額正確
        → 各支付平台（ECPay/支付寶/微信/91app）各自的正向案例
        → 回調延遲 30 秒內到帳

[ ] 27. 負向測試：重複回調只充值一次
        → 模擬支付寶/微信重複發送 notify（2-3 次）
        → 驗證只有第一次觸發充值
        → 驗證後續回調返回正確格式（success）且不重複充值

[ ] 28. 並發測試：多個請求同時扣款不超扣
        → 10 個並發打賞請求，用戶僅有足夠一次的點數
        → 驗證只有一個成功，其餘返回 InsufficientPointsError
        → 驗證點數餘額為 0，不為負數

[ ] 29. 邊界測試：最小/最大金額、零點數餘額扣款
        → 最小充值金額（如 1 元）
        → 最大充值金額（AML 上限）
        → 0 點數餘額發起扣款
        → 微信支付 0.01 元（1 分）
        → 分潤計算無法整除的邊界值

[ ] 30. 沙箱測試：各支付平台沙箱環境已通過驗收
        → 綠界 ECPay：stage.ecpay.com.tw 測試商家帳號測試通過
        → 支付寶：沙箱 openapi.alipaydev.com 測試通過
        → 微信支付：沙箱 api.mch.weixin.qq.com/sandboxnew 測試通過
        → 91app：測試環境已驗收
```

---

## 七、正面安全編碼基線（Python 版）

> 以下是各操作的正確寫法範例，供修復時直接參照。

### 點數精度計算

```python
from decimal import Decimal, ROUND_HALF_DOWN

# 充值點數計算
def calc_points(purchase_amount: str, rate: str) -> int:
    amount = Decimal(purchase_amount)         # 使用字串初始化
    exchange_rate = Decimal(rate)
    points = (amount * exchange_rate).quantize(
        Decimal('1'), rounding=ROUND_HALF_DOWN
    )
    return int(points)

# 多方分潤（最大餘額法）
def split_tip(total: Decimal) -> tuple[Decimal, Decimal]:
    platform = (total * Decimal('0.30')).quantize(
        Decimal('0.01'), rounding=ROUND_HALF_DOWN
    )
    streamer = total - platform   # 最大餘額法，確保 streamer + platform == total
    assert streamer + platform == total
    return streamer, platform
```

### 支付回調驗簽

```python
# 綠界 ECPay 驗簽
import hashlib, urllib.parse

def verify_ecpay(params: dict, hash_key: str, hash_iv: str) -> bool:
    check_mac = params.pop('CheckMacValue', '')
    sorted_p = sorted(params.items(), key=lambda x: x[0].lower())
    raw = f"HashKey={hash_key}&" + "&".join(f"{k}={v}" for k, v in sorted_p) + f"&HashIV={hash_iv}"
    encoded = urllib.parse.quote_plus(raw).lower()
    computed = hashlib.sha256(encoded.encode()).hexdigest().upper()
    return computed == check_mac

# 支付寶驗簽（使用官方 SDK）
from alipay import AliPay
def verify_alipay(params: dict, public_key: str, appid: str) -> bool:
    sign = params.pop('sign', '')
    params.pop('sign_type', None)
    alipay = AliPay(appid=appid, alipay_public_key_string=public_key)
    return alipay.verify(params, sign)
```

### 冪等保護

```python
import redis, uuid
REDIS = redis.Redis(host=REDIS_HOST)

def idempotent_credit(user_id: int, amount: int, request_id: str) -> bool:
    """冪等充值：同一 request_id 只充值一次"""
    key = f"charge:v1:{user_id}:{request_id}"
    is_first = REDIS.set(key, "processing", ex=86400, nx=True)
    if not is_first:
        return False   # 重複請求
    try:
        credit_points(user_id, amount)
        REDIS.set(key, "done", ex=86400 * 7)
        return True
    except Exception:
        REDIS.delete(key)   # 失敗時清除，允許重試
        raise
```

### 原子點數扣減

```python
def debit_points_atomic(user_id: int, amount: int) -> bool:
    """原子扣款，確保不超扣"""
    rows = db.execute(
        "UPDATE users SET points = points - %s WHERE id = %s AND points >= %s",
        (amount, user_id, amount)
    )
    if rows == 0:
        raise InsufficientPointsError(f"user={user_id}, amount={amount}")
    return True
```

### IDOR 防護

```python
# 資源歸屬必須在 SQL 層強制
def get_user_order(order_id: int, user: User) -> Order:
    order = db.execute(
        "SELECT * FROM orders WHERE id = %s AND user_id = %s",
        (order_id, user.id)   # user.id 來自 JWT，不來自請求參數
    ).fetchone()
    if not order:
        raise HTTPException(status_code=404)
    return order
```

### 敏感欄位遮罩

```python
SENSITIVE_KEYS = {'card_number', 'cvv', 'password', 'secret', 'bank_account'}

def mask(data: dict) -> dict:
    return {
        k: f"****{v[-4:]}" if k in SENSITIVE_KEYS and isinstance(v, str) and len(v) > 4 else v
        for k, v in data.items()
    }

log.info("支付回調: %s", mask(callback_body))
```

---

## 通過標準

| 分類 | 項目 | 要求 |
|------|------|------|
| 點數精度（1-4） | 全部 | 未通過 → Block PR |
| 支付回調安全（5-10） | 5、6、9 | 未通過 → Block PR（CRITICAL） |
| 支付回調安全（5-10） | 7、8、10 | 未通過 → Block PR（視情況） |
| 並發安全與冪等（11-15） | 全部 | 涉及充值/扣款的 PR 必須全通過 |
| 業務合理性守衛（16-20） | 16、19、20 | 未通過 → Block PR |
| 業務合理性守衛（16-20） | 17、18 | 未通過 → 需說明原因 |
| 日誌與可觀測性（21-25） | 24 | 未通過 → Block PR（隱私合規） |
| 日誌與可觀測性（21-25） | 21、22、23、25 | 未通過 → 需說明原因 |
| QA 自動化（26-30） | 26、27、28 | 涉及核心流程的 PR 必須通過 |
| QA 自動化（26-30） | 29、30 | 建議通過，不通過需排期補充 |

> 最後更新：2026-06-05 | 維護：SWAG QA 部門
> 替代：settlement-checklist.md（已改為 Java/Spring 版，本檔為 Python/FastAPI 版）
