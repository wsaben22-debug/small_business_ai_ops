# Small Business AI Ops

**AI 輔助營運決策與自動化系統**

Small Business AI Ops 是一套以客服案件（Support Ticket）為入口的營運決策與自動化系統，使用 Python、Django、Django REST Framework 與 Gemini AI 建立。

專案聚焦於中小型電商的訂單客服問題，將原本需要人工逐筆判斷的客服案件，轉換為可追蹤、可解釋且具有人工作業控制的 Workflow。

## Project Goal

本專案不只是 CRUD 或 AI 聊天機器人，而是建立一條可信任的營運決策流程。

核心理念：

> 先把一條 Workflow 做到值得相信，再讓整個系統逐步變聰明。

系統主要解決：

- 客服案件需要人工逐筆判斷處理優先順序。
- 不同風險案件缺乏一致的處理規則。
- 自動化操作需要安全限制，避免錯誤處理。
- 決策與人工審核過程缺乏可追溯紀錄。
- AI 建議需要整合既有業務規則，而不能直接取代人工決策。

## Core Workflow

```text
SupportTicket
    ↓
Eligibility
    ↓
Enrich
    ↓
Assess
(Severity / Impact / Urgency)
    ↓
Priority & Human Requirement
    ↓
TicketTriageDecision
    ↓
Risk Gate
    ├── Auto Handle
    │     └── Limited Internal Action
    │
    └── Human Review
          ├── AI Assist (Optional)
          └── Human Decision
    ↓
Record / Audit Trail
    ↓
Dashboard
```

## Key Features

### 1. Support Ticket Management

- 客戶、商品、訂單及客服案件資料模型
- 客服案件 CRUD
- 案件狀態與分類篩選
- Django Web UI
- REST API
- Authentication 與 Permission 控制

### 2. Rule-Based Triage

系統依據案件與訂單資訊評估：

- Severity：問題嚴重程度
- Impact：訂單影響程度
- Urgency：案件緊急程度
- Priority：綜合優先等級
- Human Requirement：是否需要人工介入

評估結果保存為 `TicketTriageDecision`。

Decision 採用不可變歷史紀錄設計，保留評估時的資料快照、分數、原因及規則版本。

### 3. Risk Gate & Automation

Risk Gate 決定案件後續處理路徑。

**Auto Handle**

僅允許符合既有規則的低風險資訊類案件執行有限度的內部動作。

目前不會自動退款、直接發送客服訊息或關閉案件。

**Human Review**

高優先級或需要人工授權的案件進入人工審核。

系統保存處理方式、審核原因及相關決策紀錄。

### 4. Gemini AI Assist

在既有 Rule-Based Workflow 基礎上整合 Google Gemini。

AI Assist 針對符合條件的人工審核案件產生：

- Summary：案件摘要
- Risk Notes：風險與處理注意事項
- Reply Draft：客服回覆草稿

AI 不直接核准退款、補償或繞過 Risk Gate。

系統透過 `TicketAIAssistRecord` 保存輸入快照、輸出結果、執行狀態、模型名稱及 Prompt 版本。

AI 呼叫失敗也會保留紀錄，讓人工審核流程可以繼續運作。

### 5. Decision History & Auditability

系統保存：

- TicketTriageDecision
- TriageRiskGateRecord
- TriageExecutionRecord
- TriageHumanReviewRecord
- TicketAIAssistRecord

藉此追蹤案件如何被評估、如何分流、執行了哪些動作，以及人工最終如何處理。

### 6. Operations Dashboard

提供營運決策統計、待人工審核案件及最近執行紀錄。

介面採用繁體中文與原生 CSS，呈現簡潔的營運管理介面。

## Technology Stack

| Category | Technology |
|---|---|
| Backend | Python, Django |
| REST API | Django REST Framework |
| Database | SQLite（目前開發與展示環境） |
| ORM | Django ORM |
| AI Integration | Google Gemini API、Google GenAI SDK |
| AI Output Validation | Pydantic |
| Frontend | Django Templates、HTML、CSS |
| Authentication | Django Auth、DRF Authentication |
| Testing | Django TestCase、APITestCase、Mock |
| Version Control | Git、GitHub |

## Project Evolution

| Version | Focus | Status |
|---|---|---|
| V0 | Models、CRUD、Web UI | Completed |
| V1 | REST API、Authentication、Permission | Completed |
| V2 | Rule-Based Workflow、Risk Gate、Automation | Completed |
| V2.0.1 | Reliability Hardening、Data Consistency | Completed |
| V3 Lite | Gemini AI Assist、Human-in-the-Loop | Core Implemented |
| Finalization | Demo Data、E2E Verification、Documentation | In Progress |

## Demo Data & Workflow

為了驗證多種營運情境，專案建立可重複執行的 Demo Data 初始化工具。

目前 Demo 資料包含：

| Data | Count |
|---|---:|
| Customer | 30 |
| Product | 15 |
| Order | 60 |
| OrderItem | 115 |
| SupportTicket | 40 |

其中：

- 34 筆案件已透過正式 Workflow 完成 Triage。
- 13 筆進入 Auto Handle。
- 21 筆進入 Human Review。
- 6 筆保留為現場操作案件。

系統使用 Django Management Command 管理 Demo 資料。

```bash
python manage.py seed_demo --with-tickets
```

預覽 Demo Triage：

```bash
python manage.py seed_demo_triage
```

正式執行：

```bash
python manage.py seed_demo_triage --execute
```

批次工具包含資料一致性檢查、Decision 防重複保護與資料庫交易保護。

請注意：Demo 指令會操作目前設定的資料庫，應僅在適當的本機或獨立展示環境使用。

## Verified Scenarios

**Auto Handle**

低風險資訊詢問經過規則評估後，執行允許的內部處理動作，將案件從 `open` 更新為 `in_progress`，並保存 Execution Record。

**AI-Assisted Human Review**

高風險商品缺失案件經 Risk Gate 進入人工審核，Gemini 成功產生案件摘要、風險提醒與客服回覆草稿。

**AI Failure Handling**

配送補償案件遭遇 Gemini HTTP 504，系統保留失敗紀錄，人工仍可完成審核並記錄處理原因。

## Testing & Reliability

截至 2026-10-22：

- Django Full Test Suite：**84 / 84 PASS**
- Django System Check：**0 issues**
- 完成 Decision / Risk Gate 一對一資料驗證
- 完成 Auto Handle 與 Human Review 核心 E2E 驗證
- 完成 AI Record 持久化與重新顯示驗證

開發過程重視：

- Regression Testing
- Data Consistency
- Permission Control
- Immutable Decision History
- Protected Delete
- Transaction Safety
- Failure Traceability
- Human-in-the-Loop

## Current Limitations

- 目前使用 SQLite 作為本機開發與展示資料庫。
- Gemini API 可能出現服務端逾時或 HTTP 5xx 錯誤。
- AI 回覆草稿需要人工確認，不可直接視為已完成的處理承諾。
- Demo Ticket 的等待時間會持續變化，正式展示前需要重新準備時間基準。
- 正式部署、監控及完整 Production Hardening 尚未完成。

## Project Status

目前 V3 Lite 核心功能已完成實作，正在進行 Final Verification、文件整理及成果發表準備。

本專案重點在於展示如何將業務規則、API、資料庫、Workflow、自動化與 AI Assist 整合為一套具備風險控制及可追溯性的營運系統。
