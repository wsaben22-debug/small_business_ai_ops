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


```

---

## Project Evolution

| Version | Focus | Status |
|---|---|---|
| V0 | Django Models、CRUD、Web UI | Completed |
| V1 | REST API、Authentication、Permission | Completed |
| V2 | Rule-Based Triage、Risk Gate、Automation、Human Review | Completed |
| V2.0.1 | Reliability Hardening、Data Consistency、Regression Tests | Completed |
| V3 Lite | AI Assist | Planned |

## V2.0.1 Reliability Hardening

V2.0.1 主要提升既有營運決策 Workflow 的安全性與可靠性，不改變核心業務流程。

### Completed Improvements

- Anonymous API Read：收斂未登入使用者的 API 讀取權限
- Decision Input Consistency：防止已評估案件修改核心決策輸入
- Customer / Order Consistency：確認案件客戶與訂單客戶一致
- Persisted Risk Gate：優先使用已保存的風險分流結果，保留 Legacy Fallback
- Protected Delete：處理 Web 及 REST API 的受保護案件刪除錯誤
- Human Review Validation：拒絕空白的人工審查原因

### Verification

- Django Full Test Suite：67 / 67 PASS
- Django System Check：0 issues
- 採用 Red → Green 及 Regression Testing 驗證核心 Business Rules

### Engineering Principles

- 保留 Decision History 與可追溯的決策依據
- 區分不可修改的評估輸入與允許更新的 Workflow 狀態
- 優先使用 Persisted Decision Results，避免重複推導
- 保留合法操作，避免過度限制既有流程
- 以最小修改維持系統穩定性

## Next Stage

V3 Lite 將在既有 Rule-Based Workflow 的基礎上加入有限度的 AI Assist，並維持 Risk Gate、人工審查及正式業務決策的責任邊界。
