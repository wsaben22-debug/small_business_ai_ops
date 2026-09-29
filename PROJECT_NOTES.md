# Small Business AI Operations

## 專案定位

建立一套「AI 輔助的營運自動化決策系統」。

核心原則：

> 先把一條 Workflow 做到值得相信，再讓整個系統逐步變聰明。

目前第一個核心場景：

Support Ticket Triage / Exception Handling

系統目標不是單純顯示資料，而是：

- 自動整理營運資訊
- 評估 Ticket 風險與優先級
- 低風險案件自動執行
- 高風險案件交給人工判斷
- 保留 Decision / Execution History
- 逐步建立 Evaluation Layer


## V0 — CRUD Foundation ✅

完成：

- Customer
- Product
- Order
- OrderItem
- SupportTicket

功能：

- CRUD
- Ticket 狀態篩選
- Ticket 分類篩選


## V1 — REST API ✅

完成：

- Function-based API
- APIView
- Generic Views
- ModelViewSet + Router
- GET / POST / PUT / PATCH / DELETE
- Authentication
- Permission
- Token
- API Tests


## V2 — Support Ticket Triage Workflow 🚧

核心 Workflow：

SupportTicket
→ Eligibility
→ Enrich
→ Assess
→ Decide
→ TicketTriageDecision
→ Risk Gate
→ Auto Handle / Human Review
→ Record
→ Evaluation
→ Surface

目前已完成：

- TicketTriageDecision
- Input Snapshot
- Severity / Impact / Urgency
- Priority
- Human Requirement
- Decision History
- Immutable Decision
- SupportTicket PROTECT
- run_triage()
- Risk Gate
- Low Risk Automation
- High Risk Decision Support Package
- Customer / Order Context
- Ticket History Context
- High Risk Recommendation
- TriageExecutionRecord
- Execution success / skipped history
- Evaluation Layer v1
  - total_decisions
  - human_review_rate
  - auto_handled_rate
- Automated Tests


## V2 下一步

- 補強 Evaluation Layer
- Surface / Dashboard
- Demo 操作流程
- V2 整體整理與驗收


## Future

後續功能不預先綁死版本號，依實際產品需求決定。

可能方向：

- AI Assist
- Response Draft
- Refund / Exchange Policy
- RAG
- External Tool Integration
- Multi-channel Integration
- More Workflow Automation