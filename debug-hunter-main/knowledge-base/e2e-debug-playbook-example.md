---
file_id: e2e-debug-playbook-example
kind: playbook
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 180
owner: knowledge-writer-agent
external_refs: []
---

# 端到端 Debug 劇本範例：併發提款漏洞 (Race Condition)

> 地位：**實戰演練**。演示 AI 如何協同使用 KB 中的多個檔案來解決一個複雜問題。

---

## 1. 偵測階段 (Detection)
- **觸發器**: 掃描到提款代碼中缺乏分佈式鎖或樂觀鎖。
- **參考 Pattern**: `PAT-SEC-103` (餘額檢查與扣款非原子 / TOCTOU 雙花)；併參 `persistence-consistency-controls.md`。
- **工具輸出**: Semgrep 警告 `check-ownership-before-withdrawal` 雖通過，但 `INV-ST-01` (餘額非負) 在併發下可能失效。

## 2. 診斷與定級 (Diagnosis & Severity)
- **影響分析**: 查詢 `money-flow-map.md`。確認 Sink 是 `walletService.debit` (核心金流)。
- **定級**: 
  - $DirectLoss$: 可能導致用戶餘額變負，損失視用戶規模而定（重大）。
  - $Likelihood$: 併發利用工具成熟（高）。
  - **結論**: `P1 (High)`，見 `severity-loss-model.md`。

## 3. 復現準備 (Reproduction)
- **模板**: 使用 `reproduce-scenarios.md#SCENE-CON-002`（並發批次更新錢包餘額丟失）。
- **PBT 生成**: 根據 `property-test-catalog.md#PBT-FIN-02`（餘額非負）生成併發測試腳本：
  ```java
  @Test
  void testConcurrentWithdraw() {
      // 發送 10 個併發請求，每個金額等於當前餘額
  }
  ```
- **PoC 參考**: 參考 `attack-regression-corpus.md#CORP-003`（競態條件 / 並發提款超提）。

## 4. 修復與驗收 (Fix & Verify)
- **修復建議**: 參考 `financial-security-patterns.md#PAT-SEC-103` 與 `settlement-checklist.md` 第七節編碼基線。引入樂觀鎖 `UPDATE wallet SET balance = balance - :amt, version = version + 1 WHERE id = :id AND version = :oldVersion`。
- **證據標準**: 依據 `finding-evidence-standard.md`，必須提交：
  1. 修復後的單元測試通過。
  2. 併發 100 執行緒下不再出現負餘額（證據 ID: EVID-PBT-SUCCESS）。

---
