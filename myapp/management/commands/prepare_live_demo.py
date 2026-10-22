
from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from myapp.models import SupportTicket
from myapp.management.commands.seed_demo import (
    DEMO_TICKETS,
    DEMO_LIVE_TICKET_IDS,
)
from myapp.management.commands.seed_demo_triage import (
    predict_demo_route,
)


EXPECTED_ROUTES = {
    "DEMO-T001": "auto_handle",
    "DEMO-T002": "human_review",
    "DEMO-T004": "auto_handle",
    "DEMO-T025": "human_review",
    "DEMO-T034": "human_review",
    "DEMO-T040": "human_review",
}


class Command(BaseCommand):
    help = "Safely prepare Live Demo Ticket waiting times"

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Update Live Demo Ticket timestamps",
        )

    def handle(self, *args, **options):
        execute = options["execute"]

        # Safety Gate
        if execute and not getattr(
            settings, "ALLOW_DEMO_DATA_RESET", False
        ):
            raise CommandError(
                "Demo data reset is disabled in this environment."
            )

        # 禁止在非 DEBUG 模式下執行資料更新
        if execute and not settings.DEBUG:
            raise CommandError(
                "Live Demo preparation requires DEBUG=True."
            )

        # 所有時間使用同一個基準
        base_time = timezone.now()

        live_specs = [
            data
            for data in DEMO_TICKETS
            if data["demo_id"] in DEMO_LIVE_TICKET_IDS
        ]

        if (
            len(live_specs) != 6
            or len(DEMO_LIVE_TICKET_IDS) != 6
            or set(DEMO_LIVE_TICKET_IDS) != set(EXPECTED_ROUTES)
        ):
            raise CommandError(
                "Live Demo specifications are inconsistent"
            )

        ready_tickets = []

        # 檢查與更新放在同一個 Transaction
        with transaction.atomic():

            # Step 1: 驗證全部六筆案件
            for data in live_specs:
                demo_id = data["demo_id"]
                marker = f"[{demo_id}]"

                matches = list(
                    SupportTicket.objects.filter(
                        message__startswith=marker
                    ).select_related("order")
                )

                if len(matches) != 1:
                    raise CommandError(
                        f"{demo_id}: expected one Ticket, "
                        f"found={len(matches)}"
                    )

                ticket = matches[0]

                if ticket.status != "open":
                    raise CommandError(
                        f"{demo_id}: unexpected status={ticket.status}"
                    )

                if ticket.triage_decisions.exists():
                    raise CommandError(
                        f"{demo_id}: Decision already exists"
                    )

                expected_message = (
                    f"{marker} {data['message']}"
                )

                if (
                    ticket.order.order_number
                    != data["order_number"]
                    or ticket.customer_id
                    != ticket.order.customer_id
                    or ticket.category
                    != data["category"]
                    or ticket.requested_action
                    != data["requested_action"]
                    or ticket.message
                    != expected_message
                ):
                    raise CommandError(
                        f"{demo_id}: Ticket data conflict"
                    )

                target_hours = data["waiting_hours"]

                if (
                    not isinstance(target_hours, (int, float))
                    or isinstance(target_hours, bool)
                    or target_hours < 0
                ):
                    raise CommandError(
                        f"{demo_id}: invalid waiting_hours"
                    )

                current_hours = (
                    base_time - ticket.created_at
                ).total_seconds() / 3600

                ready_tickets.append(
                    (demo_id, ticket, target_hours)
                )

                self.stdout.write(
                    f"{demo_id}: READY "
                    f"current={current_hours:.2f}h "
                    f"target={target_hours}h"
                )

            if len(ready_tickets) != 6:
                raise CommandError(
                    "Live Demo count mismatch"
                )

            # Step 2: Dry Run 不修改任何資料
            if not execute:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Live Demo Dry Run: "
                        f"ready={len(ready_tickets)}"
                    )
                )
                return

            # Step 3: 正式更新時間
            self.stdout.write(
                "Starting Live Demo time preparation..."
            )

            for demo_id, ticket, target_hours in ready_tickets:

                target_created_at = (
                    base_time - timedelta(hours=target_hours)
                )

                # auto_now_add 欄位使用受限制的 ORM update
                updated_count = SupportTicket.objects.filter(
                    pk=ticket.pk,
                    status="open",
                ).update(
                    created_at=target_created_at
                )

                if updated_count != 1:
                    raise CommandError(
                        f"{demo_id}: timestamp update failed"
                    )

                # 重新讀取更新後的 Ticket
                ticket.refresh_from_db()

                actual_hours = (
                    base_time - ticket.created_at
                ).total_seconds() / 3600

                if abs(actual_hours - target_hours) > 0.01:
                    raise CommandError(
                        f"{demo_id}: waiting time mismatch"
                    )

                # 確認仍然沒有 Decision
                if ticket.triage_decisions.exists():
                    raise CommandError(
                        f"{demo_id}: unexpected Decision"
                    )

                # Step 4: 重新預測正式 Workflow 分流
                predicted_route = predict_demo_route(ticket)

                expected_route = EXPECTED_ROUTES[demo_id]

                if predicted_route != expected_route:
                    raise CommandError(
                        f"{demo_id}: route mismatch "
                        f"expected={expected_route}, "
                        f"actual={predicted_route}"
                    )

                self.stdout.write(
                    f"{demo_id}: VERIFIED "
                    f"waiting={actual_hours:.2f}h "
                    f"route={predicted_route}"
                )

        # 成功離開 Transaction，才代表更新已提交
        self.stdout.write(
            self.style.SUCCESS(
                "Live Demo preparation completed: updated=6"
            )
        )
