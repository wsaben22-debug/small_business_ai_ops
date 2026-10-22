# Small Business AI Operations

## 專案定位

建立一套「AI 輔助營運決策與自動化系統」。

核心原則：

> 先把一條 Workflow 做到值得相信，再讓整個系統逐步變聰明。

第一個核心場景：

**Support Ticket Triage / Exception Handling**

系統負責：

- 整理客服案件與訂單資訊
- 評估 Severity / Impact / Urgency
- 計算 Priority
- 判斷 Human Requirement
- 透過 Risk Gate 分流
- 低風險案件執行有限度自動化
- 高風險案件進入人工審核
- AI Assist 提供摘要、風險提示及客服草稿
- 保存 Decision / Execution / Human Review / AI History
- 透過 Dashboard 呈現營運決策

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

## 核心架構原則

### Immutable Decision

`TicketTriageDecision` 建立後保留原始決策歷史。

重新評估應建立新的 Decision，不直接覆蓋舊 Decision。

不儲存 `is_current`，最新 Decision 從 Decision History 推導。

### Decision Snapshot

保存：

- 評估時的 Category / Requested Action
- 訂單狀態與金額
- 等待時間
- Severity Level / Score / Reason
- Impact Level / Score / Reason
- Urgency Level / Score / Reason
- Priority Level / Score
- Human Requirement / Reason
- Rule Version
- Trigger Type

### Risk Gate

基本原則：

- `requires_human=True` → `human_review`
- `priority_level=high` → `human_review`
- 其他符合條件的案件 → `auto_handle`

### Low Risk Automation

目前限定資訊類內部處理：

- Action Code：`info_triage_prepared`
- Ticket Status：`open` → `in_progress`
- 不自動關閉案件
- 不自動退款
- 不自動發送客戶訊息

### Human Review

高風險或需要人工授權的案件由人工決策。

保存人工選擇、建議快照、是否採納建議及審核原因。

---

# V2.0.1 — Reliability Hardening ✅

完成日期：2026-10-13

## 階段目標

強化既有 V2 Workflow 的安全性、資料一致性及錯誤處理。

原則：

- 不重新設計 V2 核心架構
- 優先修正已確認的問題
- 使用 Red → Green 驗證 Business Rules
- 透過 Regression Tests 防止功能退化
- 避免不必要的 Refactor

## V2.0.1-1 — Anonymous API Read ✅

Commit：`c15b9b9`

完成匿名 API 讀取權限收斂。

## V2.0.1-2 — Evaluated Ticket Input Consistency ✅

Commit：`b31ffbf`

完成：

- 已評估 Ticket 禁止修改 Category
- 已評估 Ticket 禁止修改 Requested Action
- 已評估 Ticket 禁止更換 Order
- Customer 必須與 Order Customer 一致
- API Serializer 與 Web Form 分別實作驗證
- 保留合法的 Message / Status 更新
- 完成 PUT 與 Web Regression Tests

測試：59 / 59 PASS

設計重點：

保護影響當時 Decision 的核心輸入，避免目前 Ticket 與歷史 Decision 不一致。

## V2.0.1-3 — Persisted Risk Gate Consistency ✅

Commit：`cfb73cd`

完成：

- Dashboard human_review_count 改用 `get_risk_gate_result()`
- 優先使用已保存的 Risk Gate Route
- 保留 Legacy Fallback
- 不改變原本 Auto Handled Count 的定義
- 保留 High Risk Queue 既有邏輯

測試：60 / 60 PASS

## V2.0.1-4 — Small Safety Fixes ✅

Commit：`16d10cc`

完成：

**Protected Delete**

- Web 捕捉 ProtectedError
- Function-based API 回傳 HTTP 409
- APIView 回傳 HTTP 409
- Generic View 回傳 HTTP 409
- ModelViewSet 回傳 HTTP 409
- 保留合法刪除流程

**Human Review Validation**

- Service Layer 拒絕空白 Reason
- 防止重複提交
- 保留合法審核流程

測試：67 / 67 PASS

## V2.0.1 Final Verification

- Full Test Suite：67 / 67 PASS
- Django System Check：0 issues
- 已 Push GitHub
- 最終 Commit：`16d10cc`
- Branch：main

---

# V3 Lite — Gemini AI Assist ✅

狀態：核心功能已完成，Finalization 進行中。

## 階段目標

在已完成的 Rule-Based Workflow 上加入 AI Assist。

AI 不是新的正式決策引擎，而是人工審核的輔助分析層。

## AI Assist Workflow

```text
TicketTriageDecision
→ Persisted Risk Gate
→ human_review
→ Build AI Input Snapshot
→ Gemini AI
→ Validate Structured Output
→ TicketAIAssistRecord
→ Human Review
```

## AI Input Snapshot

透過 `build_ai_input_snapshot(decision)` 建立輸入快照。

包含：

- Ticket Message
- Category
- Requested Action
- Order Status
- Order Total
- Severity / Impact / Urgency
- Priority
- Risk Gate Route / Reason
- Prior Ticket Count

## AI Structured Output

使用 Pydantic 驗證：

- `summary`
- `risk_notes`
- `reply_draft`

AI 產生的內容僅供人工參考。

不得直接核准退款、補償或宣稱案件已完成處理。

## TicketAIAssistRecord

保存：

- Decision ForeignKey
- Input Snapshot
- Output Data
- Status
- Error Code
- Error Message
- Model Name
- Prompt Version
- Created By
- Created At

Status：

- pending
- success
- failed

AI Record 保留執行歷史，不因後續成功而覆蓋先前失敗紀錄。

## Gemini Integration

使用 Google GenAI SDK。

目前成功 Demo Record：

- Ticket：DEMO-T003
- Decision：#12
- AI Record：#3
- Status：success
- Model：gemini-3.8-flash
- Prompt Version：v1

已保存 Summary、Risk Notes、Reply Draft，並驗證重新開啟 Web 頁面後仍能正常顯示。

## AI Failure Handling

T020 曾發生：

- Exception Type：ServerError
- HTTP Status：504
- Error Code：GEMINI_REQUEST_FAILED

兩次失敗保存為 AI Record #4、#5。

新增安全 Logging：

- Exception Type
- HTTP Status Code

不直接將完整例外內容或可能包含敏感資訊的請求資料輸出至 Log。

Commit：`0a278f6`

目前 AI API 可靠性仍有待補強。

---

# Checkpoint 05 — Demo Data & Workflow ✅

完成期間：2026-10-21 至 2026-10-22

## Demo Data

建立固定規格：

| Data | Count |
|---|---:|
| Customer | 30 |
| Product | 15 |
| Order | 60 |
| OrderItem | 115 |
| SupportTicket | 40 |

初始化指令：

```bash
python manage.py seed_demo --with-tickets
```

具備：

- Demo 標記識別
- 衝突檢查
- 重複初始化防護
- transaction.atomic()
- Customer / Order 關聯驗證

## Demo Triage

獨立 Management Command：

`seed_demo_triage.py`

Dry Run：

```bash
python manage.py seed_demo_triage
```

Execute：

```bash
python manage.py seed_demo_triage --execute
```

安全保護：

- 僅操作 Demo Ticket 規格
- 六筆 Live Ticket 排除
- 已有 Decision 跳過
- 執行前檢查資料一致性
- 使用正式 V2 Workflow
- Transaction Rollback
- 執行後驗證 Decision / Gate / Execution

實際結果：

- 34 筆 Demo Decision
- 34 筆 Risk Gate Record
- 13 筆 Auto Handle
- 21 筆 Human Review
- 13 筆 Auto Handle Execution Record

Commit：`1d17187`

## Live Demo Tickets

保留六筆未評估案件：

- DEMO-T001
- DEMO-T002
- DEMO-T004
- DEMO-T025
- DEMO-T034
- DEMO-T040

預定分流：

- Auto Handle：2
- Human Review：4

已確認六筆目前為 open 且沒有 Decision。

**重要限制：**

Waiting Hours 會隨時間增加，成果發表前必須重新準備展示時間基準。

不得任意修改已有 Decision 的歷史資料。

---

# Checkpoint 05-6 — End-to-End Demo ✅

## Auto Handle

案例：DEMO-T005

- Ticket ID：23
- Decision ID：11
- Risk Gate：auto_handle
- Action：info_triage_prepared
- Execution Status：success
- Ticket：open → in_progress

已確認 Execution Record 完整保存。

## Human Review with AI Success

案例：DEMO-T003

- Ticket ID：21
- Decision ID：12
- Priority：high
- Risk Gate：human_review
- AI Record：#3 success

已驗證 AI 分析結果持久化與網頁重新顯示。

## Human Review with AI Failure

案例：DEMO-T020

- Ticket ID：38
- Decision ID：27
- Priority：low
- Risk Gate：human_review
- AI Records：#4、#5 failed
- Human Review Record：#4
- Selected Action：request_more_information
- Accepted Recommendation：False

已驗證即使 Gemini 呼叫失敗，人工審核仍可完成。

---

# Checkpoint 05-7 — Final Verification

截至 2026-10-22：

## 已完成

- Django Full Test Suite：84 / 84 PASS
- Django System Check：0 issues
- 34 筆 Demo Decision 各有一筆 Risk Gate
- 六筆 Live Ticket 目前分流符合規劃
- Auto Handle E2E 驗收
- Human Review E2E 驗收
- Gemini AI Record 持久化與重新顯示
- Git 程式碼 Checkpoint 已 Push

## 尚待完成

- 成果發表前 Live Ticket 時間基準重建
- Gemini 逾時及失敗時的展示可靠性改善
- AI 回覆草稿避免宣稱尚未完成的調查
- 完整 Demo 操作腳本
- README / PROJECT_NOTES 文件更新與提交
- Deployment 可行性及資料持久化評估
- 成果發表前最終驗收

---

# 後續改善清單

以下項目暫不插入目前主線，留待核心工作完成後統一評估。

## UI / Usability

- 客服案件列表搜尋欄位
- 決策儀表板搜尋
- 待人工審核清單搜尋
- 大量案件下的操作便利性

## AI Reliability

- 暫時性 5xx 錯誤的有限重試
- 更明確的錯誤提示
- 避免冗長等待影響展示
- Prompt 品質改善

## Engineering Hardening

- Demo Reset 安全機制
- Demo 執行操作保護
- Production Database 規劃
- Deployment、環境變數與持久化資料管理

---

# 後續專案複習重點

完成作品後，依照：

V0 → V1 → V2 → V2.0.1 → V3 Lite → Deployment

進行系統性複習。

重點包含：

- Django ORM 與 Data Flow
- REST API / Authentication / Permission
- Django TestCase / APITestCase
- TDD、Red → Green、Regression Testing
- Serializer.validate() / Form.clean()
- Decision Snapshot 與 Immutable History
- Risk Gate 與 Human Requirement
- ProtectedError 與 HTTP 409
- Service Layer / View Layer 責任分工
- Django Management Command
- transaction.atomic()
- Dry Run / Execute
- Gemini API / Pydantic
- Error Handling / Logging
- Git / GitHub
- Workflow Architecture
- Human-in-the-Loop

目前仍以完成專案及成果發表為優先，不因個別基礎概念尚未完全理解而停止開發。
