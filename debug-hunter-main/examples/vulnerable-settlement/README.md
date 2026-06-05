# 端到端示範：IDOR 越權提款閉環

> 證明 debug-hunter 的「DETECT → REPRODUCE(PoC) → VERIFY」在真實程式上成立。
> 刻意零外部依賴（純 JDK），可立即編譯執行——符合「demo 必須能真 build & test」原則。

## 執行

```bash
cd examples/vulnerable-settlement
javac IdorDemo.java && java IdorDemo
# exit 0 = 閉環成立
```

## 實際輸出（已驗證）

```
[DETECT]  taint: request.accountId → withdraw() → ledger.debit()，path 上無歸屬校驗 → candidate finding
[REPRODUCE] PoC：A(userId=1) 帶入 B 的 accountId=200 提款 1000
           漏洞版結果：B 餘額 1000 → 0，INV-ST-01(歸屬) 違反=true
           ✔ PoC 成功（漏洞存在，攻擊得逞）
[VERIFY]   套用修復版（歸屬校驗），重跑同一攻擊
           攻擊被擋：帳戶歸屬不符 accountId=200
           ✔ 驗收通過（攻擊不再成功 ∧ 不變量恆成立）
[VERIFY+]  負面對照：本人提自己的帳 → 正常流程未被誤殺（降誤報）
=== 結果：全部通過 ✅ 閉環成立 ===
```

## 對應知識庫

| 階段 | 知識檔 |
|------|--------|
| 漏洞模式 | `financial-security-patterns.md#PAT-SEC-101` |
| 攻擊成功判據 | `financial-invariants.md#INV-ST-01` |
| 修復 ground-truth | `authorization-ownership-matrix.md` |
| 回歸語料 | `attack-regression-corpus.md#CORP-001` |
| 證據門檻 | `finding-evidence-standard.md`（candidate→confirmed） |
| 靜態規則 | `rules/semgrep/financial-security.yml#idor-money-sink-missing-ownership` |

## 重點

- **PoC「成功」的定義 = 不變量被違反**（INV-ST-01），不是「丟例外」——這是安全驗收與功能測試的關鍵差異。
- **負面對照**（本人提款應成功）確保修復未誤殺正常流程，呼應 finding-evidence-standard 的降誤報精神。
- 真實系統請改用 Spring `@RestController` + MyBatis `selectByIdAndUserId`，邏輯與此 demo 等價。
