from .triage_service import build_high_risk_support_package


def build_ai_input_snapshot(decision):

    package, error = build_high_risk_support_package(
        decision
    )

    if error is not None:
        return None, error

    ticket = decision.ticket

    snapshot = {
        "ticket_message": ticket.message,

        "category": package["category"],
        "requested_action": package["requested_action"],

        "order_status": package["order_status"],
        "order_total": str(package["order_total"]),

        "severity_level": package["severity"]["level"],
        "impact_level": package["impact"]["level"],
        "urgency_level": package["urgency"]["level"],

        "priority_level": package["priority"]["level"],

        "risk_gate_route": package["route"],
        "risk_gate_reason": package["route_reason"],

        "prior_ticket_count": (
            package["ticket_history"]["prior_ticket_count"]
        ),
    }

    return snapshot, None