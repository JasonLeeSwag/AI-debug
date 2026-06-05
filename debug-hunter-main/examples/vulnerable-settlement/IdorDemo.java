// 端到端示範：IDOR 越權提款（PAT-SEC-101）的「偵測 → 復現(PoC) → 驗收」閉環。
// 刻意零外部依賴（純 JDK），可直接 `javac IdorDemo.java && java IdorDemo` 執行驗證。
// 對應知識庫：PAT-SEC-101 / INV-ST-01 / authorization-ownership-matrix / CORP-001。
import java.math.BigDecimal;
import java.util.HashMap;
import java.util.Map;

public class IdorDemo {

    // ---- 極簡帳本：account_id -> (owner_user_id, balance) ----
    record Account(long ownerUserId, BigDecimal balance) {}

    static final class Ledger {
        final Map<Long, Account> accounts = new HashMap<>();
        Ledger seed(long accId, long owner, String bal) {
            accounts.put(accId, new Account(owner, new BigDecimal(bal))); return this;
        }
        BigDecimal balance(long accId) { return accounts.get(accId).balance(); }
        long owner(long accId) { return accounts.get(accId).ownerUserId(); }
        void debit(long accId, BigDecimal amt) {
            Account a = accounts.get(accId);
            accounts.put(accId, new Account(a.ownerUserId(), a.balance().subtract(amt)));
        }
    }

    static class AccessDeniedException extends RuntimeException {
        AccessDeniedException(String m) { super(m); }
    }

    // ====== 漏洞版：accountId 直接來自請求，無歸屬校驗（PAT-SEC-101）======
    static void withdrawVulnerable(Ledger l, long callerUserId, long accountId, BigDecimal amount) {
        l.debit(accountId, amount);                 // ← 任何人帶任意 accountId 即可提款
    }

    // ====== 修復版：歸屬錨定於認證主體（authorization-ownership-matrix）======
    static void withdrawFixed(Ledger l, long callerUserId, long accountId, BigDecimal amount) {
        if (l.owner(accountId) != callerUserId)     // ← 歸屬校驗：accountId 必須屬於 caller
            throw new AccessDeniedException("帳戶歸屬不符 accountId=" + accountId);
        if (amount.signum() <= 0)                   // 數值域校驗（PAT-SEC-102 順帶）
            throw new IllegalArgumentException("金額必須為正");
        l.debit(accountId, amount);
    }

    // INV-ST-01：餘額非負（任一時刻必成立）。攻擊成功的客觀判據 = 此不變量被違反。
    static boolean invStAccountBelongsViolated(Ledger l, long victimAcc, long victimUser, BigDecimal before) {
        // 受害者未授權卻被動帳 → 視為越權成功（餘額被他人改變）
        return l.owner(victimAcc) == victimUser && l.balance(victimAcc).compareTo(before) < 0;
    }

    public static void main(String[] args) {
        int failures = 0;

        System.out.println("=== debug-hunter 端到端 demo：PAT-SEC-101 IDOR 越權提款 ===\n");

        // STAGE 1 DETECT（敘述）：taint = @RequestParam accountId → walletService.debit，無歸屬 sanitizer
        System.out.println("[DETECT]  taint: request.accountId → withdraw() → ledger.debit()，path 上無歸屬校驗 → candidate finding");

        // STAGE 2.5 REPRODUCE：攻擊 PoC —— user A(id=1) 用 user B(id=2) 的 accountId 提款
        System.out.println("[REPRODUCE] PoC：A(userId=1) 帶入 B 的 accountId=200 提款 1000");
        {
            Ledger l = new Ledger().seed(100, 1, "0").seed(200, 2, "1000");
            BigDecimal bBefore = l.balance(200);
            withdrawVulnerable(l, /*caller A*/1, /*B 的帳*/200, new BigDecimal("1000"));
            boolean violated = invStAccountBelongsViolated(l, 200, 2, bBefore);
            System.out.println("           漏洞版結果：B 餘額 " + bBefore + " → " + l.balance(200)
                    + "，INV-ST-01(歸屬) 違反=" + violated);
            if (!violated) { System.out.println("  ✗ 預期攻擊應成功，PoC 無效"); failures++; }
            else System.out.println("           ✔ PoC 成功（漏洞存在，攻擊得逞）");
        }

        // STAGE 4 VERIFY：套用修復版，同一攻擊應失敗，不變量恆成立
        System.out.println("\n[VERIFY]   套用修復版（歸屬校驗），重跑同一攻擊");
        {
            Ledger l = new Ledger().seed(100, 1, "0").seed(200, 2, "1000");
            BigDecimal bBefore = l.balance(200);
            boolean blocked = false;
            try {
                withdrawFixed(l, 1, 200, new BigDecimal("1000"));
            } catch (AccessDeniedException e) {
                blocked = true;
                System.out.println("           攻擊被擋：" + e.getMessage());
            }
            boolean violated = invStAccountBelongsViolated(l, 200, 2, bBefore);
            boolean ok = blocked && !violated && l.balance(200).compareTo(bBefore) == 0;
            System.out.println("           修復版結果：B 餘額不變=" + (l.balance(200).compareTo(bBefore)==0)
                    + "，攻擊被擋=" + blocked + "，INV-ST-01 恆成立=" + !violated);
            if (!ok) { System.out.println("  ✗ 修復驗收失敗"); failures++; }
            else System.out.println("           ✔ 驗收通過（攻擊不再成功 ∧ 不變量恆成立）");
        }

        // 正向對照（負面測試）：合法本人提款應成功（驗證修復未誤殺正常流程，降誤報）
        System.out.println("\n[VERIFY+]  負面對照：本人 B(userId=2) 提自己的帳，應成功");
        {
            Ledger l = new Ledger().seed(200, 2, "1000");
            boolean ok = true;
            try { withdrawFixed(l, 2, 200, new BigDecimal("300")); }
            catch (Exception e) { ok = false; }
            ok = ok && l.balance(200).compareTo(new BigDecimal("700")) == 0;
            System.out.println("           本人提款後餘額=" + l.balance(200) + "，正常流程未被誤殺=" + ok);
            if (!ok) { System.out.println("  ✗ 修復誤殺了正常流程（誤報風險）"); failures++; }
            else System.out.println("           ✔ 正常流程不受影響");
        }

        System.out.println("\n=== 結果：" + (failures == 0 ? "全部通過 ✅ 閉環成立" : (failures + " 項失敗 ❌")) + " ===");
        System.exit(failures == 0 ? 0 : 1);
    }
}
