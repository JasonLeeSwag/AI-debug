---
file_id: financial-invariants
kind: invariant
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 180
owner: knowledge-writer-agent
external_refs: ["CWE-840"]
---

# 金融不變量知識庫（Invariant-Driven Detection）

> 檔案路徑：knowledge-base/financial-invariants.md
> 用途：以「**永遠必須成立的財務性質**」作為偵測與驗收的最強防線。
> 核心理念：**特徵比對抓「已知寫法」，不變量抓「未知後果」。** 任何 bug 或攻擊，只要最終違反資金不變量，就會被攔截——即使我們沒收錄那個特定模式。
> 使用者：detector（轉為斷言/查詢）、verifier（驗收）、reproducer（PoC 成功判定）、線上對帳（runtime guard）

---

## 為何不變量是最後一道、也是最強一道防線

特徵庫永遠落後於攻擊者。但**「系統內金錢總量守恆」「餘額不為負」這類性質，無論用什麼新手法攻擊，被突破時都會違反**。因此不變量是：
1. **偵測補網**：把「找特定錯誤寫法」升級為「找任何違反性質的後果」
2. **驗收金標準**：修復後不變量必須恆成立（比「測試通過」更強）
3. **線上守衛**：可做成 runtime assertion / 每日對帳，事中攔截、事後發現

不變量分三層：**單筆交易內**（I-TXN）、**帳戶/系統狀態**（I-STATE）、**時間序列/對帳**（I-TIME）。

---

## I-TXN：單筆交易內不變量（同一交易邊界內檢查）

| 代碼 | 不變量 | 違反含義 | 檢查方式 |
|------|--------|---------|---------|
| INV-TXN-01 | **借貸平衡**：Σ debit = Σ credit（雙式記帳每筆淨額為 0） | 憑空造錢/銷錢 | 交易提交前斷言分錄總和為 0 |
| INV-TXN-02 | **金額非負且在域內**：amount > 0 ∧ scale ≤ 資產精度 ∧ ≤ 上限 | 參數竄改 PAT-SEC-102 | 入口校驗 + 服務層再驗 |
| INV-TXN-03 | **手續費邊界**：0 ≤ fee ≤ principal ∧ fee = 後端重算值 | 費用篡改/負費 | 後端重算比對 |
| INV-TXN-04 | **結算方向自洽**：盈虧方向與行情方向、持倉方向一致 | PAT-BIZ-003 平局錯誤 | 方向交叉校驗 |
| INV-TXN-05 | **分配殘差守恆**：Σ 各方分得 = 總額（捨入殘差有明確歸屬） | 拆分捨入吞錢/造錢 | 分配後比對總和 |
| INV-TXN-06 | **收益率上下限**：impliedRate ∈ [min, max] | PAT-BIZ-002 異常收益 | settlementGuard 校驗 |

**INV-TXN-01 範例（最關鍵）**：
```java
// 每筆業務交易結束前，所有分錄淨額必為 0
BigDecimal net = entries.stream()
    .map(LedgerEntry::signedAmount)            // debit 為負、credit 為正（或反之）
    .reduce(BigDecimal.ZERO, BigDecimal::add);
if (net.compareTo(BigDecimal.ZERO) != 0)
    throw new InvariantViolation("INV-TXN-01 借貸不平衡 net=" + net + " txn=" + txnId);
```

---

## I-STATE：帳戶/系統狀態不變量（任一時刻必成立）

| 代碼 | 不變量 | 違反含義 | 檢查方式 |
|------|--------|---------|---------|
| INV-ST-01 | **餘額非負**（除非明確授信帳戶） | TOCTOU 雙花 PAT-SEC-103 | DB CHECK 約束 + 原子扣款 |
| INV-ST-02 | **餘額 = 初始 + Σ 該帳戶所有分錄** | 漏記/重複記/覆蓋 PAT-CON-004 | 對帳重算比對 |
| INV-ST-03 | **系統內某資產總量守恆**：Σ 所有使用者餘額 + 平台帳 = 鑄造/入金總額 − 出金總額 | 全域造錢/漏錢 | 每日全量對帳 |
| INV-ST-04 | **熱錢包鏈上餘額 ≥ 使用者負債總額**（儲備充足，crypto） | 擠兌/挪用 | 定時 proof-of-reserve |
| INV-ST-05 | **狀態機單調**：訂單/提款狀態僅依合法躍遷圖前進，不可回退 | 重複入帳/狀態竄改 | 狀態機強制 + 樂觀鎖 |
| INV-ST-06 | **凍結 + 可用 = 總額**：available + frozen = total | 凍結邏輯漏洞 | 每次變更後斷言 |

**INV-ST-03 範例（全域守恆，對帳核心）**：
```java
// 每日對帳：系統不該無中生有
BigDecimal userTotal   = walletMapper.sumAllBalances(coinId);
BigDecimal platformAcc = walletMapper.platformBalance(coinId);
BigDecimal expected    = depositMapper.totalIn(coinId)
                          .subtract(withdrawMapper.totalOut(coinId));
if (userTotal.add(platformAcc).compareTo(expected) != 0)
    alert.critical("INV-ST-03 資產守恆破裂 coin=" + coinId
        + " 帳面=" + userTotal.add(platformAcc) + " 應有=" + expected);
```

---

## I-TIME：時間序列 / 對帳不變量（跨時間比對）

| 代碼 | 不變量 | 違反含義 | 檢查方式 |
|------|--------|---------|---------|
| INV-T-01 | **每筆資金變動可追溯**：每個餘額 delta 對應唯一審計分錄 | PAT-SEC-110 抵賴 | append-only 審計比對 |
| INV-T-02 | **冪等不重複**：同一業務鍵僅產生一次資金效果 | PAT-CON-001 重複結算 | 業務鍵去重統計 |
| INV-T-03 | **內外對帳一致**：我方帳 = 支付閘道/交易所帳 | 偽造回調 PAT-SEC-104 | T+1 三方對帳 |
| INV-T-04 | **重放零增益**：重送同請求不改變系統狀態 | PAT-SEC-107 重放 | PoC 重送後狀態比對 |

---

## 如何把不變量接入各 Stage

### DETECT（偵測補網）
對每條資金流，問：「這裡若出錯，會違反哪條不變量？該不變量有沒有被斷言/約束保護？」沒有保護 → Finding（缺防護，非缺特徵）。

### REPRODUCE（PoC 成功判定）
安全 PoC 的「成功」定義 = **使某條不變量被違反**。例：雙花 PoC 成功 = INV-ST-01 餘額變負。

### VERIFY（驗收金標準）
```
修復驗收 = 復現測試由失敗轉通過
         ∧ 相關不變量在「攻擊重跑 + 影子流量 + 模糊測試輸入」下恆成立
```

### RUNTIME GUARD（事中/事後）
- 交易邊界內：INV-TXN-* 做成 assertion，違反即回滾並告警
- 每日批次：INV-ST-03 / INV-T-03 全量對帳，差異即 P0

---

## 屬性測試 / 蛻變測試（Property-based & Metamorphic）

不變量天然適合屬性測試——用隨機輸入轟炸，斷言不變量恆成立，可挖出特徵庫沒收錄的邊界。

```java
// jqwik 範例：任意金額序列下，總量守恆
@Property
void totalConserved(@ForAll("txns") List<Transfer> txns) {
    BigDecimal before = ledger.totalSupply(COIN);
    txns.forEach(t -> { try { engine.apply(t); } catch (Exception ignore) {} });
    assertThat(ledger.totalSupply(COIN)).isEqualByComparingTo(before); // INV-ST-03
}
```

**蛻變關係（無需預期答案，最適合金融）**：
- 結算順序無關：`settle(A,B,C)` 與 `settle(C,A,B)` 結果相同（揪出順序相依/競態）
- 拆分不變：一筆 100 拆成 60+40 兩筆，總效果應等於一筆 100（揪出捨入吞錢）
- 重放零增益：執行一次與重放後，狀態一致（INV-T-04）

> 與 `oss-debug-security-loop.md` 的 Jazzer fuzzing 結合：fuzzer 找輸入，不變量當 oracle 判定是否破防。

---

## 不變量登錄維護

| 日期 | 動作 | 不變量 | 對應 Pattern |
|------|------|--------|-------------|
| 2026-06 | 建立 | INV-TXN-01~06、INV-ST-01~06、INV-T-01~04 | 全面 |
