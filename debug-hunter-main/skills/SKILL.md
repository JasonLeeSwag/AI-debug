# SKILL.md — SWAG QA 系統 Bug 偵測與修復技能

> 適用：swag.live 成人直播平台 · 博弈遊戲（龍虎鬥／百家樂）· 金流付費（綠界 ECPay／91app／支付寶／微信支付）· API 買分後台
> 技術堆疊：Python · FastAPI / Django · React / JSX · JavaScript · Flutter Web · Robot Framework · Playwright · Appium
> 版本：v1.0 · 最後更新：2026-06-05

---

## 何時使用此技能

當你需要：
- 審查博弈遊戲核心邏輯（RNG、賠率計算、結算流程）
- 審查點數系統與金流付費相關的 Python / JavaScript 程式碼
- 偵測充值、扣減、出金、打賞、訂閱相關的潛在 Bug
- 驗證金流回調（ECPay、支付寶、微信支付）的安全實作
- 分析 API 買分後台的防刷與冪等性機制
- 審查 QA 自動化測試腳本品質（Robot Framework、Playwright、Appium）
- 設計冪等性保護機制與不變量守衛
- 進行事後檢視（Post-mortem）

請在開始分析前，先讀取：
1. `knowledge-base/financial-bug-patterns.md`（已知 Bug 模式）
2. `knowledge-base/financial-security-patterns.md`（安全漏洞模式）
3. `knowledge-base/financial-invariants.md`（不變量庫）
4. `knowledge-base/oss-debug-security-loop.md`（高星開源 debug／漏洞閉環清單；當任務涉及全專案掃描、PR / release gate 時必讀）

---

## 偵測流程（Detection Protocol）

### Step 1：識別程式碼分類

拿到程式碼後，先判斷屬於哪個風險類別：

```
類別 A：博弈遊戲核心（最高風險）
  → RNG 亂數生成、賠率計算、下注結算、出金邏輯
  → 必須執行完整的 15 項博弈安全檢查
  → 任何 Finding 預設為 P0 候選

類別 B：點數／金流計算（最高風險）
  → 充值入帳、點數扣減、出金計算、訂閱計費
  → 必須執行完整的 12 項點數金流檢查
  → 任何 Finding 預設為 P0 候選

類別 C：金流回調處理（高風險）
  → 綠界 ECPay、91app、支付寶、微信支付回調接收與驗簽
  → 重點檢查：簽章驗證、金額比對、冪等性、重放防護

類別 D：API 買分後台（高風險）
  → 買分流程、點數分配、帳戶管理 API
  → 重點檢查：身份驗證、授權、負數防護、冪等性

類別 E：直播功能（中風險）
  → 打賞互動、訂閱訂單、虛擬禮物、主播分潤
  → 重點檢查：並發打賞競態、斷線補償、退款同步

類別 F：QA 自動化測試（中風險）
  → Robot Framework 測試腳本、Playwright E2E 測試、Appium 行動端測試
  → 重點檢查：測試案例完整性、斷言品質、邊界條件覆蓋
```

---

### Step 2：執行對應的檢查清單

#### 【類別 A】博弈遊戲核心 15 項安全檢查

```
[ ] 1.  RNG 安全性：亂數生成是否使用密碼學安全的 CSPRNG？
        Python 必須使用 secrets 模組或 os.urandom()，禁止 random.random()
[ ] 2.  RNG 種子保護：種子是否被記錄在可被外部存取的日誌或回應欄位中？
[ ] 3.  RNG 獨立性：每局牌局的 RNG 是否相互獨立？不得共用種子狀態
[ ] 4.  賠率表驗證：賠率是否從伺服器端核定表取得？不得由前端參數傳入
[ ] 5.  賠率計算精度：賠率計算是否全程使用 decimal.Decimal？禁止 float
[ ] 6.  賠率上限守衛：計算結果是否有業務核定賠率上限的校驗？
[ ] 7.  下注金額驗證：下注金額是否為正數，且 ≤ 帳戶可用餘額？
[ ] 8.  結算冪等性：同一局的結算是否有冪等保護，防止重複結算？
[ ] 9.  並發下注防護：高並發下注時是否有悲觀鎖或版本號（樂觀鎖）保護餘額？
[ ] 10. 結算狀態機：結算狀態是否只能單向流轉（PENDING → SETTLED → PAID）？
[ ] 11. 出金金額核算：出金金額是否由後端根據賠率表計算，而非接受前端傳入值？
[ ] 12. 最大贏額限制：單局最大贏額是否有上限，防止異常賠付？
[ ] 13. 負餘額防護：任何扣款操作後，帳戶餘額是否有 ≥ 0 的守衛？
[ ] 14. 牌局記錄完整性：每一局的輸入、RNG 輸出、賠率、結算金額是否完整記錄，供稽核？
[ ] 15. 防作弊監控：是否有異常贏率監控（如連贏次數超過統計閾值觸發人工審查）？
```

**類別 A 常見問題程式碼（Python）**：

```python
# 錯誤示範：使用不安全的 random 模組
import random
rng_result = random.randint(1, 13)  # 可被預測！禁止用於博弈

# 正確示範：使用 secrets 模組
import secrets
rng_result = secrets.randbelow(13) + 1  # 密碼學安全

# 錯誤示範：賠率計算使用 float
payout = bet_amount * 1.95  # float 精度問題

# 正確示範：賠率計算使用 Decimal
from decimal import Decimal, ROUND_HALF_DOWN
payout = Decimal(str(bet_amount)) * Decimal("1.95")
payout = payout.quantize(Decimal("0.01"), rounding=ROUND_HALF_DOWN)
```

---

#### 【類別 B】點數／金流計算 12 項安全檢查

```
[ ] 1.  Decimal 精度：所有點數與金額計算是否全程使用 decimal.Decimal？禁止 float
[ ] 2.  冪等性保護：充值和扣款是否有唯一冪等鍵（transaction_id）防止重複執行？
[ ] 3.  負數防護：amount 參數是否有 > 0 的強制驗證？傳入負數或零值是否被拒絕？
[ ] 4.  餘額原子操作：「檢查餘額」與「扣款」是否在同一資料庫事務中（原子操作）？
[ ] 5.  競態條件：並發扣款時是否有悲觀鎖（SELECT FOR UPDATE）或樂觀鎖（version）保護？
[ ] 6.  溢位防護：超大點數值的乘除運算是否有溢位風險？
[ ] 7.  單位一致性：入參、計算、出參的單位（點數單位）是否全程一致，不得隱式轉換？
[ ] 8.  null / None 防護：從資料庫取回的數值是否有 None 檢查，避免 NoneType 錯誤？
[ ] 9.  Rounding 規則：四捨五入的規則是否符合業務規範，且全程統一？
[ ] 10. 上限校驗：單筆充值上限、單筆出金上限、單日限額是否有守衛？
[ ] 11. 事務回滾：扣款失敗時，已進行的部分操作是否正確回滾？
[ ] 12. 稽核日誌：每筆點數異動是否記錄（who, what, when, before, after）供對帳？
```

**類別 B 常見問題程式碼（Python）**：

```python
# 錯誤示範：float 計算導致精度錯誤
points_after = user.points - 9.99 * 3  # float: 可能得到 29.969999...

# 正確示範：Decimal 全程
from decimal import Decimal
points_after = user.points - Decimal("9.99") * 3  # 精確

# 錯誤示範：未鎖定即扣款（競態條件）
user = db.query(User).filter_by(id=user_id).first()
if user.points >= amount:
    user.points -= amount  # 並發時可能透支

# 正確示範：SELECT FOR UPDATE + 事務
with db.begin():
    user = db.query(User).filter_by(id=user_id).with_for_update().first()
    if user.points < amount:
        raise InsufficientPointsError()
    user.points -= amount
```

---

#### 【類別 C】金流回調處理 8 項安全檢查

```
[ ] 1.  簽章驗證：是否在處理任何業務邏輯前，先驗證支付服務商的簽章／HMAC？
        ECPay：SHA256 CheckMacValue；支付寶：RSA2 簽名；微信支付：HMAC-SHA256
[ ] 2.  簽章驗證不可繞過：是否有任何條件分支（if skip_verify）可以跳過驗簽？
[ ] 3.  金額比對：回調金額是否與資料庫中的訂單金額做嚴格比對（不允許差異）？
[ ] 4.  訂單狀態確認：處理回調前，是否確認訂單狀態為 PENDING（防止已完成訂單被重複入帳）？
[ ] 5.  重複消費防護：是否有冪等鍵（trade_no 或 out_trade_no）確保同一回調只處理一次？
[ ] 6.  原子更新：「記錄回調」→「更新訂單狀態」→「增加用戶點數」是否在同一事務中？
[ ] 7.  來源 IP 白名單：是否有支付服務商 IP 白名單驗證（作為簽章驗證的附加防線）？
[ ] 8.  回調回應規範：是否只在所有邏輯成功後才回傳支付商要求的成功訊號（如 SUCCESS）？
```

**類別 C 常見問題程式碼（Python / FastAPI）**：

```python
# 錯誤示範：未驗簽即處理，金額未比對
@app.post("/payment/callback/ecpay")
async def ecpay_callback(data: dict):
    order = db.get_order(data["MerchantTradeNo"])
    order.status = "PAID"  # 危險：任何人都能偽造此請求
    user.points += calculate_points(data["TradeAmt"])

# 正確示範：先驗簽，再比對金額，再原子更新
@app.post("/payment/callback/ecpay")
async def ecpay_callback(request: Request):
    body = await request.body()
    params = parse_ecpay_params(body)

    # 1. 驗簽（最優先）
    if not verify_ecpay_checksum(params, ECPAY_HASH_KEY, ECPAY_HASH_IV):
        raise HTTPException(status_code=400, detail="Invalid signature")

    trade_no = params["MerchantTradeNo"]
    paid_amount = Decimal(params["TradeAmt"])

    with db.begin():
        # 2. 冪等鍵防重複
        if db.callback_already_processed(trade_no):
            return {"RtnCode": 1}  # 已處理，回傳成功避免重試

        # 3. 查訂單並驗金額
        order = db.get_order_for_update(trade_no)
        if order.status != "PENDING":
            raise HTTPException(status_code=400, detail="Order not in pending state")
        if order.amount != paid_amount:
            raise HTTPException(status_code=400, detail="Amount mismatch")

        # 4. 原子更新
        order.status = "PAID"
        user.points += order.points_to_grant
        db.mark_callback_processed(trade_no)

    return {"RtnCode": 1, "RtnMsg": "OK"}
```

---

#### 【類別 D】API 買分後台 8 項安全檢查

```
[ ] 1.  身份驗證：買分 API 是否強制要求有效的 JWT / API Key？未授權請求是否返回 401？
[ ] 2.  授權層級：是否驗證呼叫方有權執行買分操作（角色／權限檢查）？
[ ] 3.  payment_id 驗證：買分是否需要有效且未使用的 payment_id？
        不可在無對應支付記錄的情況下直接增加點數
[ ] 4.  amount 正整數驗證：amount 是否強制驗證為正整數（> 0）？
        傳入 0、負數、浮點數、字串等異常值是否全部被拒絕？
[ ] 5.  冪等性：相同 idempotency_key 的請求是否只執行一次？
[ ] 6.  IDOR 防護：是否防止 A 用戶替 B 用戶買分（參數中的 user_id 是否做授權比對）？
[ ] 7.  速率限制：買分接口是否有速率限制防止大量刷分？
[ ] 8.  稽核日誌：每次買分操作是否記錄完整資訊（操作者、目標帳號、金額、時間、IP）？
```

**類別 D 常見問題程式碼（Python / FastAPI）**：

```python
# 錯誤示範：無驗證直接買分
@app.post("/admin/add-points")
async def add_points(user_id: int, amount: int):
    user = db.get_user(user_id)
    user.points += amount  # 任何人可無限買分！

# 正確示範：完整保護
from fastapi import Depends, HTTPException
from decimal import Decimal

@app.post("/admin/add-points")
async def add_points(
    request: AddPointsRequest,
    current_user: User = Depends(require_admin_role)  # 1. 驗證身份+角色
):
    # 2. 驗證 amount 為正整數
    if request.amount <= 0:
        raise HTTPException(status_code=422, detail="amount must be positive integer")

    # 3. 驗證 payment_id 有效且未使用
    payment = db.get_valid_unused_payment(request.payment_id)
    if not payment:
        raise HTTPException(status_code=400, detail="Invalid or used payment_id")

    # 4. 冪等鍵防重
    if db.idempotency_key_exists(request.idempotency_key):
        return {"status": "already_processed"}

    with db.begin():
        target_user = db.get_user_for_update(request.user_id)
        target_user.points += request.amount
        db.mark_payment_used(request.payment_id)
        db.record_idempotency_key(request.idempotency_key)
        db.write_audit_log(
            operator=current_user.id,
            target=request.user_id,
            action="add_points",
            amount=request.amount,
            payment_id=request.payment_id
        )
```

---

### Step 2.5：QA 自動化掃描工具清單

若任務範圍不是單一 bug，而是整個專案的 debug / 漏洞盤點，或需驗收修復品質，必須依 `knowledge-base/oss-debug-security-loop.md` 補做以下交叉驗證：

**靜態分析（SAST）**：
```
[ ] 1. Bandit：Python 程式碼安全弱點靜態掃描（針對 FastAPI/Django 後端）
[ ] 2. Semgrep：自訂規則掃描（可針對 SWAG 業務邏輯，如回調驗簽、Decimal 使用）
[ ] 3. ESLint + security plugins：JavaScript / JSX 前端程式碼安全掃描
[ ] 4. CodeQL：跨檔案 taint 資料流分析（追蹤使用者輸入→金額計算→資料庫寫入）
[ ] 5. Gitleaks：掃描 secrets / 金鑰 / token 外洩（ECPay HashKey、支付寶私鑰等）
```

**依賴安全**：
```
[ ] 6. Safety / pip-audit：掃描 Python requirements.txt 的已知漏洞
[ ] 7. npm audit：掃描 Node.js / React 依賴的已知漏洞
[ ] 8. Trivy：掃描容器映像、設定錯誤、SBOM
[ ] 9. OSV-Scanner：掃描 lockfile 的已知漏洞
```

**動態分析（DAST）與測試**：
```
[ ] 10. OWASP ZAP：對 staging API 做 DAST（重點：支付回調接口、買分接口）
[ ] 11. Nuclei：對已部署端點做模板式弱點驗證（API 鑑權弱點、參數竄改）
[ ] 12. Playwright：E2E 測試——支付流程、點數扣減、訂閱流程
[ ] 13. Appium：行動端 E2E 測試（Flutter Web / 原生 App）
[ ] 14. Robot Framework：BDD 驗收測試（博弈遊戲流程、金流充值流程）
[ ] 15. pytest-hypothesis：Python 屬性測試——對賠率計算、點數計算做 fuzzing
```

原則：
- 金融規則相關問題，不可只依賴通用工具，仍須回到本技能既有清單判讀
- 通用工具命中後，必須轉譯成 SWAG 業務語境的風險說明，而不是只貼工具原始輸出
- 任一外部工具確認為真陽性，最終都必須回寫成 `PAT-*` 或 `RULE-*`

---

### Step 3：輸出偵測報告格式

每個發現的問題，輸出以下格式（使用台灣正體中文 + Markdown）：

```markdown
## [P0] BUG-SWAG-{序號}：{簡短標題}

**風險等級**：P0 / P1 / P2 / P3
**受影響系統**：博弈遊戲 / 直播平台 / 金流支付 / 買分後台
**受影響服務**：{服務名稱，如 payment-service、game-settlement}
**技術堆疊**：Python FastAPI / JavaScript React / Flutter Web
**Bug 類別**：{RNG 安全性 / 賠率計算 / 冪等性 / 回調偽造 / 點數競態 / ...}
**違反不變量**：{INV-SWAG-XXX（若有）}

### 問題描述
{說明 Bug 的具體行為，包含觸發條件與業務影響}

### 問題程式碼
```python
# 標示出有問題的行，附上檔案路徑與行號
```

### 根因
{說明為什麼系統設計上允許這個 Bug 存在；指出設計缺陷，而非只描述症狀}

### 修復方案
```python
# 修復後的程式碼
```

### 測試案例
```python
# pytest / Robot Framework 覆蓋此 Bug 的測試
```

### 知識庫規則
**規則代碼**：RULE-{類別}-{序號}
**規則描述**：{可以被 Semgrep / Bandit 實作的規則描述}
```

---

## 修復策略選擇指南

根據根因類型，選擇對應的修復策略（Python 優先，JavaScript 附帶）：

### 策略 1：CSPRNG 替換（Cryptographically Secure RNG）
**適用**：博弈遊戲 RNG 使用了不安全的亂數生成器

```python
# 錯誤：random 模組可被預測
import random
result = random.choice(["龍", "虎", "和"])

# 正確：secrets 模組（密碼學安全）
import secrets
result = secrets.choice(["龍", "虎", "和"])

# 若需要可驗證公平性（Provably Fair），使用 HMAC-SHA256
import hmac, hashlib, secrets
server_seed = secrets.token_hex(32)  # 每局新種子，提前公布 hash(server_seed)
client_seed = "user_provided_seed"
combined = f"{server_seed}:{client_seed}:{nonce}"
result_hash = hmac.new(server_seed.encode(), combined.encode(), hashlib.sha256).hexdigest()
```

### 策略 2：Decimal 精確計算
**適用**：金額、點數、賠率計算使用了 float

```python
from decimal import Decimal, ROUND_HALF_DOWN, ROUND_HALF_UP

# 賠率計算（所有中間值都是 Decimal）
bet = Decimal("100")
odds = Decimal("1.95")
payout = (bet * odds).quantize(Decimal("0.01"), rounding=ROUND_HALF_DOWN)

# JavaScript 等效（使用 big.js 或 decimal.js）
# const Decimal = require('decimal.js')
# const payout = new Decimal(bet).times(odds).toFixed(2)
```

### 策略 3：資料庫原子操作 + 悲觀鎖
**適用**：點數扣減、餘額更新的競態條件

```python
from sqlalchemy import select
from sqlalchemy.orm import Session

def deduct_points(db: Session, user_id: int, amount: Decimal):
    # SELECT FOR UPDATE 確保同一時間只有一個事務可修改
    user = db.execute(
        select(User).filter_by(id=user_id).with_for_update()
    ).scalar_one()

    if user.points < amount:
        raise InsufficientPointsError(f"餘額不足：有 {user.points}，需 {amount}")

    user.points -= amount
    db.flush()  # 立即寫入，確保鎖的效力
    return user.points
```

### 策略 4：冪等性雙層保護
**適用**：金流回調重複處理、買分請求重放、打賞重複扣款

```python
import redis
from contextlib import contextmanager

redis_client = redis.Redis()

def process_payment_callback(trade_no: str, handler_fn):
    idempotency_key = f"payment:processed:{trade_no}"

    # 第一層：Redis 快速攔截（TTL 24 小時）
    if not redis_client.set(idempotency_key, "1", nx=True, ex=86400):
        return {"status": "already_processed"}

    try:
        with db.begin():
            # 第二層：DB 狀態機（防 Redis 故障後的二次防護）
            order = db.get_order_for_update(trade_no)
            if order.status != "PENDING":
                return {"status": "already_processed"}
            handler_fn(order)
    except Exception:
        # 失敗時清除 Redis 鍵，允許重試
        redis_client.delete(idempotency_key)
        raise
```

### 策略 5：金流回調簽章驗證
**適用**：ECPay / 支付寶 / 微信支付回調缺少驗簽

```python
import hmac
import hashlib
import urllib.parse

def verify_ecpay_checksum(params: dict, hash_key: str, hash_iv: str) -> bool:
    """驗證綠界 ECPay 回調簽章"""
    # 移除 CheckMacValue 本身
    check_value = params.pop("CheckMacValue", None)

    # 依照 ECPay 規範：key 按 ASCII 排序，URL encode，包夾 HashKey/HashIV
    sorted_params = "&".join(
        f"{k}={v}" for k, v in sorted(params.items())
    )
    raw = f"HashKey={hash_key}&{sorted_params}&HashIV={hash_iv}"
    encoded = urllib.parse.quote_plus(raw).lower()
    computed = hashlib.sha256(encoded.encode()).hexdigest().upper()

    return hmac.compare_digest(computed, check_value or "")

def verify_alipay_signature(params: dict, public_key: str) -> bool:
    """驗證支付寶 RSA2 簽名"""
    from Crypto.Signature import pkcs1_15
    from Crypto.PublicKey import RSA
    from Crypto.Hash import SHA256
    import base64

    sign = params.pop("sign", None)
    params.pop("sign_type", None)
    content = "&".join(f"{k}={v}" for k, v in sorted(params.items()))

    key = RSA.import_key(public_key)
    h = SHA256.new(content.encode("utf-8"))
    try:
        pkcs1_15.new(key).verify(h, base64.b64decode(sign))
        return True
    except (ValueError, TypeError):
        return False
```

### 策略 6：業務合理性守衛（最後防線）
**適用**：作為最後一道防線，即使計算邏輯有 Bug 也能攔截異常結果

```python
from decimal import Decimal

MAX_SINGLE_PAYOUT = Decimal("100000")   # 單局最大賠付（業務核定）
MAX_ODDS = Decimal("100")               # 最高賠率上限
MIN_BALANCE = Decimal("0")             # 帳戶最低餘額

def validate_game_settlement(bet_amount: Decimal, odds: Decimal, payout: Decimal):
    """博弈結算合理性守衛"""
    if odds > MAX_ODDS:
        raise SettlementGuardError(f"賠率 {odds} 超出上限 {MAX_ODDS}")

    expected_max = bet_amount * MAX_ODDS
    if payout > expected_max:
        raise SettlementGuardError(f"賠付金額 {payout} 超出理論上限 {expected_max}")

    if payout > MAX_SINGLE_PAYOUT:
        raise SettlementGuardError(f"單局賠付 {payout} 超出業務上限 {MAX_SINGLE_PAYOUT}")

def validate_balance_after_deduction(balance_after: Decimal):
    """扣款後餘額守衛"""
    if balance_after < MIN_BALANCE:
        raise BalanceGuardError(f"扣款後餘額 {balance_after} 為負數，疑似競態攻擊")
```

### 策略 7：QA 自動化測試品質提升
**適用**：Robot Framework / Playwright 測試腳本覆蓋不足或斷言不正確

```python
# Playwright 金流回調測試（Python）
import pytest
from playwright.sync_api import Page

def test_ecpay_callback_forge_rejected(page: Page):
    """驗證偽造的 ECPay 回調被正確拒絕（P0 安全測試）"""
    # 建立一筆待支付訂單
    order = create_test_order(amount="100")

    # 構造偽造回調（金額竄改 + 無效簽章）
    forged_payload = {
        "MerchantTradeNo": order.trade_no,
        "TradeAmt": "1",          # 竄改金額：100 → 1
        "RtnCode": "1",
        "CheckMacValue": "INVALID_SIGNATURE"
    }

    response = page.request.post("/api/payment/callback/ecpay", data=forged_payload)

    # 驗收：偽造請求必須被拒絕
    assert response.status == 400
    # 驗收：訂單狀態不得改變
    order_after = get_order(order.trade_no)
    assert order_after.status == "PENDING"
    # 驗收：用戶點數不得增加
    assert get_user_points(order.user_id) == INITIAL_POINTS
```

```robot
*** Test Cases ***
博弈結算冪等性驗證
    [Documentation]    相同局號不得被結算兩次（INV-SWAG-G03）
    ${game_id}=    建立測試局號
    結算遊戲    ${game_id}    玩家獲勝    下注金額=100
    ${points_after_first}=    取得用戶點數    ${TEST_USER}
    結算遊戲    ${game_id}    玩家獲勝    下注金額=100    # 重複結算
    ${points_after_second}=    取得用戶點數    ${TEST_USER}
    Should Be Equal    ${points_after_first}    ${points_after_second}
    ...    msg=重複結算導致點數不一致，違反 INV-SWAG-G03
```

---

## 事後檢視（Post-mortem）模板

每次 P0 / P1 Bug 修復後，必須填寫：

```markdown
# 事後檢視報告 — {Bug 標題}

**日期**：{YYYY-MM-DD}
**等級**：{P0 / P1}
**受影響系統**：{博弈遊戲 / 直播平台 / 金流支付 / 買分後台}
**影響時間**：{開始} ~ {結束}（共 {N} 分鐘）
**影響範圍**：{受影響的使用者數 / 訂單數 / 點數或金額損失}

## 事件時間軸
| 時間 | 事件 |
|------|------|
| HH:MM | 系統出現異常告警（點數異常 / 回調驗簽失敗 / 賠率異常）|
| HH:MM | On-call 接收到告警 |
| HH:MM | 確認根因 |
| HH:MM | 開始部署修復 |
| HH:MM | 服務恢復正常 |

## 根本原因
{5-Why 分析}

## 修復措施
{本次採取的修復行動，含程式碼修改與部署操作}

## 驗收確認
- [ ] 攻擊 PoC 在修復後無法成功執行
- [ ] 所有相關 INV-SWAG 不變量在壓力測試下恆成立
- [ ] Robot Framework / Playwright 回歸測試全數通過
- [ ] 受影響用戶的點數／金額已正確補償或沖正

## 預防措施
{未來如何避免同類問題；包含程式碼規範、測試補強、監控設定}

## 知識庫更新
- 新增規則：{RULE-XXX-NNN}
- 更新模式：{PAT-SWAG-XXX}
- 新增不變量：{INV-SWAG-XXX（若有）}
- 新增復現情境：{reproduce-scenarios.md 條目}
```
