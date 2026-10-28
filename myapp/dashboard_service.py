from django.db.models import Prefetch

from .models import (
    SupportTicket,
    TicketTriageDecision,
    TriageExecutionRecord,
)
from .triage_service import get_risk_gate_result

PENDING_SORT_OPTIONS = (
    ("priority_level", "優先等級"),
    ("priority_score", "分數"),
    ("category", "問題分類"),
    ("requested_action", "請求動作"),
    ("ticket_id", "Ticket ID"),
)


def sort_pending_queue(queue, sort="priority_level", direction="desc"):
    if sort not in dict(PENDING_SORT_OPTIONS) or direction not in ("asc", "desc"):
        sort, direction = "priority_level", "desc"

    ranks = {
        "priority_level": {"low": 1, "medium": 2, "high": 3},
        "category": {
            "delivery": 1, "damaged": 2, "missing": 3, "refund": 4, "other": 5,
        },
        "requested_action": {
            "info": 1, "exchange": 2, "refund": 3, "compensation": 4, "other": 5,
        },
    }
    sign = 1 if direction == "asc" else -1

    def sort_key(item):
        value = ranks[sort].get(item[sort]) if sort in ranks else item[sort]
        primary = (value is None, sign * (value or 0))
        if sort == "priority_level":
            return (*primary, -item["priority_score"], item["ticket_id"])
        return (*primary, item["ticket_id"])

    return sorted(queue, key=sort_key), sort, direction


def get_high_risk_queue(tickets=None):
    if tickets is None:
        tickets = SupportTicket.objects.all()
    tickets = tickets.filter(
        status__in=["open", "in_progress"]
    ).prefetch_related(
        Prefetch(
            "triage_decisions",
            queryset=TicketTriageDecision.objects.select_related(
                "risk_gate_record", "human_review_record"
            ).order_by("-created_at")[:1],
            to_attr="latest_decisions",
        )
    )

    high_risk_queue = []

    for ticket in tickets:
        latest_decision = next(iter(ticket.latest_decisions), None)

        if latest_decision is None:
            continue

        if hasattr(latest_decision, "human_review_record"):
            continue

        route, _ = get_risk_gate_result(latest_decision)

        if route == "human_review":
            high_risk_queue.append(
                {
                    "ticket_id": ticket.id,
                    "category": latest_decision.category_snapshot,
                    "requested_action": (
                        latest_decision.requested_action_snapshot
                    ),
                    "priority_level": latest_decision.priority_level,
                    "priority_score": latest_decision.priority_score,
                    "has_persisted_gate": hasattr(latest_decision, "risk_gate_record"),
                    "reason": (
                        latest_decision.human_reason
                        if latest_decision.requires_human
                        else "high priority requires human review"
                    ),
                }
            )
    return high_risk_queue

def get_recent_execution_history(limit=5):
    records = (
        TriageExecutionRecord.objects
        .select_related(
            "decision",
            "decision__ticket",
        )
        .order_by("-created_at")[:limit]
    )

    history = []

    for record in records:
        history.append(
            {
                "ticket_id": record.decision.ticket.id,
                "action_code": record.action_code,
                "execution_status": record.execution_status,
                "status_before": record.ticket_status_before,
                "status_after": record.ticket_status_after,
                "reason": record.reason,
                "created_at": record.created_at,
            }
        )

    return history