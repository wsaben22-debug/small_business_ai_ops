"""
幫知識庫手冊算座標（Embedding），存成 knowledge_base/index.json。

手冊內容有修改時，重新執行一次即可：
    python manage.py build_knowledge_index
"""

from django.core.management.base import BaseCommand, CommandError

from myapp.retrieval_service import (
    DEFAULT_INDEX_PATH,
    RetrievalError,
    build_knowledge_index,
)


class Command(BaseCommand):

    help = "使用 Gemini Embedding 建立知識庫索引（index.json）"

    def handle(self, *args, **options):
        try:
            count = build_knowledge_index()
        except RetrievalError as exc:
            raise CommandError(str(exc))

        self.stdout.write(
            self.style.SUCCESS(f"已建立 {count} 頁的座標，存到 {DEFAULT_INDEX_PATH}")
        )
