# Knowledge Base（RAG 知識庫）

這個資料夾存放 RAG（Retrieval-Augmented Generation）要檢索的「公司知識」。

> 注意：以下政策內容皆為**作品展示用的虛構政策**，不代表任何真實公司的規定。

## 寫作規則

- 每份文件是一個 Markdown 檔，第一行用 `# 標題` 寫文件名稱。
- 每個獨立主題用 `## 小標題` 分段。系統會**依照 `##` 小標題切段**，
  所以一個段落最好只講一件事，並且單獨閱讀也看得懂。
- 段落內可以使用條列，但盡量不要在一個段落塞超過 500 字。

## 目前文件

| 檔案 | 內容 | 對應 Ticket Category |
|---|---|---|
| `policies/refund_policy.md` | 退款條件、時程、例外 | refund |
| `policies/delivery_policy.md` | 配送時效、延遲處理 | delivery |
| `policies/damaged_missing_policy.md` | 商品損壞、缺件處理 | damaged / missing |
| `policies/compensation_policy.md` | 補償原則與授權層級 | requested_action=compensation |
| `policies/customer_service_faq.md` | 常見問題與回覆語氣 | other / info |
