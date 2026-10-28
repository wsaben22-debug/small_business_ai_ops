from django.db.models import Count

from .triage_service import get_risk_gate_result
from .models import(
    SupportTicket,
    TicketTriageDecision,
    TriageExecutionRecord,
)

def calculate_triage_metrics():
    total_decisions = TicketTriageDecision.objects.count()

    human_review_count = 0

    for decision in TicketTriageDecision.objects.select_related("risk_gate_record"):
        route, _ = get_risk_gate_result(decision)

        if route == "human_review":
            human_review_count += 1

    auto_handled_count = (
        TicketTriageDecision.objects
        .filter(
            execution_records__execution_status="success"
        )
        .distinct()
        .count()
    )

    if total_decisions == 0:
        human_review_rate = 0.0
        auto_handled_rate = 0.0
    else:
        human_review_rate = round(
            human_review_count / total_decisions * 100,
            2,
        )

        auto_handled_rate = round(
            auto_handled_count / total_decisions * 100,
            2,
        )

    return {
        "total_decisions": total_decisions,
        "human_review_count": human_review_count,
        "human_review_rate": human_review_rate,
        "auto_handled_count": auto_handled_count,
        "auto_handled_rate": auto_handled_rate,
    }


def calculate_ticket_category_stats():
    counts = dict(
        SupportTicket.objects.order_by().values("category")
        .annotate(count=Count("pk")).values_list("category", "count")
    )
    total = sum(counts.values())
    labels = dict(SupportTicket.CATEGORY_CHOICES)
    categories = []
    for category in dict.fromkeys([*labels, *counts]):
        count = counts.get(category, 0)
        categories.append({
            "category": category,
            "label": labels.get(category, category),
            "count": count,
            "percentage": round(count / total * 100, 2) if total else 0.0,
        })
    return {"total_tickets": total, "categories": categories}