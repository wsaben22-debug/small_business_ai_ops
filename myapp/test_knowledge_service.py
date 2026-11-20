from django.test import SimpleTestCase

from .knowledge_service import (
    KnowledgeChunk,
    load_knowledge_chunks,
    split_long_text,
    split_markdown_into_chunks,
)


# SimpleTestCase：不需要資料庫的測試，跑得比 TestCase 快
class SplitMarkdownIntoChunksTests(SimpleTestCase):

    def test_each_h2_section_becomes_one_chunk(self):
        markdown = (
            "# 退款政策\n"
            "\n"
            "## 申請期限\n"
            "收到商品 7 天內。\n"
            "\n"
            "## 處理時程\n"
            "7 到 14 個工作天。\n"
        )

        chunks = split_markdown_into_chunks("refund.md", markdown)

        self.assertEqual(len(chunks), 2)

        self.assertEqual(chunks[0].chunk_id, "refund.md#1")
        self.assertEqual(chunks[0].doc_title, "退款政策")
        self.assertEqual(chunks[0].section_title, "申請期限")
        self.assertEqual(chunks[0].text, "收到商品 7 天內。")

        self.assertEqual(chunks[1].section_title, "處理時程")

    def test_section_without_body_is_skipped(self):
        markdown = "# 文件\n\n## 空段落\n\n## 有內容\n內容\n"

        chunks = split_markdown_into_chunks("doc.md", markdown)

        self.assertEqual(len(chunks), 1)
        self.assertEqual(chunks[0].section_title, "有內容")

    def test_text_before_first_h2_is_ignored(self):
        markdown = "# 文件\n前言不屬於任何段落\n\n## 段落\n內容\n"

        chunks = split_markdown_into_chunks("doc.md", markdown)

        self.assertEqual(len(chunks), 1)
        self.assertNotIn("前言", chunks[0].text)

    def test_missing_h1_falls_back_to_source_name(self):
        chunks = split_markdown_into_chunks("doc.md", "## 段落\n內容\n")

        self.assertEqual(chunks[0].doc_title, "doc.md")

    def test_long_section_is_split_but_keeps_section_title(self):
        long_body = "\n\n".join(["甲" * 30, "乙" * 30, "丙" * 30])
        markdown = f"# 文件\n## 長段落\n{long_body}\n"

        chunks = split_markdown_into_chunks("doc.md", markdown, max_chars=40)

        self.assertEqual(len(chunks), 3)
        self.assertEqual(
            [c.chunk_id for c in chunks],
            ["doc.md#1", "doc.md#2", "doc.md#3"],
        )
        for chunk in chunks:
            self.assertEqual(chunk.section_title, "長段落")


class SplitLongTextTests(SimpleTestCase):

    def test_short_text_is_returned_as_is(self):
        self.assertEqual(split_long_text("短文字", max_chars=10), ["短文字"])

    def test_paragraphs_are_merged_until_limit(self):
        text = "aaaa\n\nbbbb\n\ncccc"

        # "aaaa\n\nbbbb" 長度 10，剛好不超過上限
        self.assertEqual(
            split_long_text(text, max_chars=10),
            ["aaaa\n\nbbbb", "cccc"],
        )

    def test_single_oversized_paragraph_is_not_cut_mid_sentence(self):
        text = "x" * 50

        self.assertEqual(split_long_text(text, max_chars=10), [text])


class KnowledgeChunkTests(SimpleTestCase):

    def test_context_text_includes_titles(self):
        chunk = KnowledgeChunk(
            chunk_id="refund.md#1",
            source="refund.md",
            doc_title="退款政策",
            section_title="處理時程",
            text="7 到 14 個工作天。",
        )

        self.assertEqual(
            chunk.to_context_text(),
            "【退款政策 > 處理時程】\n7 到 14 個工作天。",
        )


class LoadKnowledgeChunksTests(SimpleTestCase):

    def test_project_knowledge_base_loads(self):
        chunks = load_knowledge_chunks()

        sources = {chunk.source for chunk in chunks}

        self.assertIn("refund_policy.md", sources)
        self.assertIn("delivery_policy.md", sources)

        # chunk_id 必須唯一，之後 AI 引用來源才不會混淆
        chunk_ids = [chunk.chunk_id for chunk in chunks]
        self.assertEqual(len(chunk_ids), len(set(chunk_ids)))

        for chunk in chunks:
            self.assertTrue(chunk.text)
