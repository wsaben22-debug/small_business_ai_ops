# 學習筆記 01：RAG 知識庫與文件切段（Chunking）

## 這一步要解決什麼問題？

目前 `ai_service.py` 的 prompt 寫著「不得編造公司政策」，但 AI 手上其實**沒有任何公司政策**可以參考。結果 AI 只能寫出很模糊的回覆，例如「我們會盡快為您處理」。

RAG（Retrieval-Augmented Generation，檢索增強生成）的想法很簡單：

> 問 AI 之前，先去「知識庫」找出相關資料，連同問題一起交給 AI。

就像考試從閉書考變成「可以帶小抄」：AI 不必靠記憶亂猜，而是根據你給的資料回答，還可以說出它引用了哪一段。

## RAG 的完整流程

```text
【事前準備：只做一次】
知識文件 (.md)
    ↓ 切段 Chunking              ← 本次 PR
KnowledgeChunk × N
    ↓ 轉向量 Embedding            ← 下一個 PR
向量資料（存起來）

【每次客服案件進來時】
案件內容
    ↓ 轉向量 Embedding
    ↓ 找出最相似的 Chunk（Retrieval）
相關政策段落 Top 3
    ↓ 和案件快照一起放進 Prompt
Gemini 產生有依據的回覆草稿     ← 之後接到 ai_service.py
```

## 本次新增的檔案

| 檔案 | 角色 |
|---|---|
| `knowledge_base/policies/*.md` | 5 份虛構的公司政策，是 RAG 的「小抄」 |
| `myapp/knowledge_service.py` | 讀取文件，切成 `KnowledgeChunk` |
| `myapp/management/commands/show_knowledge_chunks.py` | 在終端機印出切段結果，讓你「看見」 Chunk |
| `myapp/test_knowledge_service.py` | 10 個測試，確認切段規則正確 |

## 關鍵設計：為什麼依 `##` 小標題切段？

切段的方法主要有兩種：

| 方法 | 優點 | 缺點 |
|---|---|---|
| 固定字數切（例如每 500 字） | 簡單，任何文件都能用 | 可能把一句話切成兩半，意思壞掉 |
| 依文件結構切（標題、段落） | 每段意思完整 | 文件需要有一致的格式 |

我們的政策文件是自己寫的，可以控制格式，所以選擇**依 `##` 小標題切**：一個小標題就是一個主題，例如「退款處理時程」。萬一某段太長（超過 500 字），才再依空行拆開，而且不會切斷句子。

另外，每個 Chunk 都會記住它屬於哪份文件、哪個小標題（`to_context_text()`）。因為單看「7 到 14 個工作天」這句話，AI 不知道它在講退款還是配送；加上「【退款政策 > 退款處理時程】」就清楚了。

## 和你既有專案的一致性

- `KnowledgeChunk` 使用 `frozen=True`（建立後不能改），和你的 Decision「不可變紀錄」是同一種思維。
- `chunk_id`（例如 `refund_policy.md#4`）是為了之後讓 AI **標示引用來源**，人工審核時才能回頭查證，延續你重視「可追溯性」的設計。
- 讀檔時寫明 `encoding="utf-8"`：Windows 預設的編碼不是 UTF-8，不寫的話讀中文檔可能出錯。

## 動手試試看（Windows / VS Code）

```bash
# 進入你的 venv 之後
python manage.py show_knowledge_chunks
python manage.py show_knowledge_chunks --max-chars 50
python manage.py test myapp.test_knowledge_service
```

---

## 小練習

做完再展開答案。看不懂也沒關係，直接回覆我，我會再解釋。

**練習 1：** `python manage.py show_knowledge_chunks` 會印出幾個 Chunk？`refund_policy.md` 會被切成幾段？（提示：去數 `##`）

<details><summary>答案</summary>

總共 22 個 Chunk。`refund_policy.md` 有 5 個 `##` 小標題，所以是 5 段。

</details>

**練習 2：** 下面這段 Markdown，`split_markdown_into_chunks("a.md", text)` 會產生幾個 Chunk？各自的 `section_title` 是什麼？

```markdown
# 測試文件
這是前言
## A
內容 A
## B
## C
內容 C
```

<details><summary>答案</summary>

2 個：`A` 和 `C`。「這是前言」在第一個 `##` 之前，不屬於任何段落，會被忽略；`B` 沒有內文，也會被略過。

</details>

**練習 3（思考題）：** 如果把 `DEFAULT_MAX_CHARS` 改成 20，會發生什麼事？Chunk 太小對 AI 回答有什麼壞處？

<details><summary>答案</summary>

多段落的小標題會被拆成更多塊，但「單一段落超長」的部分仍會整段保留（我們不硬切句子）。Chunk 太小的壞處是上下文不足：例如只拿到「需由主管再次確認」，卻不知道前面講的是「3,000 元以上的退款」，AI 就可能誤解。所以 Chunk 大小是在「精準」和「完整」之間取捨。

</details>

**練習 4（面試常考）：** 用一句話向面試官說明：為什麼不把所有政策文件一次全部塞給 AI 就好？

<details><summary>參考答案</summary>

文件一多就會超過模型能讀的長度、成本變高、回應變慢，而且無關內容會干擾 AI 的判斷；RAG 只挑出最相關的幾段，讓回答更準確、更便宜，也能清楚標示引用來源。

</details>
