"""
RAG 第二步：轉向量（Embedding）與檢索（Retrieval）。

用「意思地圖」來想：
    - Embedding：幫每一段文字在地圖上找到座標（一串數字）
    - Retrieval：把顧客的問題也轉成座標，找出離它「最近」的幾頁手冊

整體分成兩個時機：

    【事前準備：手冊有更新時才做一次】
    build_knowledge_index()
        22 頁手冊 → Gemini Embedding → 存成 knowledge_base/index.json

    【每次查詢】
    search_knowledge("錢什麼時候回來？")
        問題 → Gemini Embedding → 和 22 頁比距離 → 回傳最近的前 3 頁

為什麼要先存成 index.json？
    手冊內容不常變，每次查詢都重新幫 22 頁算座標，既浪費時間也浪費 API 額度。
    所以先算好存起來，查詢時只需要算「問題」這一句的座標。
"""

import json
import math
import os
from pathlib import Path

from django.conf import settings
from google import genai
from google.genai import types

from .knowledge_service import load_knowledge_chunks


# Gemini 的 Embedding 模型名稱
EMBEDDING_MODEL = "gemini-embedding-001"

# 算好的座標存放位置（這是「產生出來的檔案」，不放進 Git）
DEFAULT_INDEX_PATH = Path(settings.BASE_DIR) / "knowledge_base" / "index.json"

# 一次最多送幾段文字給 Gemini（API 有單次上限）
EMBED_BATCH_SIZE = 50


class RetrievalError(Exception):
    """檢索流程中可預期的錯誤，例如沒有設定 API Key、還沒建立索引。"""


# ---------------------------------------------------------------------------
# 1. 算座標：呼叫 Gemini Embedding
# ---------------------------------------------------------------------------

def embed_texts(texts, task_type):
    """
    把多段文字轉成座標（向量）。

    task_type 是告訴 Gemini「這段文字的用途」，會影響座標的品質：
        - "RETRIEVAL_DOCUMENT"：這是手冊內容，等著被別人找
        - "RETRIEVAL_QUERY"：這是顧客的問題，要拿去找手冊

    回傳：list，每個元素是一個座標（一串小數）。
    """

    api_key = os.getenv("GEMINI_API_KEY")

    if not api_key:
        raise RetrievalError("GEMINI_API_KEY is not configured")

    client = genai.Client(api_key=api_key)

    try:
        vectors = []

        # 分批送出：第 0~49 段、第 50~99 段……
        for start in range(0, len(texts), EMBED_BATCH_SIZE):
            batch = texts[start:start + EMBED_BATCH_SIZE]

            response = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=batch,
                config=types.EmbedContentConfig(task_type=task_type),
            )

            vectors.extend(embedding.values for embedding in response.embeddings)

        return vectors

    finally:
        client.close()


# ---------------------------------------------------------------------------
# 2. 比距離：兩個座標有多「像」
# ---------------------------------------------------------------------------

def cosine_similarity(vector_a, vector_b):
    """
    計算兩個座標的相似度（Cosine Similarity，餘弦相似度）。

    結果介於 -1 到 1 之間：
        越接近 1  → 意思越像
        越接近 0  → 沒什麼關係

    不需要背公式，只要記得：「分數越高，意思越接近」。
    """

    dot = sum(a * b for a, b in zip(vector_a, vector_b))
    length_a = math.sqrt(sum(a * a for a in vector_a))
    length_b = math.sqrt(sum(b * b for b in vector_b))

    if length_a == 0 or length_b == 0:
        return 0.0

    return dot / (length_a * length_b)


# ---------------------------------------------------------------------------
# 3. 事前準備：幫整本手冊算座標，存成 index.json
# ---------------------------------------------------------------------------

def build_knowledge_index(index_path=DEFAULT_INDEX_PATH, embed=embed_texts):
    """
    幫所有手冊頁面算座標，並存到 index.json。

    embed 參數預設是真的 Gemini（embed_texts）。
    測試時可以換成假的函式，就不需要真的呼叫 API。
    """

    chunks = load_knowledge_chunks()

    vectors = embed(
        [chunk.to_context_text() for chunk in chunks],
        task_type="RETRIEVAL_DOCUMENT",
    )

    entries = [
        {
            "chunk_id": chunk.chunk_id,
            "doc_title": chunk.doc_title,
            "section_title": chunk.section_title,
            "text": chunk.text,
            "vector": vector,
        }
        for chunk, vector in zip(chunks, vectors)
    ]

    index = {
        "model": EMBEDDING_MODEL,
        "entries": entries,
    }

    Path(index_path).write_text(
        json.dumps(index, ensure_ascii=False),
        encoding="utf-8",
    )

    return len(entries)


def load_knowledge_index(index_path=DEFAULT_INDEX_PATH):
    """讀取 index.json。還沒建立的話，提示要先執行建立指令。"""

    index_path = Path(index_path)

    if not index_path.exists():
        raise RetrievalError(
            "Knowledge index not found. "
            "Run: python manage.py build_knowledge_index"
        )

    return json.loads(index_path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# 4. 查詢：找出和問題最相關的前幾頁
# ---------------------------------------------------------------------------

def search_knowledge(query, top_k=3, index_path=DEFAULT_INDEX_PATH, embed=embed_texts):
    """
    輸入一個問題，回傳最相關的前 top_k 頁。

    步驟：
        1. 讀取事先算好的手冊座標
        2. 把問題轉成座標
        3. 問題和每一頁比相似度
        4. 依分數由高到低排序，取前 top_k 名
    """

    index = load_knowledge_index(index_path)

    query_vector = embed([query], task_type="RETRIEVAL_QUERY")[0]

    results = []

    for entry in index["entries"]:
        score = cosine_similarity(query_vector, entry["vector"])

        results.append(
            {
                "chunk_id": entry["chunk_id"],
                "doc_title": entry["doc_title"],
                "section_title": entry["section_title"],
                "text": entry["text"],
                "score": score,
            }
        )

    # key=lambda r: r["score"] 的意思是「用 score 這個欄位來排序」
    results.sort(key=lambda r: r["score"], reverse=True)

    return results[:top_k]
