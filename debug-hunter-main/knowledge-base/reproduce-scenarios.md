---
file_id: reproduce-scenarios
kind: reference
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 180
owner: reproducer-agent
external_refs: []
---

# 復現情境沉澱庫

> 檔案路徑：knowledge-base/reproduce-scenarios.md
> 用途：儲存已驗證的最小復現情境（MRS），供後續同類 Bug 直接複用
> 更新時機：每次 Stage 5 RECYCLE 後，由 knowledge-writer.md 自動追加
> 版本：v1.0（初始版，來自 SettlementFlow.java 掃描）

---

## 情境索引

| 代碼 | Bug 標題 | 類別 | 復現狀態 | 觸發機率 | 來源 |
|------|---------|------|---------|---------|------|
| SCENE-CON-001 | Kafka 重送批次導致部分訂單雙重結算 | 整合測試 | Confirmed | 100%（重送時） | SettlementFlow.java BUG-EXAMPLE-101 |
| SCENE-CON-002 | 並發批次更新錢包餘額丟失 | 並發測試 | Confirmed | ~80%（並發度≥5時） | SettlementFlow.java BUG-EXAMPLE-102 |
| SCENE-BIZ-001 | 行情 API 失敗靜默返回 ZERO 導致平局誤判 | 單元測試 | Confirmed | 100%（API失敗時） | SettlementFlow.java BUG-EXAMPLE-103 |
| SCENE-CON-003 | Retry 場景 changeType() 狀態奇偶污染 | 單元測試 | Confirmed | 100%（重試次數為偶數時） | SettlementFlow.java BUG-EXAMPLE-104 |

---

## SCENE-CON-001：Kafka 重送批次導致部分訂單雙重結算

**對應 Bug 模式**：PAT-CON-001 變體 B
**對應靜態規則**：RULE-CON-006

### 前置條件

| 條件 | 值 |
|------|-----|
| Kafka 消費模式 | 批次（batch） |
| 批次大小 | 3 筆 Runner |
| 第 2 筆 Runner | 刻意注入例外，觸發 hasError=true |
| 冪等保護 | 無（Bug 狀態） |

### 觸發步驟

```
1. Kafka 批次投遞 [Runner-A, Runner-B, Runner-C]
2. Runner-A 結算成功 → 錢包入帳 ✅
3. Runner-B 結算拋出例外 → hasError = true
4. Runner-C 結算成功 → 錢包入帳 ✅
5. hasError=true → 整批不 ACK
6. Kafka 重送整批 [Runner-A, Runner-B, Runner-C]
7. Runner-A 再次結算 → 錢包再次入帳 ← 雙重入帳！
8. Runner-C 再次結算 → 錢包再次入帳 ← 雙重入帳！
```

### 錯誤結果

```
Runner-A 帳戶餘額：應 +100，實際 +200（入帳兩次）
Runner-C 帳戶餘額：應 +80，實際 +160（入帳兩次）
Runner-B 帳戶餘額：正確（從未成功結算）
```

### 復現測試

```java
@SpringBootTest
@Testcontainers
class SceneConReproduceTest {

    @Test
    @DisplayName("SCENE-CON-001：Kafka 重送時無冪等保護導致雙重入帳")
    void scene_con_001_kafka_resend_double_settlement() throws Exception {
        // 建立 3 筆 Runner，中間那筆會失敗
        String runnerA = buildRunnerJson(1L, "normal");
        String runnerB = buildRunnerJson(2L, "will-fail"); // 注入失敗標記
        String runnerC = buildRunnerJson(3L, "normal");

        BigDecimal balanceA_before = getBalance("account-A");
        BigDecimal balanceC_before = getBalance("account-C");

        // 第一次批次（含失敗）
        kafkaTemplate.send(SETTLEMENT_CLOSE, runnerA).get();
        kafkaTemplate.send(SETTLEMENT_CLOSE, runnerB).get();
        kafkaTemplate.send(SETTLEMENT_CLOSE, runnerC).get();
        Thread.sleep(3000);

        // 模擬 Kafka 重送（再次發送相同訊息）
        kafkaTemplate.send(SETTLEMENT_CLOSE, runnerA).get();
        kafkaTemplate.send(SETTLEMENT_CLOSE, runnerC).get();
        Thread.sleep(3000);

        BigDecimal balanceA_after = getBalance("account-A");
        BigDecimal balanceC_after = getBalance("account-C");

        // 驗證雙重入帳
        BigDecimal profitA = balanceA_after.subtract(balanceA_before);
        BigDecimal profitC = balanceC_after.subtract(balanceC_before);

        assertThat(profitA).isGreaterThan(EXPECTED_PROFIT_A.multiply(new BigDecimal("1.5")));
        assertThat(profitC).isGreaterThan(EXPECTED_PROFIT_C.multiply(new BigDecimal("1.5")));

        log.info("SCENE-CON-001 復現成功：A帳戶多入帳 {}，C帳戶多入帳 {}", profitA, profitC);
    }
}
```

**測試檔案路徑**：`src/test/java/com/example/reproduce/SceneConReproduceTest.java`

---

## SCENE-CON-002：並發批次更新錢包餘額丟失

**對應 Bug 模式**：PAT-CON-004
**對應靜態規則**：RULE-CON-004

### 前置條件

| 條件 | 值 |
|------|-----|
| 初始錢包餘額 | 1000 |
| 並發批次數 | 2 個批次同時讀取同一錢包 |
| Batch-1 入帳 | +500 |
| Batch-2 入帳 | +300 |
| DB 鎖定 | 無（Bug 狀態） |

### 觸發步驟

```
時序：
T1: Batch-1 讀取 wallet → balance=1000（快照）
T1: Batch-2 讀取 wallet → balance=1000（同一快照）
T2: Batch-1 計算 1000+500=1500，寫回 DB
T3: Batch-2 計算 1000+300=1300，寫回 DB  ← 覆蓋 Batch-1！
最終：balance=1300，正確應為 1800，損失 500
```

### 復現關鍵：CountDownLatch 控制時序

```java
@Test
@DisplayName("SCENE-CON-002：並發批次讀取同一錢包快照，後寫覆蓋前寫導致餘額丟失")
void scene_con_002_concurrent_wallet_update_lost() throws Exception {
    walletRepo.save(Wallet.of("account-X", new BigDecimal("1000")));
    CountDownLatch bothRead = new CountDownLatch(2);
    CountDownLatch startWrite = new CountDownLatch(1);

    Thread batchOne = new Thread(() -> {
        Wallet w = walletRepo.findById("account-X");       // 讀到 1000
        bothRead.countDown();
        awaitQuietly(startWrite);                          // 等 Batch-2 也讀完
        w.setBalance(w.getBalance().add(new BigDecimal("500")));
        walletRepo.save(w);                                // 寫 1500
    });

    Thread batchTwo = new Thread(() -> {
        Wallet w = walletRepo.findById("account-X");       // 也讀到 1000（同快照）
        bothRead.countDown();
        awaitQuietly(startWrite);
        w.setBalance(w.getBalance().add(new BigDecimal("300")));
        walletRepo.save(w);                                // 寫 1300，覆蓋 1500！
    });

    batchOne.start(); batchTwo.start();
    bothRead.await();       // 兩個都讀完
    startWrite.countDown(); // 同時開始寫
    batchOne.join(); batchTwo.join();

    BigDecimal actual = walletRepo.findById("account-X").getBalance();
    assertThat(actual).isNotEqualByComparingTo(new BigDecimal("1800"));
    log.info("SCENE-CON-002 復現：正確餘額 1800，實際餘額 {}，丟失 {}",
        actual, new BigDecimal("1800").subtract(actual));
}
```

**觸發機率**：並發度 5 以上約 80%，並發度 10 接近 100%

**測試檔案路徑**：`src/test/java/com/example/reproduce/SceneConReproduceTest.java`

---

## SCENE-BIZ-001：行情 API 失敗靜默返回 ZERO 導致平局誤判

**對應 Bug 模式**：PAT-BIZ-003
**對應靜態規則**：RULE-BIZ-002

### 前置條件

| 條件 | 值 |
|------|-----|
| 行情 API | Mock 返回失敗（code != 1） |
| 真實開盤價 | 應為 100（SYM-A） |
| 真實收盤價 | 應為 110（上漲，方向 A 勝） |

### 觸發步驟

```
1. 行情 API 回傳 code=500（服務異常）
2. fetchQuote() 靜默返回 QuoteVo(code, BigDecimal.ZERO)
3. runner.openPrice = 0, runner.closePrice = 0
4. 比較結果：0.compareTo(0) = 0 → result = 0（平局）
5. 所有方向 A 訂單應獲勝，但被判為平局
```

### 錯誤結果

```
預期：方向 A 獲勝（result=1），方向 A 入帳收益
實際：判為平局（result=0），依業務邏輯退款或無收益
影響：整期所有訂單以錯誤結果結算
```

### 復現測試

```java
@Test
@DisplayName("SCENE-BIZ-001：行情 API 失敗靜默返回 ZERO，整期被誤判為平局")
void scene_biz_001_quote_api_failure_causes_wrong_result() {
    when(priceApi.getOpenPrice(anyString(), anyLong()))
        .thenReturn(ResponseResult.fail("Internal Server Error"));

    Runner runner = Runner.builder()
        .instrumentCode("SYM-A")
        .marketId(1L).id(100L).build();

    // fetchQuote 靜默吞錯，返回 ZERO
    settlementService.fetchRoundPriceData(runner).block();

    assertThat(runner.getOpenPrice()).isEqualByComparingTo(BigDecimal.ZERO);
    assertThat(runner.getClosePrice()).isEqualByComparingTo(BigDecimal.ZERO);

    // 結算方向被錯誤判為平局
    int result = runner.getClosePrice().compareTo(runner.getOpenPrice()) == 0 ? 0 : 1;
    assertThat(result).isEqualTo(0);
    log.info("SCENE-BIZ-001 復現：API 失敗被靜默吞錯，錯誤判定為平局 result={}", result);
}
```

**測試檔案路徑**：`src/test/java/com/example/reproduce/SceneBizReproduceTest.java`

---

## SCENE-CON-003：Retry 場景 changeType() 狀態奇偶污染

**對應 Bug 模式**：PAT-CON-005
**對應靜態規則**：RULE-CON-005

### 前置條件

| 條件 | 值 |
|------|-----|
| 重試次數 | 3（backoff(3, ...)） |
| changeType() 語意 | 切換（toggle），非單向設定 |

### 觸發步驟

```
初始 resultType = 0（正常）
第 1 次失敗 → changeType() → resultType = 1（錯誤）
第 2 次失敗 → changeType() → resultType = 0（翻回！）
第 3 次失敗 → changeType() → resultType = 1（錯誤）
最終：3 次重試後剛好是奇數次，resultType=1（正確）
但若重試 2 次：resultType=0（誤判為正常！）
```

### 錯誤結果

```
重試 2 次（偶數）：resultType=0（Bug：誤判為成功）
重試 3 次（奇數）：resultType=1（恰好正確，但依賴奇偶）
行為完全不可預測，取決於失敗次數
```

### 復現測試

```java
@ParameterizedTest
@ValueSource(ints = {1, 2, 3, 4})
@DisplayName("SCENE-CON-003：changeType() 在不同重試次數下狀態不可預測")
void scene_con_003_changeType_unpredictable_under_retry(int retryCount) {
    CountDto countDto = CountDto.builder()
        .resultType(new AtomicReference<>(0)).build();

    IntStream.range(0, retryCount).forEach(_ -> countDto.changeType());

    int finalState = countDto.getResultType().get();
    int expected = 1; // 失敗就應該是 1，永遠

    if (retryCount % 2 == 0) {
        // 偶數次重試：狀態回到 0，Bug！誤判為正常
        assertThat(finalState).isEqualTo(0);
        log.warn("Bug 復現：重試 {} 次（偶數），resultType 回到 0，誤判為正常！", retryCount);
    } else {
        // 奇數次：剛好正確，但只是巧合
        assertThat(finalState).isEqualTo(1);
        log.info("重試 {} 次（奇數），結果剛好正確，但依賴奇偶非設計保證", retryCount);
    }
}
```

**測試檔案路徑**：`src/test/java/com/example/reproduce/SceneConReproduceTest.java`

---

## 新增情境（模板）

```markdown
## SCENE-{類別}-{序號}：{Bug 標題}

**對應 Bug 模式**：PAT-XXX-NNN
**對應靜態規則**：RULE-XXX-NNN

### 前置條件
| 條件 | 值 | 說明 |
|------|-----|------|

### 觸發步驟
```
1.
2.
3.
```

### 錯誤結果
```
預期：
實際：
```

### 復現測試
\`\`\`java
// 測試程式碼
\`\`\`

**觸發機率**：{100% / ~X%}
**測試檔案路徑**：src/test/java/com/example/reproduce/{ClassName}.java
**新增日期**：{YYYY-MM-DD}
**新增人員**：{Knowledge Writer Agent / 工程師}
```
