import os
import tempfile
from pathlib import Path
from unittest import mock

from django.test import SimpleTestCase

from .retrieval_service import (
    RetrievalError,
    build_knowledge_index,
    cosine_similarity,
    embed_texts,
    search_knowledge,
)


def fake_embed(texts, task_type):
    """
    假的 Embedding，測試時用來取代真正的 Gemini。

    規則很簡單：座標 = [出現「退款」的次數, 出現「配送」的次數, 出現「補償」的次數]
    這樣不用連網路、不花 API 額度，結果也每次都一樣。
    """

    keywords = ["退款", "配送", "補償"]

    return [[text.count(word) for word in keywords] for text in texts]


class CosineSimilarityTests(SimpleTestCase):

    def test_same_direction_scores_one(self):
        self.assertAlmostEqual(cosine_similarity([1, 2], [2, 4]), 1.0)

    def test_unrelated_vectors_score_zero(self):
        self.assertAlmostEqual(cosine_similarity([1, 0], [0, 1]), 0.0)

    def test_zero_vector_scores_zero(self):
        self.assertEqual(cosine_similarity([0, 0], [1, 1]), 0.0)


class BuildAndSearchTests(SimpleTestCase):

    def setUp(self):
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        self.index_path = Path(temp_dir.name) / "index.json"

    def test_build_index_saves_every_chunk(self):
        count = build_knowledge_index(index_path=self.index_path, embed=fake_embed)

        self.assertEqual(count, 22)
        self.assertTrue(self.index_path.exists())

    def test_search_returns_top_k_sorted_by_score(self):
        build_knowledge_index(index_path=self.index_path, embed=fake_embed)

        results = search_knowledge(
            "退款", top_k=3, index_path=self.index_path, embed=fake_embed
        )

        self.assertEqual(len(results), 3)

        scores = [r["score"] for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

        # 用假 Embedding 時，問「退款」找到的第一名，內容一定有提到退款
        self.assertIn("退款", results[0]["text"])

    def test_search_without_index_raises_clear_error(self):
        with self.assertRaises(RetrievalError):
            search_knowledge("退款", index_path=self.index_path, embed=fake_embed)


class EmbedTextsTests(SimpleTestCase):

    def test_missing_api_key_raises_clear_error(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            with self.assertRaises(RetrievalError):
                embed_texts(["測試"], task_type="RETRIEVAL_QUERY")
