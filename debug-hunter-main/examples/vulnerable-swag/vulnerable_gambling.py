"""
SWAG 博弈遊戲漏洞示例程式碼（教學用途）
此程式碼故意包含安全漏洞，用於 QA 教育訓練
"""

import random  # PAT-GAM-001: 不安全！應使用 secrets
from decimal import Decimal  # 正確引入（但下面沒用到）
from typing import Optional

# ==========================================
# 漏洞一：使用 random 模組（PAT-GAM-001）
# ==========================================
class VulnerableGamblingService:
    """
    這個類別示範了多個安全漏洞。
    實際 SWAG 系統不應這樣寫！
    """

    MAX_BET = 10000  # 最大押注

    def determine_dragon_tiger_result(self, deck: list) -> str:
        """
        PAT-GAM-001 VULNERABLE: 使用 Python random 模組決定龍虎鬥結果
        攻擊者如果能預測 random 的種子，就能預知結果
        """
        dragon_card = random.choice(deck)  # 漏洞！
        tiger_card = random.choice(deck)   # 漏洞！

        if dragon_card > tiger_card:
            return "dragon"
        elif tiger_card > dragon_card:
            return "tiger"
        else:
            return "tie"

    def calculate_payout(self, bet_amount, win_side: str, result: str) -> float:
        """
        PAT-GAM-002 VULNERABLE: 使用 float 計算賠付，有精度問題
        """
        if win_side == result:
            if result == "tie":
                return bet_amount * 8.0  # float 計算，有精度問題！
            else:
                return bet_amount * 1.95  # float 計算，有精度問題！
        return 0.0

    def place_bet(self, user_id: int, amount: float, side: str):
        """
        PAT-CRED-003 VULNERABLE: 先檢查再更新，有 TOCTOU 競態問題
        PAT-GAM-004 VULNERABLE: 無最大賠付校驗
        """
        # 先查詢餘額
        user = User.objects.get(id=user_id)
        if user.points < amount:
            raise ValueError("餘額不足")

        # 問題：查完後到這裡之間可能有其他請求也在扣款！
        user.points -= amount  # TOCTOU 漏洞！
        user.save()


# ==========================================
# 漏洞二：支付回調未驗簽（PAT-PAY-001）
# ==========================================
class VulnerablePaymentCallback:

    def ecpay_callback(self, request_data: dict):
        """
        PAT-PAY-001 VULNERABLE: 直接信任回調資料，未驗簽
        攻擊者可以偽造回調，憑空獲取點數！
        """
        # 漏洞：沒有驗簽！
        trade_status = request_data.get('RtnCode')
        amount = request_data.get('TradeAmt')
        merchant_id = request_data.get('MerchantTradeNo')

        if trade_status == '1':  # 1 = 成功
            # 直接充值，沒有驗證簽章和比對訂單金額
            self.credit_user_points(merchant_id, amount)  # 漏洞！

    def credit_user_points(self, order_id: str, amount: int):
        """
        PAT-CRED-003 VULNERABLE: 無冪等保護
        同一個 order_id 被呼叫兩次，點數會充兩次
        """
        order = Order.objects.get(id=order_id)
        user = User.objects.get(id=order.user_id)
        # 漏洞：沒有 Redis 冪等保護
        # 漏洞：user.points = user.points + amount 非原子操作
        user.points = user.points + amount  # TOCTOU！
        user.save()
        order.status = 'paid'
        order.save()


# ==========================================
# 安全版本（示範修復後的寫法）
# ==========================================
import secrets
from decimal import Decimal, ROUND_HALF_DOWN
from django.db.models import F
from django.db import transaction
import redis

REDIS_CLIENT = redis.Redis()

class SecureGamblingService:
    """
    這是修復後的安全版本
    """

    def determine_dragon_tiger_result(self, deck: list) -> str:
        """
        RULE-GAM-001 COMPLIANT: 使用 secrets 模組，密碼學安全
        """
        dragon_card = secrets.choice(deck)  # ✅ 密碼學安全
        tiger_card = secrets.choice(deck)   # ✅ 密碼學安全

        if dragon_card > tiger_card:
            return "dragon"
        elif tiger_card > dragon_card:
            return "tiger"
        else:
            return "tie"

    def calculate_payout(self, bet_amount: Decimal, win_side: str, result: str) -> Decimal:
        """
        RULE-GAM-002 COMPLIANT: 使用 Decimal，精確計算
        """
        if win_side == result:
            if result == "tie":
                payout = bet_amount * Decimal('8.0')
            else:
                payout = bet_amount * Decimal('1.95')
            return payout.quantize(Decimal('0.01'), rounding=ROUND_HALF_DOWN)
        return Decimal('0')

    @transaction.atomic
    def place_bet(self, user_id: int, amount: Decimal, side: str, request_id: str):
        """
        RULE-GAM-003 COMPLIANT: 分散式鎖 + 原子扣款
        RULE-CRED-002 COMPLIANT: SELECT FOR UPDATE
        RULE-CRED-003 COMPLIANT: 冪等保護
        """
        # 冪等保護
        idempotent_key = f"bet:{user_id}:{request_id}"
        if not REDIS_CLIENT.set(idempotent_key, "1", nx=True, ex=3600):
            raise DuplicateRequestError("重複請求")

        # 原子扣款（有餘額才扣）
        updated = User.objects.filter(
            id=user_id,
            points__gte=amount  # 餘額必須 >= amount
        ).update(
            points=F('points') - amount  # ✅ 原子更新
        )

        if updated == 0:
            REDIS_CLIENT.delete(idempotent_key)
            raise InsufficientPointsError("餘額不足")
