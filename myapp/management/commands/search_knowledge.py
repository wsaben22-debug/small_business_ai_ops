"""
輸入一個問題，找出最相關的手冊頁面。

    python manage.py search_knowledge "錢什麼時候會回到我帳戶？"
    python manage.py search_knowledge "東西寄好久都沒來" --top-k 5
"""

from django.core.management.base import BaseCommand, CommandError

from myapp.retrieval_service import RetrievalError, search_knowledge


class Command(BaseCommand):

    help = "用語意搜尋，找出和問題最相關的手冊頁面"

    def add_arguments(self, parser):
        parser.add_argument("query", help="要查詢的問題")
        parser.add_argument("--top-k", type=int, default=3, help="回傳前幾名")

    def handle(self, *args, **options):
        try:
            results = search_knowledge(options["query"], top_k=options["top_k"])
        except RetrievalError as exc:
            raise CommandError(str(exc))

        self.stdout.write(f"問題：{options['query']}\n")

        for rank, result in enumerate(results, start=1):
            self.stdout.write(
                f"第 {rank} 名（相似度 {result['score']:.3f}）"
                f"[{result['chunk_id']}] {result['doc_title']} > {result['section_title']}"
            )
            self.stdout.write(f"    {result['text'][:60]}...\n")
