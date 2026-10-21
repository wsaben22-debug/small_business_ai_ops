
from collections import Counter

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from myapp.models import (
    SupportTicket,
    TriageRiskGateRecord,
    TriageExecutionRecord,
)
from myapp.management.commands.seed_demo import (
    DEMO_TICKETS,
    DEMO_LIVE_TICKET_IDS,
)
from myapp.triage_service import (
    calculate_order_total,
    calculate_waiting_hours,
    assess_severity,
    assess_impact,
    assess_urgency,
    assess_priority,
    assess_human_requirement,
    run_triage_execution_workflow,
)


def predict_demo_route(ticket):
    severity = assess_severity(ticket.category)
    impact = assess_impact(
        calculate_order_total(ticket.order)
    )
    urgency = assess_urgency(
        calculate_waiting_hours(ticket.created_at)
    )

    _, priority_level = assess_priority(
        severity[1],
        impact[1],
        urgency[1],
    )

    requires_human, _ = assess_human_requirement(
        ticket.requested_action
    )

    if requires_human or priority_level == "high":
        return "human_review"

    return "auto_handle"


class Command(BaseCommand):
    help = "Preview or execute Demo Ticket Triage Workflow"

    def add_arguments(self, parser):
        parser.add_argument(
            "--execute",
            action="store_true",
            help="Execute the real Demo Triage Workflow",
        )

    def handle(self, *args, **options):
        execute = options["execute"]

        ready_tickets = []
        predicted_routes = Counter()

        already_count = 0
        live_count = 0

        # 正式執行時，檢查與寫入使用同一個交易。
        with transaction.atomic():

            # Step 1：先檢查完整 40 筆 Demo Ticket
            if len(DEMO_TICKETS) != 40:
                raise CommandError(
                    "Demo Ticket specification count is not 40"
                )

            for ticket_data in DEMO_TICKETS:
                demo_id = ticket_data["demo_id"]
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

                expected_message = (
                    f"{marker} {ticket_data['message']}"
                )

                # 驗證資料沒有被意外修改
                if (
                    ticket.order.order_number
                    != ticket_data["order_number"]
                    or ticket.customer_id
                    != ticket.order.customer_id
                    or ticket.category
                    != ticket_data["category"]
                    or ticket.requested_action
                    != ticket_data["requested_action"]
                    or ticket.message != expected_message
                ):
                    raise CommandError(
                        f"{demo_id}: Ticket data conflict"
                    )

                # Step 2：保留六筆現場展示案件
                if demo_id in DEMO_LIVE_TICKET_IDS:
                    if ticket.triage_decisions.exists():
                        raise CommandError(
                            f"{demo_id}: LIVE Ticket already triaged"
                        )

                    if ticket.status != "open":
                        raise CommandError(
                            f"{demo_id}: LIVE status={ticket.status}"
                        )

                    live_count += 1

                    self.stdout.write(
                        f"{demo_id}: LIVE - skipped"
                    )
                    continue

                # Step 3：已有 Decision 的案件不重複執行
                if ticket.triage_decisions.exists():
                    already_count += 1

                    self.stdout.write(
                        f"{demo_id}: ALREADY TRIAGED - skipped"
                    )
                    continue

                # Step 4：未評估案件必須是 open
                if ticket.status != "open":
                    raise CommandError(
                        f"{demo_id}: unexpected status={ticket.status}"
                    )

                predicted_route = predict_demo_route(ticket)
                predicted_routes[predicted_route] += 1

                ready_tickets.append(
                    (demo_id, ticket)
                )

                self.stdout.write(
                    f"{demo_id}: READY - "
                    f"predicted={predicted_route}"
                )

            ready_count = len(ready_tickets)

            if ready_count + already_count + live_count != 40:
                raise CommandError(
                    "Demo Triage count mismatch"
                )

            # Step 5：Dry Run 到此結束
            if not execute:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Dry Run: ready={ready_count}, "
                        f"already_triaged={already_count}, "
                        f"live_skipped={live_count}"
                    )
                )

                self.stdout.write(
                    f"Predicted Routes: {dict(predicted_routes)}"
                )

                return

            # Step 6：正式執行 Workflow
            self.stdout.write(
                "Starting Demo Triage execution..."
            )

            executed_routes = Counter()
            executed_count = 0

            for demo_id, ticket in ready_tickets:

                # 執行前再次確認沒有 Decision
                if ticket.triage_decisions.exists():
                    raise CommandError(
                        f"{demo_id}: Decision already exists"
                    )

                decision, route, action_code, reason = (
                    run_triage_execution_workflow(
                        ticket,
                        "manual",
                    )
                )

                if decision is None:
                    raise CommandError(
                        f"{demo_id}: Workflow failed: {reason}"
                    )

                # 驗證 Decision 與 Ticket 的關聯
                if decision.ticket_id != ticket.id:
                    raise CommandError(
                        f"{demo_id}: Decision Ticket mismatch"
                    )

                # 驗證 Decision 已保存
                if ticket.triage_decisions.count() != 1:
                    raise CommandError(
                        f"{demo_id}: Decision count mismatch"
                    )

                # 驗證 Risk Gate Record
                gate_records = TriageRiskGateRecord.objects.filter(
                    decision=decision
                )

                if gate_records.count() != 1:
                    raise CommandError(
                        f"{demo_id}: Risk Gate Record missing"
                    )

                saved_route = gate_records.first().route

                if saved_route != route:
                    raise CommandError(
                        f"{demo_id}: Risk Gate route mismatch"
                    )

                if route not in ("auto_handle", "human_review"):
                    raise CommandError(
                        f"{demo_id}: unexpected route={route}"
                    )

                # 驗證低風險執行紀錄
                if route == "auto_handle":
                    execution_records = (
                        TriageExecutionRecord.objects.filter(
                            decision=decision
                        )
                    )

                    if (
                        execution_records.count() != 1
                        or action_code != "info_triage_prepared"
                    ):
                        raise CommandError(
                            f"{demo_id}: Execution Record mismatch"
                        )

                    record = execution_records.first()

                    if (
                        record.execution_status != "success"
                        or record.ticket_status_after != "in_progress"
                    ):
                        raise CommandError(
                            f"{demo_id}: Execution status mismatch"
                        )

                    ticket.refresh_from_db()

                    if ticket.status != "in_progress":
                        raise CommandError(
                            f"{demo_id}: Ticket status not updated"
                        )

                # Human Review 不應直接執行自動動作
                else:
                    if action_code is not None:
                        raise CommandError(
                            f"{demo_id}: unexpected action"
                        )

                    if TriageExecutionRecord.objects.filter(
                        decision=decision
                    ).exists():
                        raise CommandError(
                            f"{demo_id}: unexpected Execution Record"
                        )

                    ticket.refresh_from_db()

                    if ticket.status != "open":
                        raise CommandError(
                            f"{demo_id}: Human Review status changed"
                        )

                executed_routes[route] += 1
                executed_count += 1

                self.stdout.write(
                    self.style.SUCCESS(
                        f"{demo_id}: SUCCESS - {route}"
                    )
                )

            if executed_count != ready_count:
                raise CommandError(
                    "Executed count does not match READY count"
                )

        # 離開 transaction.atomic() 後才代表交易已提交
        self.stdout.write(
            self.style.SUCCESS(
                f"Demo Triage Completed: "
                f"executed={executed_count}, "
                f"already_triaged={already_count}, "
                f"live_skipped={live_count}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Executed Routes: {dict(executed_routes)}"
            )
        )
