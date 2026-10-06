from .models import (
    SupportTicket,
    TriageExecutionRecord,
)
from .triage_service import get_risk_gate_result

def get_high_risk_queue():
    tickets = SupportTicket.objects.filter(
        status__in=["open", "in_progress"]
    )

    high_risk_queue = []

    for ticket in tickets:
        latest_decision = (
            ticket.triage_decisions
            .order_by("-created_at")
            .first()
        )

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