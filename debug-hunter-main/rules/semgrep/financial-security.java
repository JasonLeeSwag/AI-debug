// Semgrep 測試 fixture：對應 financial-security.yml。
// 約定：以 ruleid 註解標註「應命中」、以 ok 註解標註「不應命中」（見各方法上方）。
// 執行：semgrep --test rules/semgrep/
import java.math.BigDecimal;

class FinancialSecurityFixtures {

    // RULE-SEC-101 IDOR：whole-method 規則命中於方法簽章行
    // ruleid: idor-money-sink-missing-ownership
    public Object withdrawVuln(@RequestParam Long accountId, @RequestParam BigDecimal amount) {
        if (amount.signum() <= 0) { throw new RuntimeException("bad"); }
        return walletService.debit(accountId, amount);   // 無歸屬校驗 → 命中
    }

    // ok: idor-money-sink-missing-ownership
    public Object withdrawSafe(@RequestParam Long accountId, @RequestParam BigDecimal amount) {
        if (amount.signum() <= 0) { throw new RuntimeException("bad"); }
        Account acc = repo.findByIdAndUserId(accountId, currentUser());  // sanitizer
        return walletService.debit(accountId, amount);
    }

    // RULE-SEC-102 金額未驗
    // ruleid: amount-sink-missing-validation
    public void transferVuln(@RequestParam BigDecimal amount) {
        walletService.debit(fromId, amount);             // 無 signum/上限校驗 → 命中
    }

    // ok: amount-sink-missing-validation
    public void transferSafe(@RequestParam BigDecimal amount) {
        if (amount.signum() <= 0) { throw new RuntimeException("bad"); }   // sanitizer
        walletService.debit(fromId, amount);
    }

    // RULE-SEC-106 mass assignment
    // ruleid: mass-assignment-entity-persist
    public Object updateVuln(@RequestBody Account account) {
        accountRepo.updateById(account);                 // 直接綁實體並寫入 → 命中
        return account;
    }

    // ok: mass-assignment-entity-persist
    public Object updateSafe(@RequestBody AccountUpdateReq req) {
        Account acc = accountRepo.selectById(currentUser());
        acc.setNickname(req.getNickname());              // DTO 白名單逐欄賦值
        accountRepo.updateById(acc);
        return acc;
    }

    // RULE-SEC-109 SQL 注入
    public Object reportVuln(@RequestParam String accountId) {
        // ruleid: dynamic-sql-injection-ledger
        return jdbcTemplate.queryForList("SELECT * FROM ledger WHERE account_id = " + accountId);  // 命中
    }

    public Object reportSafe(@RequestParam String accountId) {
        // ok: dynamic-sql-injection-ledger
        return jdbcTemplate.queryForList("SELECT * FROM ledger WHERE account_id = ?", accountId);   // 參數化
    }

    // RULE-FIN-003 禁止 double/float 處理金額
    // ruleid: no-double-float-for-money
    private double balance;
    // ruleid: no-double-float-for-money
    private double profitRate;
    // ok: no-double-float-for-money
    private int retryCount;
}
