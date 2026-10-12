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