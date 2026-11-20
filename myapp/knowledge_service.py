"""
RAG 第一步：讀取知識庫文件，並切成一段一段的 Chunk。

RAG 的完整流程是：
    1. 準備知識文件          ← 本檔案負責
    2. 切段 (Chunking)       ← 本檔案負責
    3. 轉成向量 (Embedding)  ← 下一個 PR
    4. 檢索 (Retrieval)      ← 下一個 PR
    5. 交給 AI 產生回答      ← 之後接到 ai_service.py

為什麼要切段？
    AI 一次能讀的內容有限，而且整份文件丟進去，重點會被稀釋。
    把文件切成「一段只講一件事」的小塊，之後才能只挑出最相關的幾段給 AI。

本檔案只做純文字處理，不連資料庫、不呼叫 API，所以很好測試。
"""

from dataclasses import dataclass
from pathlib import Path

from django.conf import settings


# 知識庫資料夾的預設位置：專案根目錄下的 knowledge_base/
DEFAULT_KNOWLEDGE_DIR = Path(settings.BASE_DIR) / "knowledge_base" / "policies"

# 一個 Chunk 最多幾個字。太長會稀釋重點，太短會失去上下文。
DEFAULT_MAX_CHARS = 500


@dataclass(frozen=True)
class KnowledgeChunk:
    """
    一個切好的知識片段。

    dataclass 是 Python 內建的「資料盒子」寫法，
    只要寫欄位名稱，就會自動產生 __init__ 等方法。
    frozen=True 代表建立後不能修改，和專案中「不可變紀錄」的精神一致。
    """

    # 唯一識別碼，例如 "refund_policy.md#2"，之後 AI 引用來源時會用到
    chunk_id: str

    # 來源檔名，例如 "refund_policy.md"
    source: str

    # 文件標題（# 開頭那一行），例如 "退款政策"
    doc_title: str

    # 段落標題（## 開頭那一行），例如 "退款處理時程"
    section_title: str

    # 段落內文
    text: str

    def to_context_text(self):
        """
        組合成要交給 AI 的文字。

        把「文件標題 > 段落標題」放在內文前面，
        AI 和之後的 Embedding 才知道這段話是在講哪個主題。
        """
        return f"【{self.doc_title} > {self.section_title}】\n{self.text}"


def split_long_text(text, max_chars=DEFAULT_MAX_CHARS):
    """
    如果一個段落超過 max_chars，就依照「空行」（段落）拆成多塊。

    為什麼依空行拆、而不是硬切每 500 字？
        硬切可能把一句話切成兩半，意思就壞掉了。
        依空行拆，至少能保留完整的句子與條列。
    """

    if len(text) <= max_chars:
        return [text]

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

    pieces = []
    current = ""

    for paragraph in paragraphs:
        # 加上這一段後還沒超過上限，就繼續累積
        candidate = f"{current}\n\n{paragraph}" if current else paragraph

        if len(candidate) <= max_chars:
            current = candidate
        else:
            if current:
                pieces.append(current)
            # 單一段落本身就超長時，只能保留整段（不硬切句子）
            current = paragraph

    if current:
        pieces.append(current)

    return pieces


def split_markdown_into_chunks(source, markdown_text, max_chars=DEFAULT_MAX_CHARS):
    """
    把一份 Markdown 文件切成多個 KnowledgeChunk。

    規則：
        - 第一個 "# " 開頭的行是文件標題
        - 每個 "## " 開頭的行開始一個新段落
        - 沒有內文的段落會被略過
    """

    doc_title = source
    sections = []          # 每個元素是 (段落標題, [內文行])
    current_title = None
    current_lines = []

    for line in markdown_text.splitlines():

        if line.startswith("# "):
            doc_title = line[2:].strip()

        elif line.startswith("## "):
            # 遇到新的小標題：先把上一段存起來，再開始新的一段
            if current_title is not None:
                sections.append((current_title, current_lines))

            current_title = line[3:].strip()
            current_lines = []

        elif current_title is not None:
            current_lines.append(line)

    # 迴圈結束後，最後一段還沒存，要補存
    if current_title is not None:
        sections.append((current_title, current_lines))

    chunks = []

    for section_title, lines in sections:
        body = "\n".join(lines).strip()

        if not body:
            continue

        for piece in split_long_text(body, max_chars=max_chars):
            chunks.append(
                KnowledgeChunk(
                    chunk_id=f"{source}#{len(chunks) + 1}",
                    source=source,
                    doc_title=doc_title,
                    section_title=section_title,
                    text=piece,
                )
            )

    return chunks


def load_knowledge_chunks(directory=DEFAULT_KNOWLEDGE_DIR, max_chars=DEFAULT_MAX_CHARS):
    """
    讀取資料夾內所有 .md 檔，回傳全部的 Chunk。

    sorted() 讓檔案順序固定，每次執行結果都一樣，方便測試與除錯。
    encoding="utf-8" 很重要：Windows 預設編碼不是 UTF-8，
    不指定的話，讀中文檔案可能出現亂碼或錯誤。
    """

    directory = Path(directory)
    all_chunks = []

    for path in sorted(directory.glob("*.md")):
        markdown_text = path.read_text(encoding="utf-8")

        all_chunks.extend(
            split_markdown_into_chunks(
                source=path.name,
                markdown_text=markdown_text,
                max_chars=max_chars,
            )
        )

    return all_chunks
