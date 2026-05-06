from math import ceil

from app.db.models import TicketGroupModel, TicketHistoryEventModel, TicketModel, UserModel
from app.schemas.api import (
    Actor,
    ManagerAnalyticsSummary,
    MyTicketsListResponse,
    PaginationMeta,
    RelatedTicket,
    StatusCount,
    Ticket,
    TicketAuthorSummary,
    TicketGroup,
    TicketGroupListResponse,
    TicketHistoryEvent,
    TopRepeatedProblem,
    User,
)
from app.services.grouping import build_excerpt


def to_user(user: UserModel) -> User:
    return User(id=user.id, fullName=user.full_name, initials=user.initials, role=user.role)


def to_history_event(event: TicketHistoryEventModel) -> TicketHistoryEvent:
    return TicketHistoryEvent(
        id=event.id,
        type=event.type,
        label=event.label,
        fromStatus=event.from_status,
        toStatus=event.to_status,
        createdAt=event.created_at,
        actor=Actor(type=event.actor_type, id=event.actor_id, displayName=event.actor_display_name),
    )


def to_ticket(ticket: TicketModel) -> Ticket:
    return Ticket(
        id=ticket.id,
        number=ticket.number,
        title=ticket.title,
        description=ticket.description,
        originalDescription=ticket.original_description,
        aiEnhanced=ticket.ai_enhanced,
        status=ticket.status,
        managerComment=ticket.manager_comment,
        author=to_user(ticket.author),
        groupId=ticket.group_id,
        createdAt=ticket.created_at,
        updatedAt=ticket.updated_at,
        resolvedAt=ticket.resolved_at,
        history=[to_history_event(event) for event in ticket.history_events],
    )


def to_related_ticket(ticket: TicketModel) -> RelatedTicket:
    return RelatedTicket(
        ticketId=ticket.id,
        authorSummary=TicketAuthorSummary(fullName=ticket.author.full_name, initials=ticket.author.initials),
        descriptionExcerpt=build_excerpt(ticket.description),
        createdAt=ticket.created_at,
        aiEnhanced=ticket.ai_enhanced,
        status=ticket.status,
    )


def to_ticket_group(group: TicketGroupModel) -> TicketGroup:
    ordered_tickets = sorted(group.tickets, key=lambda ticket: ticket.created_at, reverse=True)
    return TicketGroup(
        id=group.id,
        title=group.title,
        aiSummary=group.ai_summary,
        status=group.status,
        ticketCount=len(group.tickets),
        lastTicketCreatedAt=group.last_ticket_created_at,
        managerComment=group.manager_comment,
        relatedTickets=[to_related_ticket(ticket) for ticket in ordered_tickets],
        createdAt=group.created_at,
        updatedAt=group.updated_at,
    )


def paginate(total_items: int, page: int, page_size: int) -> PaginationMeta:
    total_pages = ceil(total_items / page_size) if total_items else 0
    return PaginationMeta(
        page=page,
        pageSize=page_size,
        totalItems=total_items,
        totalPages=total_pages,
        hasNextPage=page < total_pages,
        hasPreviousPage=page > 1 and total_pages > 0,
    )


def to_tickets_list_response(tickets: list[TicketModel], total_items: int, page: int, page_size: int) -> MyTicketsListResponse:
    return MyTicketsListResponse(items=[to_ticket(ticket) for ticket in tickets], meta=paginate(total_items, page, page_size))


def to_group_list_response(groups: list[TicketGroupModel], total_items: int, page: int, page_size: int) -> TicketGroupListResponse:
    return TicketGroupListResponse(items=[to_ticket_group(group) for group in groups], meta=paginate(total_items, page, page_size))


def to_status_count(values: dict[str, int]) -> StatusCount:
    return StatusCount(
        open=values.get("open", 0),
        in_review=values.get("in_review", 0),
        resolved=values.get("resolved", 0),
    )


def to_analytics_summary(groups_by_status: dict[str, int], tickets_by_status: dict[str, int], groups: list[TicketGroupModel]) -> ManagerAnalyticsSummary:
    top_problems = sorted(groups, key=lambda group: (len(group.tickets), group.last_ticket_created_at), reverse=True)[:5]
    return ManagerAnalyticsSummary(
        groupsByStatus=to_status_count(groups_by_status),
        ticketsByStatus=to_status_count(tickets_by_status),
        topRepeatedProblems=[
            TopRepeatedProblem(
                groupId=group.id,
                title=group.title,
                ticketCount=len(group.tickets),
                status=group.status,
                lastTicketCreatedAt=group.last_ticket_created_at,
            )
            for group in top_problems
        ],
    )
