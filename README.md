# Small Business AI Ops

Small Business AI Ops 是一個以客服案件為入口的營運決策與自動化系統。

目前 V2 聚焦在訂單相關客服案件，系統會將案件資料轉換成可追蹤的決策流程，評估案件的嚴重程度、影響程度與緊急程度，計算優先等級，最後透過 Risk Gate 將案件分流至：

- 低風險案件：自動處理
- 高風險或需要人工介入的案件：人工審核

系統同時保存 Decision、Execution Record 與 Human Review Record，讓每次判斷與操作都可以被追蹤、檢查與回溯。

---

## Project Goal

這個專案的目標不是單純製作 CRUD 系統，而是建立一條可被信任的營運 Workflow：

```text
Detect
→ Enrich
→ Assess
→ Decide
→ Risk Gate
→ Act / Human Review
→ Record
→ Surface