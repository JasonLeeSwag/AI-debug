---
file_id: version-compatibility-matrix
kind: reference
status: active
schema_version: 1.0
last_reviewed: 2026-06-01
stale_after_days: 180
owner: knowledge-writer-agent
---

# 版本兼容性矩陣（Version Compatibility Matrix）

> 地位：**系統演進防禦圖**。防範因升級導致的數據結構不匹配、協議降級或舊版本漏洞回潮。

---

## 1. API 協議兼容性
- **規則**: 核心金流 API 禁止破壞性變更（Breaking Changes）。
- **偵測點**: 移除欄位或更改數據類型（如 `long` 轉 `String`）必須有版本標籤 `v2`。

---

## 2. 數據 Schema 遷移
- **風險**: 舊代碼解析新產生的 DB 數據，或新代碼處理舊數據時出現 `NullPointerException`。
- **不變量**: 涉及餘額/狀態的欄位，必須提供默認值或遷移腳本。

---

## 3. 組件版本安全 (Third-party Risks)
- **核心基線**:
  - Java 21+ (虛擬線程併發安全校驗)
  - Spring Boot 3.2+
  - Jackson (防範反序列化漏洞)
- **偵測點**: `pom.xml` 中是否存在已知 CVE 的依賴版本。

---

## 4. 灰度發布下的狀態一致性
- **場景**: A 服務已升級，B 服務仍為舊版。
- **風險**: B 服務不認識 A 服務寫入的新訂單狀態，將其誤判為 `INTERNAL_ERROR` 觸發錯誤退款。
- **對策**: 狀態機定義必須預留 `UNKNOWN_STATE` 的優雅降級邏輯。
