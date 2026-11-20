"""
用來「看見」知識庫被切成哪些 Chunk 的小工具。

執行方式：
    python manage.py show_knowledge_chunks
    python manage.py show_knowledge_chunks --max-chars 200
"""

from django.core.management.base import BaseCommand

from myapp.knowledge_service import DEFAULT_MAX_CHARS, load_knowledge_chunks


class Command(BaseCommand):

    help = "顯示知識庫文件切段（Chunking）後的結果"

    def add_arguments(self, parser):
        parser.add_argument(
            "--max-chars",
            type=int,
            default=DEFAULT_MAX_CHARS,
            help="每個 Chunk 的最大字數",
        )

    def handle(self, *args, **options):
        chunks = load_knowledge_chunks(max_chars=options["max_chars"])

        for chunk in chunks:
            self.stdout.write(
                f"[{chunk.chunk_id}] {chunk.doc_title} > {chunk.section_title}"
                f"（{len(chunk.text)} 字）"
            )

        self.stdout.write(self.style.SUCCESS(f"共 {len(chunks)} 個 Chunk"))
