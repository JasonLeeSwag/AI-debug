---
file_id: financial-bug-patterns
kind: pattern-catalog
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 180
owner: knowledge-writer-agent
external_refs: ["CWE-681", "CWE-190", "CWE-362"]
---

# 金融 Bug 模式知識庫

> 檔案路徑：knowledge-base/financial-bug-patterns.md
> 更新規則：每次事後檢視後，由 `agents/knowledge-writer.md` 自動追加
> 格式：每個模式包含觸發條件、特徵碼、修復策略、反哺規則
> 最後更新：settlement-flow-sample 掃描後（知識沉澱版 v1.2）
> 相關文件：[ai-scan-false-positive-patterns.md](./ai-scan-false-positive-patterns.md) — AI 掃描誤報模式與驗證 SOP

---

## 如何使用

1. 偵測階段：載入此檔案，逐一比對程式碼中的觸發特徵
2. 分類階段：依模式的預設優先等級快速判定風險
3. 修復階段：直接套用對應的修復策略
4. 新增模式：發現新類型 Bug 後，在檔案末尾新增條目

---

## Pattern 索引

| 代碼 | 名稱 | 預設等級 | 來源事件 | 案例數 |
|------|------|---------|---------|--------|
| PAT-FIN-002 | double/float 處理金額 | P0 | 靜態分析 | — |
| PAT-FIN-003 | BigDecimal.equals() 比較 | P1 | 靜態分析 | — |
| PAT-FIN-004 | divide() 未指定 RoundingMode | P1 | 靜態分析 | — |
| PAT-FIN-005 | 多資產精度硬編碼 scale | P0 | 設計審查 | — |
| PAT-FIN-006 | 分配/拆分捨入殘差未處理（salami） | P0 | 業務分析 | — |
| PAT-FIN-007 | 時間戳單位混淆（ms/s）與時區邊界 | P1 | 設計審查 | — |
| PAT-FIN-008 | 金額以最小單位存 long 的整數溢位 | P1 | 設計審查 | — |
| PAT-CON-001 | Kafka 消費者缺乏冪等保護 | P0 | 壓力測試 · SettlementFlow.java | 2 🆕 |
| PAT-CON-002 | @Transactional 靜默失效 | P0 | 代碼審查 | — |
| PAT-CON-003 | 分散式鎖 TTL 設計缺陷 | P1 | 事後檢視 | — |
| PAT-CON-004 | 錢包批量讀取後並發更新無行鎖 | P0 | SettlementFlow.java | 1 🆕 |
| PAT-CON-005 | Retry 場景狀態標記非冪等設計 | P1 | SettlementFlow.java | 1 🆕 |
| PAT-SCH-001 | PowerJob 多 Worker 資料競爭 | P1 | 壓力測試 | — |
| PAT-BIZ-001 | 委託時間窗口競態條件 | P1 | 業務分析 | — |
| PAT-BIZ-002 | 結算結果缺乏業務合理性校驗 | P0 | 事後檢視 | — |
| PAT-BIZ-003 | 外部行情 API 失敗靜默返回預設值 | P0 | SettlementFlow.java | 1 🆕 |

---

## PAT-FIN-002：double/float 處理金額

**描述**：
使用 `double` 或 `float` 型別儲存或計算金融數值，導致浮點精度誤差累積。單筆誤差可能極小，但在高流量下大量累加後，誤差可達數元甚至更多。

**觸發特徵**：
```java
// 特徵 1：金額欄位型別為 double 或 float
private double amount;
private float profitRate;

// 特徵 2：BigDecimal 轉 double 後再計算
double profit = order.getAmount().doubleValue() * rate;

// 特徵 3：比較金額使用 ==
if (amount1 == amount2) { ... }
```

**修復策略**：PAT-FIN-002 → 使用策略 4（BigDecimal 精確計算）

```java
// ✅ 正確：全程 BigDecimal
private BigDecimal amount;
BigDecimal profit = amount.multiply(rate)
    .setScale(8, RoundingMode.HALF_DOWN);
// 比較用 compareTo
if (amount1.compareTo(amount2) == 0) { ... }
```

**反哺規則**：RULE-FIN-003

---

## PAT-FIN-003：BigDecimal.equals() 比較

**描述**：
`BigDecimal.equals()` 同時比較數值與 scale，導致 `1.0.equals(1.00)` 回傳 `false`，在金額比較邏輯中產生隱性錯誤。

**觸發特徵**：
```java
if (calculatedAmount.equals(expectedAmount)) { ... }
if (fee.equals(BigDecimal.ZERO)) { ... }
```

**修復策略**：
```java
// ✅ 使用 compareTo
if (calculatedAmount.compareTo(expectedAmount) == 0) { ... }
if (fee.compareTo(BigDecimal.ZERO) == 0) { ... }
```

**反哺規則**：RULE-FIN-004

---

## PAT-CON-001：Kafka 消費者缺乏冪等保護

**描述**：
Kafka 的 at-least-once 語意保證訊息至少被投遞一次，在網路抖動、Rebalance、Consumer 重啟等情況下，同一訊息可能被重複投遞，若消費者沒有冪等保護，會導致重複結算、重複入帳。

**觸發特徵**：
```java
// 特徵 A：直接在 @KafkaListener 方法內執行業務邏輯，無冪等防護
@KafkaListener(topics = "settlement-topic")
public void onSettlement(SettlementMessage msg) {
    settlementService.doSettle(msg.getOrderId()); // ← 無防重
}
```

**⚠️ 變體 B（來自 SettlementFlow.java · 2024）：批次 hasError 不 ACK 造成部分雙重結算**

批次消費時，以 `AtomicBoolean hasError` 決定整批是否 ACK。
任一筆失敗 → 整批不 ACK → Kafka 重送整批 → 已成功的訂單再次結算。

```java
// 觸發特徵 B：hasError 控制整批 ACK，無單筆冪等
AtomicBoolean hasError = new AtomicBoolean(false);
Flux.fromIterable(batch)
    .flatMap(msg -> process(msg)
        .onErrorResume(ex -> {
            hasError.set(true);
            return Mono.empty(); // 繼續跑其他，成功的已入帳
        }))
    .doOnSuccess(_ -> {
        if (!hasError.get()) ack.acknowledge();
        // ← 不 ACK 時，已成功的訂單再次被重送處理
    }).subscribe();
```

**修復策略**：PAT-CON-001 → 使用策略 3（雙層冪等保護）

```java
// 變體 B 的修復：Runner 層級 Redis 防重 + DB 狀態確認
String idempotentKey = "settle:runner:" + runner.getId();
Boolean isFirst = redisTemplate.opsForValue()
    .setIfAbsent(idempotentKey, "processing", Duration.ofHours(24));
if (Boolean.FALSE.equals(isFirst)) {
    log.warn("Runner 已在處理或已結算，跳過 runnerId={}", runner.getId());
    return Mono.empty();
}
// 成功後改為 settled 狀態，7 天內永久防重
// 失敗時清除 key，允許 Kafka 重送重試
```

**反哺規則**：RULE-CON-001、**RULE-CON-006（新增·批次 Listener 單筆冪等）**

---

## PAT-CON-002：@Transactional 靜默失效

**描述**：
Spring 的 `@Transactional` 在多種情況下會靜默失效（不拋出錯誤，但事務根本沒有生效），導致部分資料更新成功、部分失敗，形成資料不一致的狀態。

**觸發特徵**：
```java
// 失效場景 1：private 方法加 @Transactional
@Transactional
private void doSettle() { ... }

// 失效場景 2：同類內部直接呼叫（繞過 Spring 代理）
public void settle() {
    this.doSettle(); // ← 繞過代理，@Transactional 不生效
}

// 失效場景 3：異常被吃掉，事務不回滾
@Transactional
public void settle() {
    try {
        updateOrder();
        updateWallet(); // 失敗...
    } catch (Exception e) {
        log.error("錯誤", e); // ← 吃掉異常，資料半寫入！
    }
}

// 失效場景 4：未指定 rollbackFor，非 RuntimeException 不回滾
@Transactional
public void settle() throws IOException { ... }
```

**修復策略**：
```java
// ✅ 正確：public 方法、明確 rollbackFor、不吃異常
@Transactional(rollbackFor = Exception.class,
               isolation = Isolation.READ_COMMITTED,
               timeout = 30)
public SettlementResult doSettle(Long orderId) {
    // 不用 try-catch 吃掉異常
    // 讓異常自然傳播，觸發事務回滾
}
```

**反哺規則**：RULE-CON-002、RULE-CON-003

---

## PAT-BIZ-002：結算結果缺乏業務合理性校驗

**描述**：
結算服務計算出結果後，缺乏對「業務合理性」的最終校驗。即使計算邏輯存在 Bug，也沒有任何機制能在資金真正入帳前攔截異常。

**觸發特徵**：
```java
// 特徵：計算完直接入帳，沒有業務邊界校驗
BigDecimal profit = calculateProfit(order, rate);
walletService.credit(order.getUserId(), profit); // ← 無校驗
```

**修復策略**：PAT-BIZ-002 → 使用策略 5（業務合理性守衛）

```java
// ✅ 正確：結算前強制校驗
settlementGuard.validate(order, profit);
walletService.credit(order.getUserId(), profit);

// SettlementGuard 的實作
public void validate(Order order, BigDecimal profit) {
    // 收益不能為負
    if (profit.compareTo(ZERO) < 0)
        throw new SettlementValidationException("收益為負數");

    // 收益率合理性（最關鍵的防線）
    BigDecimal impliedRate = profit.divide(order.getAmount(), 6, HALF_UP);
    if (impliedRate.compareTo(maxProfitRate) > 0) {
        alertService.sendCriticalAlert("結算收益率異常: " + impliedRate);
        throw new SettlementValidationException("收益率超出上限");
    }

    // 單筆賠付上限
    if (profit.compareTo(maxSinglePayout) > 0)
        throw new SettlementValidationException("單筆賠付超出上限");
}
```

**反哺規則**：RULE-BIZ-001

---

## PAT-CON-004：錢包批量讀取後並發更新無行鎖

**描述**：
批次結算時，先將多個錢包讀取進記憶體 Map（`batchFindWallets`），在記憶體中對各錢包餘額進行修改，最後批量寫回（`batchUpWallets`）。
在高並發場景下（如 `flatMap(..., 10)` 同時跑 10 個批次），兩個批次可能讀取到同一個錢包的相同快照，各自計算後批量覆蓋寫回，導致**後寫者覆蓋先寫者的更新，餘額憑空消失**。

**觸發特徵**：
```java
// 特徵 1：批量讀錢包進 Map（無 FOR UPDATE）
walletService.batchFindWallets(walletKeys)
    .forEach(wallet -> walletMap.put(key, wallet));  // ← 記憶體快照

// 特徵 2：在記憶體 Map 中修改餘額
wallet.setBalance(wallet.getBalance().add(profit));  // ← 基於快照計算

// 特徵 3：批量寫回（覆蓋型更新，無版本號）
walletService.batchUpWallets(new ArrayList<>(walletMap.values()));
// ← 若兩個批次持有同一錢包快照，後者覆蓋前者

// 特徵 4：上游有高並發設定
.flatMap(batch -> batchSettleOrders(...), 10)  // ← 並發度 10
```

**危害等級**：P0 — 錢包餘額直接丟失，且不易被即時發現（需對帳才能察覺）

**修復策略**：選擇其一

```java
// 方案 A：悲觀鎖（SELECT FOR UPDATE）
// SQL: SELECT * FROM wallet_tbl
//      WHERE (account_id, coin_id) IN (...)
//      ORDER BY account_id, coin_id   ← 固定順序防死鎖
//      FOR UPDATE
walletService.batchFindWalletsForUpdate(walletKeys)  // ← 加鎖版本
    .forEach(wallet -> walletMap.put(key, wallet));

// 方案 B：樂觀鎖（version 欄位）+ 搭配現有 retryIds 重試
// SQL: UPDATE wallet_tbl SET balance=?, version=version+1
//      WHERE id=? AND version=?
int updated = walletMapper.updateWithVersion(wallet);
if (updated == 0) {
    retryIds.add(AccountCoinKey.of(wallet.getAccountId(), wallet.getCoinId()));
}
```

**反哺規則**：RULE-CON-004

**來源事件**：SettlementFlow.java 掃描 BUG-EXAMPLE-102
**新增日期**：2024-01
**新增人員**：Knowledge Writer Agent

---

## PAT-BIZ-003：外部行情 API 失敗靜默返回預設值

**描述**：
呼叫外部行情 API 取得開盤/收盤價時，若 API 回傳錯誤狀態碼，直接靜默返回 `BigDecimal.ZERO` 作為預設值繼續執行結算流程。
當開盤價與收盤價皆為 ZERO 時，比較結果為「平局（result=0）」，導致**所有相關訂單以錯誤結果結算**，且不產生任何錯誤日誌，極難被發現。

**觸發特徵**：
```java
// 特徵：API 失敗時靜默返回 ZERO，不拋出例外
private Mono<QuoteVo> fetchQuote(String code, long ts) {
    return Mono.fromCallable(() -> {
        ResponseResult resp = priceApi.getOpenPrice(code, ts);
        if (resp.getCode() != 1) {
            return new QuoteVo(code, BigDecimal.ZERO); // ← 靜默吞錯
        }
        return objectMapper.convertValue(resp.getData(), QuoteVo.class);
    });
}

// 後續直接使用返回值計算結算方向
int i = runner.getClosePrice().compareTo(runner.getOpenPrice()); // 0 vs 0
int result = (i == 0 ? 0 : ...);  // ← 錯誤平局
```

**危害等級**：P0 — 整期所有訂單以錯誤方向結算，資損與實際行情完全脫鉤

**修復策略**：API 失敗必須拋出例外，禁止靜默返回預設值

```java
private Mono<QuoteVo> fetchQuote(String code, long ts) {
    return Mono.fromCallable(() -> {
        ResponseResult resp = priceApi.getOpenPrice(code, ts);

        // ✅ API 失敗：拋出例外，讓上層決定重試或暫停結算
        if (resp.getCode() != 1) {
            throw new PriceApiException(
                String.format("行情 API 失敗 code=%s ts=%d resp=%s", code, ts, resp));
        }

        QuoteVo vo = objectMapper.convertValue(resp.getData(), QuoteVo.class);

        // ✅ 額外校驗：價格不能為零或負數
        if (vo.getOpen() == null || vo.getOpen().compareTo(BigDecimal.ZERO) <= 0) {
            throw new PriceApiException(
                String.format("行情價格異常（≤0）code=%s ts=%d price=%s", code, ts, vo.getOpen()));
        }

        return vo;
    }).subscribeOn(Schedulers.boundedElastic());
}
```

**推廣原則**：凡是結算流程依賴的外部 API（行情、匯率、手續費率），失敗必須拋出例外，讓結算流程進入重試或人工介入，不允許以任何預設值代替真實數據繼續執行。

**反哺規則**：RULE-BIZ-002

**來源事件**：SettlementFlow.java 掃描 BUG-EXAMPLE-103
**新增日期**：2024-01
**新增人員**：Knowledge Writer Agent

---

## PAT-CON-005：Retry 場景下狀態標記使用非冪等切換設計

**描述**：
在有重試機制（如 `Retry.backoff(3, ...)`）的響應式流程中，失敗時呼叫 `changeType()` 等**切換型**（toggle）狀態方法。
每次重試失敗都會再次呼叫，導致狀態在每次重試間不斷翻轉，最終狀態取決於失敗次數的奇偶性，**不可預測且難以除錯**。

**觸發特徵**：
```java
// 特徵：切換型方法 + 重試機制共存
} catch (Exception e) {
    countDto.changeType();       // ← 切換：失敗第1次 → 狀態A
    throw new RuntimeException(e);
}
.retryWhen(Retry.backoff(3, Duration.ofSeconds(1)))
// 第2次失敗 → changeType() → 狀態B（翻回去）
// 第3次失敗 → changeType() → 狀態A（又翻）
// 最終狀態：取決於重試次數，不可預測
```

**危害等級**：P1 — 結算狀態標記錯誤，可能導致本應標記失敗的 Runner 被標記為成功

**修復策略**：切換型改為單向冪等標記

```java
// ✅ 方案 A：用單向設定取代切換
} catch (Exception e) {
    log.error("批次交易失敗，runnerId={}", runner.getId(), e);
    countDto.markError();   // ← 只設定為 error，不做 toggle
    throw new RuntimeException(e);
}

// CountDto 的 markError 實作
public void markError() {
    this.resultType.set(1); // 冪等：呼叫幾次都是同一個結果
}

// ✅ 方案 B：onErrorResume 集中處理，catch 區塊不改狀態
.retryWhen(Retry.backoff(3, Duration.ofSeconds(1)))
.onErrorResume(ex -> {
    log.error("重試3次後仍失敗，runnerId={}", runner.getId(), ex); // ← 補上 ex
    countDto.getResultType().set(1);  // 只在最終失敗時設定一次
    return Mono.empty();
})
```

**推廣原則**：在任何有重試機制的流程中，失敗時修改的狀態必須是**冪等的**（無論呼叫幾次，結果相同）。切換型（toggle）的狀態修改只適用於無重試的單次執行流程。

**反哺規則**：RULE-CON-005

**來源事件**：SettlementFlow.java 掃描 BUG-EXAMPLE-104
**新增日期**：2024-01
**新增人員**：Knowledge Writer Agent

---

## PAT-FIN-005：多資產精度硬編碼 scale

**描述**：
不同資產的小數精度不同（BTC 8 位、USDT 6 位、JPY 0 位、TWD 0 位）。程式中硬編碼 `setScale(8, ...)` 對所有資產一視同仁，導致：對 JPY 產生不存在的小數、對需要 8 位的幣別被截斷、跨幣別比較與加總出錯。settlement-checklist A 類「統一 scale 8 位」本身在多資產系統就是個錯誤假設。

**觸發特徵**：
```java
// 特徵：scale 寫死，未依資產定義
BigDecimal profit = amount.multiply(rate).setScale(8, RoundingMode.HALF_DOWN); // ← 所有幣別都 8
if (jpyAmount.scale() == 8) { ... } // ← JPY 不該有小數
```

**危害等級**：P0 — 跨幣別精度錯誤，累積資損且難對帳

**修復策略**：scale 由資產中繼資料決定
```java
int scale = assetMeta.getScale(coinId);            // 由資產定義取得
BigDecimal profit = amount.multiply(rate).setScale(scale, assetMeta.getRounding(coinId));
// 入庫前校驗：金額 scale 不得超過資產定義
if (amount.stripTrailingZeros().scale() > scale)
    throw new ValidationException("金額精度超出資產 " + coinId + " 定義");
```

**反哺規則**：RULE-FIN-006（對應不變量 INV-TXN-02）

---

## PAT-FIN-006：分配/拆分捨入殘差未處理（salami slicing）

**描述**：
把一筆總額分配給多方（分潤、拆單、按比例退款）時，各方 `總額 × 比例` 個別捨入後，加總**不等於**原總額，產生殘差（少了/多了 1 個最小單位）。殘差若無明確歸屬，長期累積即「salami slicing」吞錢或造錢，且違反守恆。

**觸發特徵**：
```java
// 特徵：逐項捨入後未校驗總和 = 原總額
for (Party p : parties) {
    BigDecimal share = total.multiply(p.getRatio())
        .setScale(scale, RoundingMode.HALF_UP);    // ← 各自捨入
    credit(p, share);                              // Σshare 可能 ≠ total
}
```

**危害等級**：P0 — 累積資損/造錢，違反 INV-TXN-05 與 INV-ST-03

**修復策略**：最大餘額法 / 殘差歸位（last-takes-remainder）
```java
BigDecimal allocated = ZERO;
for (int i = 0; i < parties.size(); i++) {
    BigDecimal share = (i == parties.size() - 1)
        ? total.subtract(allocated)                       // 最後一方吃殘差，保證守恆
        : total.multiply(parties.get(i).getRatio()).setScale(scale, HALF_DOWN);
    allocated = allocated.add(share);
    credit(parties.get(i), share);
}
assert allocated.compareTo(total) == 0;                   // INV-TXN-05
```

**推廣原則**：任何「一拆多」或「多合一」的金額運算，運算後必須斷言總和守恆，殘差需有明確且一致的歸屬規則。

**反哺規則**：RULE-FIN-007

---

## PAT-FIN-007：時間戳單位混淆（ms/s）與時區邊界

**描述**：
結算依賴時間戳判定開盤/收盤、T+1、利息計息日。秒（10 位）與毫秒（13 位）混用，或用系統預設時區處理跨日邊界，導致取錯價格區間、結算日歸屬錯誤、DST 當天計息錯誤。PAT-BIZ-003 的 `fetchQuote(code, ts)` 即潛在風險點。

**觸發特徵**：
```java
// 特徵 1：ms/s 混用
long ts = System.currentTimeMillis();          // 13 位 ms
priceApi.getOpenPrice(code, ts);               // ← API 預期秒？單位未明確
new Date(epochSeconds);                         // ← 把秒當毫秒

// 特徵 2：用預設時區算結算日
LocalDate settleDate = LocalDate.now();        // ← 依伺服器時區，跨日邊界錯
```

**危害等級**：P1 — 取錯價格區間 / 結算日歸屬錯誤，定向可被利用

**修復策略**：單位顯式化 + 固定結算時區
```java
Instant ts = Instant.now();                                  // 型別即語意，避免裸 long
long epochMillis = ts.toEpochMilli();
// 結算日固定以交易所/業務時區計算
LocalDate settleDate = ts.atZone(EXCHANGE_ZONE).toLocalDate();
```

**反哺規則**：RULE-FIN-008

---

## PAT-FIN-008：金額以最小單位存 long 的整數溢位

**描述**：
為效能改用 `long`（聰）儲存金額。大額聚合（總資產、平台總額、批次加總）可能超過 `Long.MAX_VALUE`，或乘法中間值溢位，靜默回繞成負/錯值。

**觸發特徵**：
```java
// 特徵：long 金額直接相乘/累加，無溢位防護
long total = 0;
for (long amt : amounts) total += amt;          // ← 大量累加可能溢位
long fee = amount * rateBps / 10000;            // ← amount * rateBps 中間值溢位
```

**危害等級**：P1 — 大額/聚合場景金額回繞，極端但破壞性高

**修復策略**：聚合與乘法用 `BigInteger`/`Math.*Exact`，或全程 BigDecimal
```java
long fee = Math.multiplyExact(amount, rateBps) / 10000;   // 溢位即拋例外
// 聚合用 BigInteger 或 BigDecimal
BigInteger total = amounts.stream().map(BigInteger::valueOf)
    .reduce(BigInteger.ZERO, BigInteger::add);
```

**反哺規則**：RULE-FIN-009

---

## 新增模式（模板）

複製以下模板，在檔案末尾新增新的模式：

```markdown
## PAT-{類別}-{序號}：{模式名稱}

**描述**：
{說明這個 Bug 模式的業務背景與危害}

**觸發特徵**：
\`\`\`java
// 描述可識別的程式碼特徵
\`\`\`

**修復策略**：{策略編號} → {策略名稱}

\`\`\`java
// 修復後的正確寫法
\`\`\`

**反哺規則**：{RULE-XXX-NNN}（新增到 rules-registry.md）

**來源事件**：{BUG-YYYY-NNN} / {事後檢視報告連結}
**新增日期**：{YYYY-MM-DD}
**新增人員**：{AI Agent / 工程師姓名}
```
