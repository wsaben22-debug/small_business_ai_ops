from django.utils import timezone
from .models import (
    Customer,
    Order,
    OrderItem,
    Product,
    SupportTicket,
    TicketTriageDecision,
    TriageExecutionRecord,
)
from django.db.models import Q

def assess_severity(category):

    if category == 'damaged':

        severity_level = 'high'

        severity_score = 3

        severity_reason = 'category=damaged maps to high severity'

        return severity_level, severity_score, severity_reason

    elif category == 'missing':

        severity_level = 'high'

        severity_score = 3

        severity_reason = 'category=missing maps to high severity'

        return severity_level, severity_score, severity_reason

    elif category == 'delivery':

        severity_level = 'medium'

        severity_score = 2

        severity_reason = 'category=delivery maps to medium severity'

        return severity_level, severity_score, severity_reason

    elif category == 'refund':

        severity_level = 'medium'

        severity_score = 2

        severity_reason = 'category=refund maps to medium severity'

        return severity_level, severity_score, severity_reason

    elif category == 'other':

        severity_level = 'low'

        severity_score = 1

        severity_reason = 'category=other maps to low severity'

        return severity_level, severity_score, severity_reason

def assess_impact(order_total):

    if order_total < 3000:

        impact_level = 'low'

        impact_score = 1

        impact_reason = f'order_total={order_total} is below 3000, so impact is low'

        return impact_level, impact_score, impact_reason

    elif 3000 <= order_total < 8000:

        impact_level = 'medium'

        impact_score = 2

        impact_reason = f'order_total={order_total} is between 3000 and 8000, so impact is medium'

        return impact_level, impact_score, impact_reason

    elif order_total >= 8000:

        impact_level = 'high'

        impact_score = 3

        impact_reason = f'order_total={order_total} is at least 8000, so impact is high'

        return impact_level, impact_score, impact_reason

def assess_urgency(waiting_hours):

    if waiting_hours < 24:

        urgency_level = 'low'

        urgency_score = 1

        urgency_reason = f'waiting_hours={waiting_hours} is below 24, so urgency is low'

        return urgency_level, urgency_score, urgency_reason

    elif 24 <= waiting_hours < 72:

        urgency_level = 'medium'

        urgency_score = 2

        urgency_reason = f'waiting_hours={waiting_hours} is between 24 and 72, so urgency is medium'

        return urgency_level, urgency_score, urgency_reason

    elif waiting_hours >= 72:

        urgency_level = 'high'

        urgency_score = 3

        urgency_reason = f'waiting_hours={waiting_hours} is at least 72, so urgency is high'

        return urgency_level, urgency_score, urgency_reason

def assess_priority(severity_score, impact_score, urgency_score):

    priority_score = severity_score + impact_score + urgency_score

    if 3 <= priority_score <= 4:

        priority_level = 'low'

    elif 5 <= priority_score <= 6:

        priority_level = 'medium'

    elif 7 <= priority_score <= 9:

        priority_level = 'high'

    return priority_score, priority_level

def assess_human_requirement(requested_action):

    if requested_action == 'info':

        requires_human = False

        human_reason = 'requested_action=info can proceed without human review by default'

        return requires_human, human_reason

    elif requested_action in ('exchange', 'refund', 'compensation', 'other'):

        requires_human = True

        human_reason = f'requested_action={requested_action} requires human review by default'

        return requires_human,human_reason

    else:
        
        requires_human = True

        human_reason = f'unknown requested_action={requested_action}, human review required'

        return requires_human, human_reason

def check_eligibility(status):

    if status in ('open', 'in_progress'):

        is_eligible = True

        eligibility_reason = f'status={status} is eligible for triage'

        return is_eligible, eligibility_reason

    elif status in ('resolved', 'closed'):

        is_eligible = False

        eligibility_reason = f'status={status} is not eligible for triage'

        return is_eligible, eligibility_reason

    else:

        is_eligible = False

        eligibility_reason = f'unknown status={status}, triage is not allowed'

        return is_eligible, eligibility_reason

def calculate_order_total(order):

    order_items = order.orderitem_set.all()

    order_total = 0

    for item in order_items:

        order_total += item.quantity * item.unit_price

    return order_total 

def calculate_waiting_hours(created_at):

    now = timezone.now()

    elapsed = now - created_at

    waiting_hours = elapsed.total_seconds() / 3600

    return waiting_hours

def run_triage(ticket, trigger_type):

    is_eligible, eligibility_reason = check_eligibility(ticket.status)

    if not is_eligible:

        return None, eligibility_reason 

    order_total = calculate_order_total(ticket.order)

    waiting_hours = calculate_waiting_hours(ticket.created_at)

    severity_level, severity_score, severity_reason = assess_severity(ticket.category)

    impact_level, impact_score, impact_reason = assess_impact(order_total)

    urgency_level, urgency_score, urgency_reason = assess_urgency(waiting_hours)

    priority_score, priority_level = assess_priority(severity_score, impact_score, urgency_score)

    requires_human, human_reason = assess_human_requirement(ticket.requested_action)

    decision = TicketTriageDecision(
        ticket=ticket,

        category_snapshot=ticket.category,

        requested_action_snapshot=ticket.requested_action,

        order_status_snapshot=ticket.order.status,

        order_total_snapshot=order_total,

        waiting_hours_snapshot=waiting_hours,

        severity_level=severity_level,

        severity_score=severity_score,

        severity_reason=severity_reason,

        impact_level=impact_level,

        impact_score=impact_score,

        impact_reason=impact_reason,

        urgency_level=urgency_level,

        urgency_score=urgency_score,

        urgency_reason=urgency_reason,

        priority_score=priority_score,

        priority_level=priority_level,

        requires_human=requires_human,

        human_reason=human_reason,

        rule_version="v1",

        trigger_type=trigger_type,
    )

    decision.full_clean()

    decision.save()

    return decision, None

def evaluate_risk_gate(decision):
    
    if decision.requires_human:
        return(
            "human_review",
            decision.human_reason,
        )
    
    if decision.priority_level == "high":
        return(
            "human_review",
            "high priority requires human review",
        )

    return(
        "auto_handle",
        "risk gate passed for automatic handling",
    )

def run_triage_workflow(ticket, trigger_type):
    decision, error = run_triage(ticket, trigger_type)

    if decision is None:
        return None,None, error

    route,reason = evaluate_risk_gate(decision)
 
    return decision, route, reason

def execute_low_risk_action(decision):
    route, route_reason = evaluate_risk_gate(decision)

    if route != "auto_handle":
        return(
            None,
            f"automation blocked by risk gate: {route_reason}",
        )
    
    if decision.requested_action_snapshot != "info":
        return(
            None,
            f"requested_action={decision.requested_action_snapshot}"
            "is not supported for low-risk automation",
        )
    
    ticket = decision.ticket

    if ticket.status != "open":
        
        action_reason = (
            f"ticket status={ticket.status} is not supported "
            "for low-risk automation"
        )

        TriageExecutionRecord.objects.create(
            decision=decision,
            action_code="info_triage_prepared",
            execution_status="skipped",
            reason=action_reason,
            ticket_status_before=ticket.status,
            ticket_status_after=ticket.status,
        )

        return (
            None,
            action_reason,
        )

    ticket_status_before = ticket.status
    ticket.status = "in_progress"
    ticket.save(update_fields=["status"])

    action_code = "info_triage_prepared"
    action_reason = "low-risk info ticket moved to in_progress"

    TriageExecutionRecord.objects.create(
        decision=decision,
        action_code=action_code,
        execution_status="success",
        reason=action_reason,
        ticket_status_before=ticket_status_before,
        ticket_status_after=ticket.status,
    )

    return(
        action_code,
        action_reason,
    )

def run_triage_execution_workflow(ticket, trigger_type):
    decision, route, route_reason = run_triage_workflow(
        ticket,
        trigger_type,
    )

    if decision is None:
        return None, None, None, route_reason

    if route == "human_review":
        return(
            decision,
            route,
            None,
            route_reason,
        )

    action_code, action_reason = execute_low_risk_action(decision)

    return(
        decision,
        route,
        action_code,
        action_reason,
    )

def build_high_risk_recommendation(decision):
    route, route_reason = evaluate_risk_gate(decision)

    if route != "human_review":
        return None, "decision is not routed to human review"

    options = [
        "review_requested_action",
        "request_more_information",
        "escalate_high_priority_case",
    ]

    if decision.priority_level == "high":
        return {
            "options": options,
            "recommended_action": "escalate_high_priority_case",
            "recommendation_reason": (
                "high priority case requires escalation"
            ),
        }, None

    if decision.requires_human:
        return {
            "options": options,
            "recommended_action": "review_requested_action",
            "recommendation_reason": decision.human_reason,
        }, None

    return None, "unable to determine human review recommendation"

def build_high_risk_support_package(decision):
    route, route_reason = evaluate_risk_gate(decision)

    if route != "human_review":
        return None, "decision is not routed to human review"

    recommendation, recommendation_error = (
        build_high_risk_recommendation(decision)
    )

    if recommendation_error is not None:
        return None, recommendation_error

    ticket = decision.ticket

    ticket = decision.ticket
    order = ticket.order

    customer = ticket.customer

    if customer is None and order is not None:
        customer = order.customer

    history_tickets = SupportTicket.objects.none()

    if customer is not None:
        history_tickets = (
            SupportTicket.objects
            .filter(
                Q(customer=customer) | Q(order__customer=customer),
                created_at__lte=decision.created_at,
            )
            .exclude(id=ticket.id)
            .distinct()
        )

    prior_ticket_count = history_tickets.count()

    same_category_ticket_count = history_tickets.filter(
        category=decision.category_snapshot).count()

    recent_tickets = [
        {
            "ticket_id": history_ticket.id,
            "category": history_ticket.category,
            "requested_action": history_ticket.requested_action,
            "status": history_ticket.status,
        }
        for history_ticket in history_tickets.order_by("-created_at")[:5]
    ]

    package = {
        "ticket_id": ticket.id,
        "route": route,
        "route_reason": route_reason,

        "category": decision.category_snapshot,
        "requested_action": decision.requested_action_snapshot,
        "order_status": decision.order_status_snapshot,
        "order_total": decision.order_total_snapshot,
        "waiting_hours": decision.waiting_hours_snapshot,

        "severity": {
            "level": decision.severity_level,
            "score": decision.severity_score,
            "reason": decision.severity_reason,
        },

        "impact": {
            "level": decision.impact_level,
            "score": decision.impact_score,
            "reason": decision.impact_reason,
        },

        "urgency": {
            "level": decision.urgency_level,
            "score": decision.urgency_score,
            "reason": decision.urgency_reason,
        },

        "priority": {
            "level": decision.priority_level,
            "score": decision.priority_score,
        },

        "human_requirement": {
            "required": decision.requires_human,
            "reason": decision.human_reason,
        },

        "decision_support": {
            "options": recommendation["options"],
            "recommended_action": recommendation["recommended_action"],
            "recommendation_reason": recommendation["recommendation_reason"],
        },

        "rule_version": decision.rule_version,
        "decision_created_at": decision.created_at,

        "customer": {
            "id": customer.id if customer else None,
            "name": customer.name if customer else None,
            "email": customer.email if customer else None,
            "phone": customer.phone if customer else None,
        },

        "order": {
            "id": order.id if order else None,
            "order_number": order.order_number if order else None,
            "status": order.status if order else None,
            "shipping_address": order.shipping_address if order else None,
        },

        "ticket_history": {
            "prior_ticket_count": prior_ticket_count,
            "same_category_ticket_count": same_category_ticket_count,
            "recent_tickets": recent_tickets,
        },
    }

    return package, None

