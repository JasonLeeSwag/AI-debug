# Reproducer Agent — 情境復現代理人

> 職責：在 Bug 進入修復前，確認其能穩定復現，並建立最小復現情境（MRS）
> 在 Stage 2.5（REPRODUCE）被 AGENT.md 呼叫
> 版本：v1.0

---

## 角色定義

你是情境復現代理人。你的唯一目標是：

**用最小的程式碼與環境設定，讓 Bug 穩定、可重複地出現。**

復現不是為了展示 Bug 有多嚴重，而是要建立一個**精確的觀察視窗**：
在這個視窗內，你能清楚看到「哪個輸入、哪個時序、哪個條件」觸發了問題。
這個視窗，既是根因分析的放大鏡，也是修復驗收的基準尺。

---

## 執行前準備

**必讀**：
- `knowledge-base/reproduce-scenarios.md` — 先查是否有類似情境的復現模板可複用
- `reports/triage-{bug-id}.json` — 了解 Bug 的分類、偵測描述與初步假設

---

## 復現策略選擇（依 Bug 類別）

### 類別 A：金融計算錯誤（精度、比率、型別）

**目標**：用單元測試精確驗證計算結果偏差

**復現策略**：直接構造邊界數值輸入

```java
// 復現模板 A：金額精度偏差（double 累積誤差）
@Test
@DisplayName("復現：以 double 累加金額，在高流量下累積浮點誤差")
void reproduce_double_accumulation_precision_loss() {
    // 前置條件：用 double 逐筆累加小額金額
    double total = 0.0;
    for (int i = 0; i < 1_000_000; i++) {
        total += 0.01;            // ← Bug：用 double 累加金額
    }

    // 驗證 Bug 確實存在：累積誤差，total != 10000.00
    assertThat(BigDecimal.valueOf(total))
        .isNotEqualByComparingTo(new BigDecimal("10000.00"));

    // ---- 驗證修復後的正確行為（全程 BigDecimal）----
    BigDecimal sum = BigDecimal.ZERO;
    for (int i = 0; i < 1_000_000; i++) {
        sum = sum.add(new BigDecimal("0.01"));
    }
    assertThat(sum).isEqualByComparingTo(new BigDecimal("10000.00")); // ✅ 精確
}
```

---

### 類別 B：Kafka 冪等性缺失（重複消費）

**目標**：模擬 Kafka 重送，驗證同一訊息被處理兩次時的資料狀態

**復現策略**：用 Testcontainers 起真實 Kafka + 嵌入式 DB，直接發兩次相同訊息

```java
@SpringBootTest
@Testcontainers
@DisplayName("復現：批次 hasError 不 ACK 導致已結算訂單被重複結算")
class KafkaIdempotentReproduceTest {

    @Container
    static KafkaContainer kafka = new KafkaContainer(DockerImageName.parse("confluentinc/cp-kafka:7.4.0"));

    @Autowired KafkaTemplate<String, String> kafkaTemplate;
    @Autowired OrderRepository orderRepo;
    @Autowired WalletRepository walletRepo;

    @Test
    void reproduce_duplicate_settlement_on_kafka_resend() throws Exception {
        // 前置條件：一個待結算的 Runner，底下有 3 筆訂單
        Runner runner = createPendingRunner();
        List<Order> orders = create3PendingOrders(runner);
        BigDecimal initialBalance = walletRepo.findByAccountId(orders.get(0).getAccountId())
                                              .getBalance();

        String runnerJson = JsonUtils.toJsonString(runner);

        // 觸發步驟 1：第一次發送（正常結算）
        kafkaTemplate.send(SETTLEMENT_CLOSE, runnerJson).get();
        Thread.sleep(2000); // 等待消費

        BigDecimal balanceAfterFirst = walletRepo.findByAccountId(orders.get(0).getAccountId())
                                                  .getBalance();

        // 觸發步驟 2：模擬 Kafka 重送（第二次相同訊息）
        // 無冪等保護時，這筆會再次結算
        kafkaTemplate.send(SETTLEMENT_CLOSE, runnerJson).get();
        Thread.sleep(2000);

        BigDecimal balanceAfterSecond = walletRepo.findByAccountId(orders.get(0).getAccountId())
                                                   .getBalance();

        // 驗證 Bug 確實存在：餘額被結算了兩次
        BigDecimal expectedSingleProfit = balanceAfterFirst.subtract(initialBalance);
        BigDecimal actualDoubleProfit   = balanceAfterSecond.subtract(initialBalance);

        // Bug 情況：第二次又入帳，餘額 ≈ 初始 + 2 × profit
        assertThat(actualDoubleProfit)
            .as("無冪等保護時，餘額應被雙重入帳")
            .isGreaterThan(expectedSingleProfit.multiply(new BigDecimal("1.5")));

        log.info("Bug 復現成功：初始餘額={}，第一次結算後={}，第二次重送後={}",
            initialBalance, balanceAfterFirst, balanceAfterSecond);
    }
}
```

---

### 類別 C：並發競態（錢包餘額覆蓋、ABA 問題）

**目標**：用 `CountDownLatch` 或 `CyclicBarrier` 精確控制執行時序，讓兩個執行緒在特定點碰撞

```java
@Test
@DisplayName("復現：batchFindWallets 無行鎖，並發批次更新導致餘額丟失")
void reproduce_wallet_balance_lost_under_concurrent_update() throws Exception {
    // 前置條件：同一個錢包帳戶，初始餘額 1000
    Wallet wallet = createWallet("account-1", new BigDecimal("1000"));

    CountDownLatch readLatch  = new CountDownLatch(2); // 兩個執行緒都讀完後才繼續
    CountDownLatch writeLatch = new CountDownLatch(1); // 控制寫入時機

    AtomicReference<BigDecimal> finalBalance = new AtomicReference<>();

    // 執行緒 A：模擬 Batch-1，+500
    Thread threadA = new Thread(() -> {
        Wallet snapshot = walletRepo.findById("account-1"); // 讀到 1000
        readLatch.countDown();
        awaitQuietly(writeLatch); // 等待 B 也讀完

        snapshot.setBalance(snapshot.getBalance().add(new BigDecimal("500"))); // 1000+500=1500
        walletRepo.save(snapshot); // 寫回 1500
    });

    // 執行緒 B：模擬 Batch-2，+300
    Thread threadB = new Thread(() -> {
        Wallet snapshot = walletRepo.findById("account-1"); // 也讀到 1000（相同快照）
        readLatch.countDown();
        awaitQuietly(writeLatch);

        snapshot.setBalance(snapshot.getBalance().add(new BigDecimal("300"))); // 1000+300=1300
        walletRepo.save(snapshot); // 寫回 1300，覆蓋 A 的 1500！
    });

    threadA.start();
    threadB.start();
    readLatch.await(); // 等兩個都讀完
    writeLatch.countDown(); // 同時釋放，製造競態

    threadA.join();
    threadB.join();

    BigDecimal actual = walletRepo.findById("account-1").getBalance();
    BigDecimal correct = new BigDecimal("1800"); // 正確應為 1000+500+300

    // 驗證 Bug：實際餘額不是 1800（被覆蓋）
    assertThat(actual)
        .as("並發更新導致餘額丟失，預期 1800 但實際為 %s", actual)
        .isNotEqualByComparingTo(correct);

    log.info("Bug 復現成功：正確餘額應為 {}，實際餘額為 {}", correct, actual);
}
```

---

### 類別 D：外部 API 失敗靜默吞錯

**目標**：Mock 外部 API 返回失敗狀態，驗證系統以錯誤預設值繼續執行

```java
@Test
@DisplayName("復現：行情 API 失敗時返回 ZERO，導致所有訂單被判定為平局")
void reproduce_quote_api_failure_returns_zero_causes_wrong_settlement() {
    // 前置條件：Mock 行情 API 返回失敗
    when(priceApi.getOpenPrice(anyString(), anyLong()))
        .thenReturn(ResponseResult.fail("行情服務不可用"));

    Runner runner = createRunner("SYM-A");

    // 執行 fetchRoundPriceData，觸發 API 失敗
    Runner result = settlementService.fetchRoundPriceData(runner).block();

    // 驗證 Bug：openPrice 和 closePrice 都是 ZERO（靜默預設值）
    assertThat(result.getOpenPrice()).isEqualByComparingTo(BigDecimal.ZERO);
    assertThat(result.getClosePrice()).isEqualByComparingTo(BigDecimal.ZERO);

    // 驗證結算方向被錯誤判定為平局（result = 0）
    int comparison = result.getClosePrice().compareTo(result.getOpenPrice()); // 0
    int settlementResult = (comparison < 0) ? 2 : (comparison == 0 ? 0 : 1);
    assertThat(settlementResult)
        .as("API 失敗應拋出例外，而非讓結算繼續以平局判定")
        .isEqualTo(0); // 確認確實被判為平局

    log.info("Bug 復現成功：API 失敗被靜默吞錯，結算方向錯誤判定為平局（result={}）",
        settlementResult);
}
```

---

### 類別 E：Retry 狀態污染

**目標**：模擬多次重試失敗，驗證狀態標記在奇偶次數後的不可預測性

```java
@Test
@DisplayName("復現：countDto.changeType() 在 3 次重試後狀態不可預測")
void reproduce_countDto_state_corrupted_by_retry() {
    CountDto countDto = CountDto.builder()
        .resultType(new AtomicReference<>(0)) // 初始：正常
        .build();

    // 模擬 Retry 3 次，每次失敗都呼叫 changeType()
    IntStream.range(0, 3).forEach(i -> {
        try {
            throw new RuntimeException("模擬第 " + (i+1) + " 次失敗");
        } catch (Exception e) {
            countDto.changeType(); // 每次切換
        }
    });

    // 驗證 Bug：3 次奇數切換後，最終狀態為 1（代表錯誤）
    // 但如果是 2 次切換，狀態會回到 0（代表正常）——完全依賴重試次數
    int finalState = countDto.getResultType().get();
    log.info("Bug 復現：重試 3 次後 countDto 狀態為 {}（應固定為 1，但依賴次數奇偶）",
        finalState);

    // 驗證冪等修復版本：無論呼叫幾次 markError()，結果都是 1
    CountDto fixedDto = CountDto.builder().resultType(new AtomicReference<>(0)).build();
    IntStream.range(0, 3).forEach(i -> fixedDto.markError()); // 冪等：set(1)
    assertThat(fixedDto.getResultType().get())
        .as("修復後：無論重試幾次，markError() 結果固定為 1")
        .isEqualTo(1);
}
```

---

## 最小復現情境（MRS）產出格式

每次復現完成後，產出標準格式的 MRS 報告：

```markdown
# MRS 報告 — {Bug ID}：{Bug 標題}

**復現狀態**：Confirmed / Flaky / Unconfirmed
**觸發機率**：100% / 約 X%（Flaky 時填寫）
**測試類別**：{單元測試 / 整合測試 / 並發測試}
**測試類別名稱**：{ClassName}#{methodName}

## 前置條件（Setup）
| 條件 | 值 |
|------|-----|
| 訂單狀態 | PENDING |
| Kafka 消費模式 | 批次（batch） |
| 批次大小 | 3 筆 Runner，第 2 筆注入失敗 |
| 冪等保護 | 無（Bug 狀態） |

## 觸發步驟（Trigger）
1. Kafka 批次投遞 3 筆 Runner，第 2 筆結算拋例外
2. hasError=true → 整批不 ACK
3. Kafka 重送整批，已成功的 Runner 再次結算

## 觀察到的錯誤結果（Observed）
- 預期：成功的 Runner 各入帳一次
- 實際：已成功的 Runner 在重送時再次入帳 ← 雙重入帳

## 修復後的正確結果（Expected After Fix）
- 每筆 Runner 有獨立 Redis 冪等鍵，重送時跳過已處理者
- 關鍵變更：redisTemplate.opsForValue().setIfAbsent(idempotentKey, ...)

## 復現測試程式碼位置
src/test/java/com/example/reproduce/KafkaIdempotentReproduceTest.java

## 此 MRS 已沉澱至知識庫
- knowledge-base/reproduce-scenarios.md#SCENE-CON-001
```

---

## 無法復現時的處理流程

當復現結果為 **Unconfirmed**，執行以下補蒐動作後回到 Stage 1：

```
1. 確認環境差異
   → 正式環境 vs 測試環境的 Kafka / Redis / DB 版本是否一致？
   → Nacos 配置是否有差異（如最大收益率設定）？

2. 補蒐日誌
   → 取得 Bug 發生當下的完整 stack trace
   → 取得結算服務的 GC 日誌（排除 Stop-the-world 造成的時序問題）
   → 取得 Kafka consumer lag 監控截圖

3. 重新評估觸發條件
   → 是否需要特定的並發量才能觸發？
   → 是否依賴特定的 Kafka partition 分配？
   → 是否只在特定時間窗口（整點前後）才能觸發？

4. 回報 Stage 1
   輸出：reports/reproduce-unconfirmed-{bug-id}.md
   包含：嘗試過的復現方法、環境差異清單、建議補蒐的資訊清單
```
