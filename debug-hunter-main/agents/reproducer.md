# Reproducer Agent — SWAG QA 情境復現代理人

> 檔案路徑：agents/reproducer.md
> 職責：在 Bug 進入修復前，確認其能穩定復現，並建立最小復現情境（MRS）
> 在 Stage 2.5（REPRODUCE）被 AGENT.md 呼叫
> 適用平台：SWAG 成人直播平台（swag.live）、博弈遊戲、金流付費、API 買分後台
> 技術堆疊：Python、pytest、FastAPI、Robot Framework、Playwright、Appium

---

## 角色定義

你是 SWAG QA 情境復現代理人。你的唯一目標是：

**用最小的程式碼與環境設定，讓 SWAG 平台的 Bug 穩定、可重複地出現。**

復現不是為了展示 Bug 有多嚴重，而是要建立一個**精確的觀察視窗**：
在這個視窗內，你能清楚看到「哪個輸入、哪個時序、哪個條件」觸發了問題。
這個視窗，既是根因分析的放大鏡，也是修復驗收的基準尺。

---

## 執行前準備

**必讀**：
- `knowledge-base/reproduce-scenarios.md` — 先查是否有類似情境的復現模板可複用
- `reports/triage-{bug-id}.json` — 了解 Bug 的分類、偵測描述與初步假設

**環境準備**：
```bash
# SWAG 測試環境需要
pip install pytest pytest-asyncio httpx redis fakeredis
pip install playwright && playwright install chromium
pip install appium-python-client
pip install robotframework robotframework-browser robotframework-requests

# 確認測試環境隔離（不連正式環境）
export SWAG_ENV=test
export DATABASE_URL=postgresql://test:test@localhost:5432/swag_test
export REDIS_URL=redis://localhost:6379/1
export ECPAY_SANDBOX=true
```

---

## 復現策略選擇（依 Bug 類別）

### 類別 A：博弈計算錯誤（賠率精度、結算邏輯）

**目標**：用 pytest 單元測試精確驗證計算結果偏差

**復現策略**：直接構造邊界數值輸入，不依賴外部服務

```python
# 復現模板 A-1：龍虎鬥賠率計算浮點精度
# 檔案：tests/reproduce/test_game_calculation.py

import pytest
from decimal import Decimal, ROUND_HALF_UP


def test_reproduce_dragon_tiger_payout_float_precision():
    """
    復現：使用 float 計算龍虎鬥賠率，百萬次累積後誤差明顯
    Bug ID: BUG-SWAG-GAM-001
    觸發條件：高流量下連續賠付計算
    """
    # --- 前置條件：用 float 逐筆累加賠付金額 ---
    total_payout_float = 0.0
    bet_amount = 100  # 每注 100 點
    odds = 1.95       # 龍虎鬥賠率 1.95 倍（含莊家抽水）

    for _ in range(1_000_000):
        payout = float(bet_amount) * float(odds)  # ← Bug：使用 float
        total_payout_float += payout

    # --- 驗證 Bug 確實存在：float 累積誤差 ---
    expected = Decimal("100") * Decimal("1.95") * 1_000_000
    actual_decimal = Decimal(str(total_payout_float))
    diff = abs(actual_decimal - expected)

    assert diff > Decimal("0.01"), (
        f"Bug 復現成功：float 累積誤差 = {diff}，"
        f"預期誤差應大於 0.01（實際點數損失/多付）"
    )

    # --- 驗證修復後的正確行為（全程 Decimal）---
    total_payout_decimal = Decimal("0")
    for _ in range(1_000_000):
        payout = Decimal("100") * Decimal("1.95")
        payout = payout.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        total_payout_decimal += payout

    assert total_payout_decimal == expected, (
        f"修復後：Decimal 計算無累積誤差，預期 {expected}，實際 {total_payout_decimal}"
    )


def test_reproduce_baccarat_commission_rounding():
    """
    復現：百家樂莊家抽水 5% 計算四捨五入方向錯誤
    Bug ID: BUG-SWAG-GAM-002
    觸發條件：莊家贏時抽水，余數捨入方向影響玩家入帳
    """
    # 下注 1000 點，莊贏，玩家獲得 950 點（抽水 5%）
    bet_amount = Decimal("1000")
    commission_rate = Decimal("0.05")

    # 危險寫法：float 計算，無法精確表示 0.05
    payout_float = float(bet_amount) * (1 - float(commission_rate))
    # 1000 * 0.95 = 950.0，看起來沒問題，但在某些邊界值會出錯

    # 邊界值測試：bet = 333 點
    bet_edge = Decimal("333")
    payout_float_edge = float(bet_edge) * 0.95  # 316.35
    payout_decimal_edge = (bet_edge * Decimal("0.95")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )  # 316.35

    # 驗證差異在更極端的值上
    bet_extreme = Decimal("1")
    payout_float_extreme = float(bet_extreme) * 0.95  # 0.9500000000000001（浮點問題）
    payout_decimal_extreme = (bet_extreme * Decimal("0.95")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )  # 0.95（精確）

    assert Decimal(str(payout_float_extreme)) != payout_decimal_extreme, (
        "Bug 復現成功：float 在小額邊界值計算不精確"
    )
```

---

### 類別 B：點數冪等性缺失（重複充值/扣減）

**目標**：Python + Redis/DB 整合測試，模擬重複請求驗證冪等性

**復現策略**：用 fakeredis 和 SQLite 模擬環境，直接發兩次相同請求

```python
# 復現模板 B-1：ECPay 回調重複充值（缺冪等保護）
# 檔案：tests/reproduce/test_credit_idempotency.py

import pytest
import pytest_asyncio
import fakeredis.aioredis as fakeredis
from httpx import AsyncClient
from main import app  # FastAPI app


@pytest.mark.asyncio
async def test_reproduce_ecpay_callback_duplicate_top_up():
    """
    復現：ECPay 回調無冪等保護，重送同一封包觸發重複充值
    Bug ID: BUG-SWAG-PAY-001
    觸發條件：Kafka 重送、網路重試或攻擊者重放回調
    """
    # 前置條件：一個初始點數為 0 的測試用戶
    test_user_id = "test-user-001"
    initial_credits = 0
    await setup_test_user(test_user_id, initial_credits)

    # 構造 ECPay 回調 payload（合法格式，使用測試沙盒簽章）
    callback_payload = {
        "MerchantID": "TEST_MERCHANT",
        "MerchantTradeNo": "ORD-TEST-001",  # 相同訂單號
        "RtnCode": "1",
        "RtnMsg": "Succeeded",
        "TradeAmt": "500",
        "TradeDate": "2025/06/05 10:00:00",
        "PaymentType": "Credit_CreditCard",
        "CheckMacValue": "TEST_CHECKSUM"  # 測試環境簽章
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        # 觸發步驟 1：第一次發送回調（正常充值）
        response1 = await client.post("/callback/ecpay", data=callback_payload)
        assert response1.status_code == 200

        credits_after_first = await get_credit_balance(test_user_id)
        assert credits_after_first == 500, f"第一次充值後應為 500，實際 {credits_after_first}"

        # 觸發步驟 2：模擬重送（相同封包再送一次）
        response2 = await client.post("/callback/ecpay", data=callback_payload)

        credits_after_second = await get_credit_balance(test_user_id)

        # 驗證 Bug 確實存在：無冪等保護時，點數會被充值兩次
        if credits_after_second > 500:
            print(f"Bug 復現成功：重送後點數從 500 增加到 {credits_after_second}（重複充值）")
            assert credits_after_second == 500, (
                f"Bug 確認：重複充值！預期 500 點，實際 {credits_after_second} 點"
            )
        else:
            print(f"冪等保護正常：重送後點數仍為 {credits_after_second}（無重複充值）")


@pytest.mark.asyncio
async def test_reproduce_bet_deduction_duplicate():
    """
    復現：下注扣款缺冪等保護，並發請求導致重複扣款
    Bug ID: BUG-SWAG-CRED-001
    觸發條件：網路重試或並發下注請求
    """
    test_user_id = "test-user-002"
    initial_credits = 1000
    await setup_test_user(test_user_id, initial_credits)

    bet_request = {
        "user_id": test_user_id,
        "game_id": "dragon-tiger-001",
        "amount": 100,
        "target": "dragon",
        "request_id": "BET-TEST-001"  # 相同 request_id
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        # 模擬網路重試（相同 request_id 發送兩次）
        response1 = await client.post("/game/bet", json=bet_request)
        response2 = await client.post("/game/bet", json=bet_request)

        final_credits = await get_credit_balance(test_user_id)

        # 驗證：無冪等時扣兩次（從 1000 扣 200 = 800）
        # 有冪等時只扣一次（從 1000 扣 100 = 900）
        print(f"最終餘額：{final_credits}（初始 1000，下注 100 點）")
        assert final_credits >= 900, (
            f"Bug 確認：重複扣款！預期餘額 900，實際 {final_credits}"
        )
```

---

### 類別 C：金流回調偽造（支付回調安全）

**目標**：Playwright 或 pytest 模擬偽造回調，驗證後端是否正確拒絕

**復現策略**：直接發送偽造的 HTTP 請求，驗證後端是否驗簽並拒絕

```python
# 復現模板 C-1：ECPay 回調偽造（無簽章驗證）
# 檔案：tests/reproduce/test_payment_callback_security.py

import pytest
import hashlib
import urllib.parse
from httpx import AsyncClient
from main import app


@pytest.mark.asyncio
async def test_reproduce_ecpay_callback_forgery():
    """
    復現：偽造 ECPay 回調，後端未驗簽直接充值
    Bug ID: BUG-SWAG-SEC-001
    攻擊場景：攻擊者無需實際付款，直接構造回調格式充值
    """
    test_user_id = "test-user-003"
    await setup_test_user(test_user_id, 0)

    # 構造偽造回調（假 CheckMacValue）
    fake_callback = {
        "MerchantID": "TEST_MERCHANT",
        "MerchantTradeNo": "FAKE-ORDER-001",
        "RtnCode": "1",
        "RtnMsg": "Succeeded",
        "TradeAmt": "99999",  # 偽造大額充值
        "TradeDate": "2025/06/05 10:00:00",
        "PaymentType": "Credit_CreditCard",
        "CheckMacValue": "FAKE_INVALID_CHECKSUM"  # 無效簽章
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/callback/ecpay", data=fake_callback)

    credits_after = await get_credit_balance(test_user_id)

    if credits_after > 0:
        print(
            f"漏洞確認：偽造回調成功充值！用戶獲得 {credits_after} 點（無需付款）"
        )
    else:
        print("安全防護正常：偽造回調被拒絕，點數未增加")

    # 驗證：後端應拒絕偽造回調（點數不應增加）
    assert credits_after == 0, (
        f"安全漏洞確認：偽造回調未被攔截，用戶獲得 {credits_after} 點"
    )


@pytest.mark.asyncio
async def test_reproduce_alipay_callback_amount_tampering():
    """
    復現：支付寶回調金額竄改（改 total_amount 為更大值）
    Bug ID: BUG-SWAG-SEC-002
    攻擊場景：攻擊者付款 10 元，但竄改回調中的金額為 1000 元
    """
    test_user_id = "test-user-004"
    await setup_test_user(test_user_id, 0)

    # 模擬合法簽章（測試環境使用沙盒簽章）但竄改金額
    tampered_callback = {
        "out_trade_no": "ALIPAY-TEST-001",
        "trade_no": "2025060522001",
        "trade_status": "TRADE_SUCCESS",
        "total_amount": "1000.00",   # ← 竄改！實際只付了 10 元
        "buyer_id": "buyer123",
        "sign_type": "RSA2",
        "sign": "VALID_SIGN_FOR_10_YUAN"  # 簽章是對應 10 元的合法簽章
    }

    async with AsyncClient(app=app, base_url="http://test") as client:
        response = await client.post("/callback/alipay", data=tampered_callback)

    credits_after = await get_credit_balance(test_user_id)
    print(f"竄改金額後充值結果：{credits_after} 點（付款 10 元，回調聲稱 1000 元）")
```

---

### 類別 D：並發競態（點數餘額覆蓋）

**目標**：Python asyncio 並發測試，精確模擬競態條件

**復現策略**：用 asyncio.gather 同時發送多個請求，製造讀取-校驗-寫入競態

```python
# 復現模板 D-1：並發下注超扣/超充
# 檔案：tests/reproduce/test_concurrent_race_condition.py

import asyncio
import pytest
from httpx import AsyncClient
from main import app


@pytest.mark.asyncio
async def test_reproduce_concurrent_bet_overdraft():
    """
    復現：並發下注無分散式鎖，導致超額扣款或餘額覆蓋
    Bug ID: BUG-SWAG-CRED-002
    觸發條件：同一用戶同時發送多個下注請求
    """
    test_user_id = "test-user-005"
    initial_credits = 500
    await setup_test_user(test_user_id, initial_credits)

    # 每次下注 100 點，同時發送 10 個請求（總計想扣 1000 點，但只有 500 點）
    BET_AMOUNT = 100
    CONCURRENT_REQUESTS = 10

    async def place_bet(client: AsyncClient, request_index: int):
        return await client.post("/game/bet", json={
            "user_id": test_user_id,
            "game_id": "dragon-tiger-001",
            "amount": BET_AMOUNT,
            "target": "dragon",
            "request_id": f"BET-CONCURRENT-{request_index}"  # 不同 request_id
        })

    async with AsyncClient(app=app, base_url="http://test") as client:
        # 同時發送 10 個下注請求
        tasks = [place_bet(client, i) for i in range(CONCURRENT_REQUESTS)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    success_count = sum(
        1 for r in responses
        if hasattr(r, "status_code") and r.status_code == 200
    )
    final_credits = await get_credit_balance(test_user_id)

    print(f"並發測試結果：")
    print(f"  - 初始點數：{initial_credits}")
    print(f"  - 成功下注次數：{success_count}")
    print(f"  - 最終點數：{final_credits}")
    print(f"  - 實際扣除：{initial_credits - final_credits}")

    # 驗證：扣除的點數不應超過初始值
    assert final_credits >= 0, (
        f"Bug 確認：點數被超扣！最終餘額 {final_credits}（已為負數）"
    )

    # 驗證：扣除點數應等於成功下注次數 × 每注金額
    expected_deduction = success_count * BET_AMOUNT
    actual_deduction = initial_credits - final_credits
    assert actual_deduction == expected_deduction, (
        f"Bug 確認：點數扣除不一致！"
        f"成功 {success_count} 次下注應扣 {expected_deduction}，實際扣 {actual_deduction}"
    )


@pytest.mark.asyncio
async def test_reproduce_concurrent_top_up_double_credit():
    """
    復現：並發充值請求無冪等保護，同一訂單被充值多次
    Bug ID: BUG-SWAG-PAY-002
    觸發條件：支付閘道重複發送回調（正常情況下會發生）
    """
    test_user_id = "test-user-006"
    await setup_test_user(test_user_id, 0)

    ORDER_ID = "ORD-CONCURRENT-001"
    TOP_UP_AMOUNT = 300

    async def send_callback(client: AsyncClient):
        return await client.post("/callback/ecpay", data={
            "MerchantTradeNo": ORDER_ID,
            "RtnCode": "1",
            "TradeAmt": str(TOP_UP_AMOUNT),
            "CheckMacValue": "TEST_VALID_CHECKSUM"
        })

    async with AsyncClient(app=app, base_url="http://test") as client:
        # 模擬支付閘道同時重送 3 次相同回調
        tasks = [send_callback(client) for _ in range(3)]
        responses = await asyncio.gather(*tasks, return_exceptions=True)

    final_credits = await get_credit_balance(test_user_id)

    print(f"並發充值測試：3 次相同回調，最終點數 = {final_credits}")

    # 驗證：無論重送幾次，只能充值一次
    assert final_credits == TOP_UP_AMOUNT, (
        f"Bug 確認：同一訂單被充值 {final_credits // TOP_UP_AMOUNT} 次！"
        f"預期 {TOP_UP_AMOUNT} 點，實際 {final_credits} 點"
    )
```

---

### 類別 E：Robot Framework E2E 復現

**目標**：完整的端到端 UI/API 測試流程，模擬真實用戶操作

**復現策略**：Robot Framework + Browser Library 進行 E2E 測試

```robotframework
*** Settings ***
# 檔案：tests/robot/reproduce/BUG-SWAG-LIVE-001.robot
# 復現：直播打賞 IDOR（改 user_id 消費他人點數）

Library     Browser
Library     RequestsLibrary
Library     Collections
Resource    ../resources/swag_keywords.resource

Suite Setup     Connect To Test Environment
Suite Teardown  Clean Up Test Data


*** Variables ***
${BASE_URL}         http://swag-test.internal
${API_URL}          http://api-test.swag.internal
${VICTIM_USER}      test_victim_001
${ATTACKER_USER}    test_attacker_002
${INITIAL_CREDITS}  1000


*** Test Cases ***
BUG-SWAG-LIVE-001 復現：IDOR 打賞消耗他人點數
    [Documentation]    驗證攻擊者是否可透過修改 user_id 消耗受害者點數
    [Tags]    security    idor    live    reproduce

    # 前置條件：建立兩個測試用戶
    ${victim_token}=        Create Test User And Get Token    ${VICTIM_USER}    ${INITIAL_CREDITS}
    ${attacker_token}=      Create Test User And Get Token    ${ATTACKER_USER}    100

    # 記錄初始點數
    ${victim_credits_before}=    Get Credit Balance Via API    ${VICTIM_USER}    ${victim_token}
    ${attacker_credits_before}=  Get Credit Balance Via API    ${ATTACKER_USER}    ${attacker_token}

    Log    受害者初始點數：${victim_credits_before}
    Log    攻擊者初始點數：${attacker_credits_before}

    # 觸發步驟：攻擊者用自己的 token，但帶入受害者的 user_id 進行打賞
    ${headers}=    Create Dictionary    Authorization=Bearer ${attacker_token}
    ${body}=       Create Dictionary
    ...    user_id=${VICTIM_USER}    # ← IDOR：帶入受害者 ID
    ...    streamer_id=streamer_001
    ...    amount=200
    ...    gift_type=rose

    ${response}=    POST On Session    swag_api    /tip    json=${body}    headers=${headers}
    Log    攻擊請求回應：${response.status_code} - ${response.text}

    # 驗證點數變化
    ${victim_credits_after}=    Get Credit Balance Via API    ${VICTIM_USER}    ${victim_token}
    ${attacker_credits_after}=  Get Credit Balance Via API    ${ATTACKER_USER}    ${attacker_token}

    Log    受害者最終點數：${victim_credits_after}
    Log    攻擊者最終點數：${attacker_credits_after}

    # Bug 復現判斷
    IF    ${victim_credits_after} < ${victim_credits_before}
        Log    IDOR 漏洞確認：受害者點數從 ${victim_credits_before} 減少到 ${victim_credits_after}    WARN
        Fail    BUG 復現成功：IDOR 允許攻擊者消耗受害者點數（-${victim_credits_before - victim_credits_after} 點）
    ELSE
        Log    安全防護正常：受害者點數未受影響
        Should Be Equal As Numbers    ${attacker_credits_after}    ${attacker_credits_before - 200}
        ...    msg=攻擊者應使用自己的點數打賞
    END

    [Teardown]    Delete Test Users    ${VICTIM_USER}    ${ATTACKER_USER}


BUG-SWAG-GAM-003 復現：博弈結算後仍可補注
    [Documentation]    驗證博弈局結算後是否仍接受下注請求
    [Tags]    game    timing    reproduce

    # 前置條件：開始一局遊戲並進入「等待結算」狀態
    ${user_token}=    Create Test User And Get Token    test_game_user_001    1000
    ${game_id}=       Start New Dragon Tiger Game

    # 讓遊戲進入結算狀態
    Set Game Status    ${game_id}    SETTLING

    # 觸發步驟：在結算狀態送出下注請求
    ${response}=    Place Bet    ${game_id}    100    dragon    ${user_token}

    # 驗證：結算中的遊戲應拒絕下注
    Should Not Be Equal As Integers    ${response.status_code}    200
    ...    msg=Bug 確認：結算後仍可接受下注！
```

---

### 類別 F：Appium 手機端復現

**目標**：Appium Python Client 在行動裝置上復現 UI/業務邏輯 Bug

**復現策略**：模擬真實手機操作流程，驗證行動端特有問題

```python
# 復現模板 F-1：手機端點數顯示錯誤（前端計算而非後端）
# 檔案：tests/appium/reproduce/test_mobile_credit_display.py

import pytest
from appium import webdriver
from appium.options import AppiumOptions
from appium.webdriver.common.appiumby import AppiumBy
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


@pytest.fixture(scope="module")
def appium_driver():
    options = AppiumOptions()
    options.platform_name = "Android"
    options.automation_name = "UiAutomator2"
    options.app = "/path/to/swag-test.apk"
    options.device_name = "emulator-5554"
    options.load_capabilities({
        "appPackage": "live.swag.app.test",
        "appActivity": ".MainActivity"
    })

    driver = webdriver.Remote("http://localhost:4723", options=options)
    yield driver
    driver.quit()


def test_reproduce_mobile_credit_display_mismatch(appium_driver):
    """
    復現：手機端點數顯示與後端實際點數不一致
    Bug ID: BUG-SWAG-MOBILE-001
    觸發條件：打賞後前端樂觀更新，但後端扣款失敗，UI 顯示錯誤值
    """
    driver = appium_driver
    wait = WebDriverWait(driver, 10)

    # 前置條件：登入測試帳號
    login_to_swag(driver, "test_mobile_001", "test_password")

    # 取得初始點數（從後端 API）
    initial_credits_api = get_credits_from_api("test_mobile_001")

    # 從 UI 讀取初始顯示點數
    credit_element = wait.until(
        EC.presence_of_element_located((AppiumBy.ID, "live.swag.app.test:id/credit_balance"))
    )
    initial_credits_ui = int(credit_element.text.replace(",", ""))

    assert initial_credits_ui == initial_credits_api, (
        f"前置條件錯誤：UI ({initial_credits_ui}) 與 API ({initial_credits_api}) 初始不一致"
    )

    # 觸發步驟：進行打賞操作（模擬網路延遲）
    enter_live_room(driver, "test_streamer_001")
    tap_gift_button(driver, gift_id="rose_gift")
    send_gift(driver)

    # 立即讀取 UI 顯示（樂觀更新應已更新顯示）
    import time
    time.sleep(0.5)  # 等待 UI 更新但網路請求可能還未完成
    credits_ui_after = int(credit_element.text.replace(",", ""))

    # 等待請求完成
    time.sleep(3)
    credits_api_after = get_credits_from_api("test_mobile_001")
    credits_ui_final = int(credit_element.text.replace(",", ""))

    print(f"初始點數：UI={initial_credits_ui}, API={initial_credits_api}")
    print(f"打賞後即時 UI：{credits_ui_after}")
    print(f"請求完成後：UI={credits_ui_final}, API={credits_api_after}")

    # 驗證：最終 UI 顯示應與 API 一致
    assert credits_ui_final == credits_api_after, (
        f"Bug 確認：UI 顯示 {credits_ui_final}，API 實際 {credits_api_after}，"
        f"前端與後端點數不同步"
    )
```

---

## MRS 報告格式

每次復現完成後，產出標準格式的 MRS 報告：

```markdown
# MRS 報告 — {Bug ID}：{Bug 標題}

**復現狀態**：Confirmed / Flaky / Unconfirmed
**觸發機率**：100% / 約 X%（Flaky 時填寫）
**測試類別**：{類別A：單元測試 / 類別B：整合測試 / 類別C：安全測試 / 類別D：並發測試 / 類別E：Robot E2E / 類別F：Appium}
**測試檔案**：{完整路徑}
**測試函式**：{test_function_name 或 Robot Test Case 名稱}

## 前置條件（Setup）
| 條件 | 值 |
|------|-----|
| 測試環境 | swag-test.internal（隔離環境，非正式環境）|
| 用戶點數 | 1000 點（測試帳號）|
| 遊戲狀態 | BETTING（接受下注中）|
| Redis 冪等保護 | 無（Bug 狀態）|
| ECPay 沙盒模式 | 啟用 |

## 觸發步驟（Trigger）
1. 建立初始狀態為 1000 點的測試帳號
2. 同時發送 10 個各扣 200 點的下注請求（asyncio.gather）
3. 等待所有請求完成
4. 查詢最終餘額

## 觀察到的錯誤結果（Observed）
- 預期：只有 5 個下注成功（1000 / 200 = 5），餘額變為 0
- 實際：所有 10 個請求都回應成功，餘額變為 -1000（超扣）← Bug 確認

## 修復後的正確結果（Expected After Fix）
- 加入 Redis 分散式鎖後，並發請求依序執行
- 第 6 個請求因餘額不足而被拒絕（返回 400 InsufficientCreditsError）
- 最終餘額為 0（正確扣除 5 × 200 = 1000）

## 復現測試程式碼位置
tests/reproduce/test_concurrent_race_condition.py::test_reproduce_concurrent_bet_overdraft

## 此 MRS 已沉澱至知識庫
- knowledge-base/reproduce-scenarios.md#SCENE-SWAG-CRED-001
```

---

## 無法復現時的處理流程

當復現結果為 **Unconfirmed**，執行以下補蒐動作後回到 Stage 1：

```
1. 確認 SWAG 環境差異
   → 測試環境 vs 正式環境的 Redis 版本是否一致？
   → 測試環境的 ECPay 沙盒簽章邏輯是否與正式環境一致？
   → Kafka 消費者設定是否相同（batch size、ack mode）？
   → Django/FastAPI 版本差異是否影響並發行為？

2. 補蒐 SWAG 特有日誌
   → 取得 Bug 發生當下的完整 Python traceback
   → 取得 Redis 鎖的 TTL 設定（排除鎖過期問題）
   → 取得支付回調的完整 HTTP request/response 日誌
   → 取得 Celery 任務佇列的執行日誌

3. 重新評估觸發條件
   → 是否需要特定的並發量才能觸發（Gunicorn workers 數量）？
   → 是否只在特定支付閘道（ECPay vs 支付寶）才能觸發？
   → 是否依賴特定的資料庫事務隔離等級（READ COMMITTED vs SERIALIZABLE）？
   → 行動端問題是否只在特定 OS 版本（iOS/Android）才能觸發？

4. 回報 Stage 1
   輸出：reports/reproduce-unconfirmed-{bug-id}.md
   包含：嘗試過的復現方法、環境差異清單、建議補蒐的資訊清單
```
