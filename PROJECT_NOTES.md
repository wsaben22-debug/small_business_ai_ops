# Small Business AI Operations

## 專案定位

建立一套「營運決策與自動化系統」。

核心原則：

> 先把一條 Workflow 做到值得相信，再讓整個系統逐步變聰明。

目前第一個核心場景：

Support Ticket Triage / Exception Handling

系統目標不是單純顯示資料，而是：

- 整理客服案件與訂單資訊
- 評估 Ticket 的 Severity / Impact / Urgency
- 計算 Priority
- 判斷是否需要人工介入
- 透過 Risk Gate 進行風險分流
- 低風險案件執行有限度自動化
- 高風險案件交由人工審核
- 保存 Decision / Execution / Human Review History
- 透過 Dashboard 呈現營運決策結果
- 為後續 AI Assist 建立可信任的 Workflow 基礎


---

## V0 — CRUD Foundation ✅

完成 Models：

- Customer
- Product
- Order
- OrderItem
- SupportTicket

完成 Web 功能：

- Create
- List
- Edit
- Delete
- Ticket 狀態篩選
- Ticket 分類篩選


---

## V1 — REST API ✅

完成：

- Function-based API
- APIView
- Generic Views
- ModelViewSet + DefaultRouter
- GET / POST / PUT / PATCH / DELETE

Authentication：

- SessionAuthentication
- BasicAuthentication
- TokenAuthentication

Permission：

- Custom DRF Permission

Testing：

- APITestCase
- API Authentication / Permission Tests

V1 Final：

- v1.0
- 2026-09-15


---

# V2 — Support Ticket Triage Workflow ✅

## 核心 Workflow

```text
SupportTicket
→ Eligibility
→ Enrich
→ Assess
→ Decide
→ TicketTriageDecision
→ Risk Gate
→ Auto Handle / Human Review
→ Record
→ Surface

```

---

# V2.0.1 — Reliability Hardening ✅

完成日期：2026-10-13

## 階段目標

V2.0.1 不新增主要業務功能，重點是強化既有 V2 Workflow 的可靠性、資料一致性與錯誤處理。

原則：

- 不重新設計 V2 核心架構
- 優先修正已確認的問題
- 使用 Red → Green 驗證 Business Rules
- 透過 Regression Tests 確保既有功能不受影響
- 不進行不必要的 Refactor

## V2.0.1-1 — Anonymous API Read ✅

Commit：c15b9b9

完成 API 匿名讀取權限收斂，避免未授權的資料存取。

## V2.0.1-2 — Evaluated Ticket Input Consistency ✅

Commit：b31ffbf

完成：

- 已評估 Ticket 禁止修改 category
- 已評估 Ticket 禁止修改 requested_action
- 已評估 Ticket 禁止更換 order
- Customer 必須與 Order Customer 一致
- API Serializer 與 Web Form 分別實作驗證
- 保留合法的 message / status 更新
- 完成 PUT 與 Web Regression Tests

測試結果：59 / 59 PASS

設計重點：

Decision 已經建立後，必須保護影響當時決策的核心輸入，避免目前 Ticket 資料與歷史 Decision 不一致。

## V2.0.1-3 — Persisted Risk Gate Consistency ✅

Commit：cfb73cd

完成：

- Dashboard human_review_count 改用 get_risk_gate_result()
- 優先使用已儲存的 Risk Gate Route
- 保留沒有 Gate Record 時的 Legacy Fallback
- 不改變 auto_handled_count 的原本定義
- 不修改 High Risk Queue 原有邏輯

測試結果：60 / 60 PASS

設計重點：

正式保存的 Risk Gate Result 應作為分流結果的優先依據，避免 Dashboard 自行重新推導造成不一致。

## V2.0.1-4 — Small Safety Fixes ✅

Commit：16d10cc

完成：

1. Protected Delete
   - Web 捕捉 ProtectedError 並顯示業務錯誤
   - Function-based API 回傳 HTTP 409
   - APIView 回傳 HTTP 409
   - Generic View 回傳 HTTP 409
   - ModelViewSet 回傳 HTTP 409
   - 保留沒有 Decision 的合法刪除流程

2. Human Review Reason Validation
   - Service Layer 拒絕空白 Reason
   - 防止建立沒有有效原因的人工審查紀錄
   - 保留正常 Human Review 與防止重複提交的既有邏輯

測試結果：67 / 67 PASS

## V2.0.1 Final Verification

- Full Test Suite：67 / 67 PASS
- Django System Check：0 issues
- 所有四個 Hardening Checkpoint 均已 Push GitHub
- 最終程式碼 Commit：16d10cc
- Branch：main

V2.0.1 核心程式開發及驗收完成。

---

## 後續專案複習重點

整體作品完成後，再依照 V0 → V1 → V2 → V2.0.1 → V3 Lite → Deployment 的順序進行系統性複習。

V2.0.1 特別需要重新理解：

- TDD：Red → Green → Refactor
- Regression Testing 與一般功能測試的差異
- Django TestCase / APITestCase
- assertEqual、assertIsNone、assertTrue 等 Assertions
- API Serializer.validate() 與 Web Form.clean()
- Decision Snapshot 與資料一致性
- Persisted Risk Gate 與 Legacy Fallback
- ProtectedError、HTTP 409 與錯誤處理
- Service Layer 與 View Layer 的責任分工
- Git status、Git diff、Git add、Commit、Push

目前先以完成專案為優先，不因基本功尚未完全理解而停止開發。

---

# Next Stage — V3 Lite AI Assist

狀態：Planned

V3 Lite 將在已完成的 Rule-Based Workflow 上加入有限度 AI Assist。

主要方向：

- AI 作為輔助分析與建議層
- 保留既有 Rule-Based Decision 與 Risk Gate
- AI 不直接繞過正式業務規則
- 保留可追蹤與可解釋的決策流程
- 控制實作範圍，兼顧 Deployment 與專案展示時間

具體功能、資料流與 API 整合方式，待 V3 Lite 開始時正式確認。
