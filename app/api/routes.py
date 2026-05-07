from datetime import UTC, datetime
from uuid import uuid4

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.core.auth import (
    AuthenticatedUser,
    create_access_token,
    get_current_user,
    require_role,
    verify_password,
)
from app.db.models import TicketGroupModel, TicketHistoryEventModel, TicketModel, UserModel
from app.db.session import get_db
from app.schemas.api import (
    AuthTokenResponse,
    CreateTicketRequest,
    EnhanceTicketDescriptionRequest,
    EnhanceTicketDescriptionResponse,
    LoginRequest,
    ManagerAnalyticsSummary,
    MyTicketsListResponse,
    SaveTicketGroupCommentRequest,
    Ticket,
    TicketGroup,
    TicketGroupListResponse,
    TicketStatus,
    UpdateTicketGroupStatusRequest,
    User,
    UserRole,
)
from app.services.ai import get_ai_service
from app.services.grouping import classify_ticket_fallback
from app.services.serializers import to_analytics_summary, to_group_list_response, to_ticket, to_ticket_group, to_tickets_list_response, to_user


router = APIRouter()


def utcnow() -> datetime:
    return datetime.now(UTC)


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def parse_statuses(raw_statuses: str | None) -> list[str] | None:
    if raw_statuses is None:
        return None
    values = [value.strip() for value in raw_statuses.split(",") if value.strip()]
    valid = {status.value for status in TicketStatus}
    if not values or any(value not in valid for value in values):
        raise HTTPException(status_code=400)
    return values


def next_ticket_number(db: Session) -> str:
    numbers = db.query(TicketModel.number).all()
    if not numbers:
        return "PT-1001"
    current = max(int(number.split("-")[1]) for number, in numbers)
    return f"PT-{current + 1}"


def add_history_event(
    *,
    db: Session,
    ticket: TicketModel,
    event_type: str,
    label: str,
    actor_type: str,
    actor_display_name: str,
    actor_id: str | None = None,
    from_status: str | None = None,
    to_status: str | None = None,
    created_at: datetime | None = None,
) -> None:
    db.add(
        TicketHistoryEventModel(
            id=new_id("the"),
            ticket=ticket,
            type=event_type,
            label=label,
            from_status=from_status,
            to_status=to_status,
            actor_type=actor_type,
            actor_id=actor_id,
            actor_display_name=actor_display_name,
            created_at=created_at or utcnow(),
        )
    )


def get_user_model(db: Session, user: AuthenticatedUser) -> UserModel:
    return db.query(UserModel).filter(UserModel.id == user.id).one()


def get_group_or_404(db: Session, group_id: str) -> TicketGroupModel:
    group = (
        db.query(TicketGroupModel)
        .options(joinedload(TicketGroupModel.tickets).joinedload(TicketModel.author))
        .filter(TicketGroupModel.id == group_id)
        .one_or_none()
    )
    if not group:
        raise HTTPException(status_code=404)
    return group


def get_employee_ticket_or_404(db: Session, ticket_id: str, user_id: str) -> TicketModel:
    ticket = (
        db.query(TicketModel)
        .options(joinedload(TicketModel.author), joinedload(TicketModel.history_events))
        .filter(TicketModel.id == ticket_id, TicketModel.author_id == user_id)
        .one_or_none()
    )
    if not ticket:
        raise HTTPException(status_code=404)
    return ticket


@router.get("/me", response_model=User)
def get_me(current_user: AuthenticatedUser = Depends(get_current_user), db: Session = Depends(get_db)) -> User:
    return to_user(get_user_model(db, current_user))


@router.post("/auth/login", response_model=AuthTokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)) -> AuthTokenResponse:
    user = db.query(UserModel).filter(UserModel.email == payload.email.lower()).one_or_none()
    if not user or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401)
    access_token, expires_in = create_access_token(user)
    return AuthTokenResponse(
        accessToken=access_token,
        tokenType="Bearer",
        expiresIn=expires_in,
        user=to_user(user),
    )


def _issue_dev_token(email: str, db: Session) -> AuthTokenResponse:
    user = db.query(UserModel).filter(UserModel.email == email).one_or_none()
    if not user:
        raise HTTPException(status_code=404)
    access_token, expires_in = create_access_token(user)
    return AuthTokenResponse(
        accessToken=access_token,
        tokenType="Bearer",
        expiresIn=expires_in,
        user=to_user(user),
    )


@router.post("/auth/dev/employee-token", response_model=AuthTokenResponse)
def get_dev_employee_token(db: Session = Depends(get_db)) -> AuthTokenResponse:
    return _issue_dev_token("employee@pulse.local", db)


@router.post("/auth/dev/manager-token", response_model=AuthTokenResponse)
def get_dev_manager_token(db: Session = Depends(get_db)) -> AuthTokenResponse:
    return _issue_dev_token("manager@pulse.local", db)


@router.post("/ai/enhance-ticket-description", response_model=EnhanceTicketDescriptionResponse)
def enhance_ticket_description(
    payload: EnhanceTicketDescriptionRequest,
    _: AuthenticatedUser = Depends(require_role(UserRole.employee)),
) -> EnhanceTicketDescriptionResponse:
    display_prefix, enhanced_text = get_ai_service().enhance_ticket_description(payload.originalText)
    return EnhanceTicketDescriptionResponse(
        originalText=payload.originalText,
        enhancedText=enhanced_text,
        aiEnhanced=True,
        displayPrefix=display_prefix,
    )


@router.post("/tickets", response_model=Ticket, status_code=201)
def create_ticket(
    payload: CreateTicketRequest,
    current_user: AuthenticatedUser = Depends(require_role(UserRole.employee)),
    db: Session = Depends(get_db),
) -> Ticket:
    now = utcnow()
    author = get_user_model(db, current_user)
    generated_title = get_ai_service().generate_ticket_title(payload.description)
    grouping_text = payload.description
    template = get_ai_service().classify_ticket(grouping_text)
    fallback_template = classify_ticket_fallback(grouping_text)
    candidate_keys = {template.key, fallback_template.key}
    candidate_title_values = {template.title, fallback_template.title}
    candidate_titles = {template.title.lower(), fallback_template.title.lower()}

    group = (
        db.query(TicketGroupModel)
        .options(joinedload(TicketGroupModel.tickets).joinedload(TicketModel.author))
        .filter(
            or_(
                TicketGroupModel.classifier_key.in_(candidate_keys),
                TicketGroupModel.title.in_(candidate_title_values),
                func.lower(TicketGroupModel.title).in_(candidate_titles),
            )
        )
        .one_or_none()
    )
    if not group:
        group = TicketGroupModel(
            id=new_id("grp"),
            classifier_key=template.key,
            title=template.title,
            ai_summary=template.summary,
            status=TicketStatus.open.value,
            manager_comment=None,
            last_ticket_created_at=now,
            created_at=now,
            updated_at=now,
        )
        db.add(group)
        db.flush()

    ticket = TicketModel(
        id=new_id("tkt"),
        number=next_ticket_number(db),
        title=generated_title,
        description=payload.description,
        original_description=payload.originalDescription,
        ai_enhanced=payload.aiEnhanced,
        status=group.status,
        manager_comment=group.manager_comment,
        author_id=author.id,
        group_id=group.id,
        created_at=now,
        updated_at=now,
        resolved_at=now if group.status == TicketStatus.resolved.value else None,
    )
    db.add(ticket)
    db.flush()

    add_history_event(
        db=db,
        ticket=ticket,
        event_type="ticket_created",
        label="Ticket created",
        actor_type="user",
        actor_id=author.id,
        actor_display_name=author.full_name,
        to_status=ticket.status,
        created_at=now,
    )
    add_history_event(
        db=db,
        ticket=ticket,
        event_type="group_assigned",
        label="Ticket assigned to AI group",
        actor_type="ai",
        actor_display_name="AI Grouper",
        created_at=now,
    )
    group.last_ticket_created_at = now
    group.updated_at = now
    db.commit()

    created = (
        db.query(TicketModel)
        .options(joinedload(TicketModel.author), joinedload(TicketModel.history_events))
        .filter(TicketModel.id == ticket.id)
        .one()
    )
    return to_ticket(created)


@router.get("/tickets/my", response_model=MyTicketsListResponse)
def list_my_tickets(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    status: str | None = Query(default=None),
    query: str | None = Query(default=None, min_length=1, max_length=200),
    current_user: AuthenticatedUser = Depends(require_role(UserRole.employee)),
    db: Session = Depends(get_db),
) -> MyTicketsListResponse:
    statuses = parse_statuses(status)
    filters = [TicketModel.author_id == current_user.id]
    if statuses:
        filters.append(TicketModel.status.in_(statuses))
    if query:
        like = f"%{query.strip()}%"
        filters.append(
            or_(
                TicketModel.title.ilike(like),
                TicketModel.description.ilike(like),
                TicketModel.manager_comment.ilike(like),
            )
        )

    base_query = (
        db.query(TicketModel)
        .options(joinedload(TicketModel.author), joinedload(TicketModel.history_events))
        .filter(*filters)
    )
    total_items = base_query.count()
    items = (
        base_query.order_by(TicketModel.updated_at.desc(), TicketModel.created_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return to_tickets_list_response(items, total_items, page, page_size)


@router.get("/tickets/my/{ticketId}", response_model=Ticket)
def get_my_ticket_by_id(
    ticketId: str,
    current_user: AuthenticatedUser = Depends(require_role(UserRole.employee)),
    db: Session = Depends(get_db),
) -> Ticket:
    return to_ticket(get_employee_ticket_or_404(db, ticketId, current_user.id))


@router.get("/manager/ticket-groups", response_model=TicketGroupListResponse)
def list_manager_ticket_groups(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, alias="pageSize", ge=1, le=100),
    status: str | None = Query(default=None),
    query: str | None = Query(default=None, min_length=1, max_length=200),
    _: AuthenticatedUser = Depends(require_role(UserRole.manager)),
    db: Session = Depends(get_db),
) -> TicketGroupListResponse:
    statuses = parse_statuses(status)
    filters = []
    if statuses:
        filters.append(TicketGroupModel.status.in_(statuses))
    if query:
        like = f"%{query.strip()}%"
        filters.append(
            or_(
                TicketGroupModel.title.ilike(like),
                TicketGroupModel.ai_summary.ilike(like),
                TicketGroupModel.manager_comment.ilike(like),
                TicketGroupModel.tickets.any(TicketModel.description.ilike(like)),
                TicketGroupModel.tickets.any(TicketModel.title.ilike(like)),
            )
        )

    base_query = (
        db.query(TicketGroupModel)
        .options(joinedload(TicketGroupModel.tickets).joinedload(TicketModel.author))
        .filter(*filters)
    )
    total_items = base_query.count()
    items = (
        base_query.order_by(
            TicketGroupModel.status == TicketStatus.resolved.value,
            TicketGroupModel.last_ticket_created_at.desc(),
            TicketGroupModel.updated_at.desc(),
        )
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return to_group_list_response(items, total_items, page, page_size)


@router.get("/manager/ticket-groups/{groupId}", response_model=TicketGroup)
def get_manager_ticket_group_by_id(
    groupId: str,
    _: AuthenticatedUser = Depends(require_role(UserRole.manager)),
    db: Session = Depends(get_db),
) -> TicketGroup:
    return to_ticket_group(get_group_or_404(db, groupId))


@router.patch("/manager/ticket-groups/{groupId}/status", response_model=TicketGroup)
def update_manager_ticket_group_status(
    groupId: str,
    payload: UpdateTicketGroupStatusRequest,
    current_user: AuthenticatedUser = Depends(require_role(UserRole.manager)),
    db: Session = Depends(get_db),
) -> TicketGroup:
    now = utcnow()
    group = get_group_or_404(db, groupId)
    previous_status = group.status

    group.status = payload.status.value
    group.updated_at = now
    for ticket in group.tickets:
        old_status = ticket.status
        ticket.status = payload.status.value
        ticket.manager_comment = group.manager_comment
        ticket.updated_at = now
        ticket.resolved_at = now if payload.status == TicketStatus.resolved else None
        if old_status != payload.status.value:
            add_history_event(
                db=db,
                ticket=ticket,
                event_type="group_status_changed",
                label="Group status changed by manager",
                actor_type="user",
                actor_id=current_user.id,
                actor_display_name=current_user.full_name,
                from_status=old_status,
                to_status=payload.status.value,
                created_at=now,
            )

    if previous_status != payload.status.value:
        db.commit()
    else:
        db.rollback()
    refreshed = get_group_or_404(db, groupId)
    return to_ticket_group(refreshed)


@router.put("/manager/ticket-groups/{groupId}/comment", response_model=TicketGroup)
def save_manager_ticket_group_comment(
    groupId: str,
    payload: SaveTicketGroupCommentRequest,
    current_user: AuthenticatedUser = Depends(require_role(UserRole.manager)),
    db: Session = Depends(get_db),
) -> TicketGroup:
    now = utcnow()
    group = get_group_or_404(db, groupId)
    group.manager_comment = payload.managerComment
    group.updated_at = now

    for ticket in group.tickets:
        ticket.manager_comment = payload.managerComment
        ticket.updated_at = now
        add_history_event(
            db=db,
            ticket=ticket,
            event_type="manager_comment_updated",
            label="Manager comment updated",
            actor_type="user",
            actor_id=current_user.id,
            actor_display_name=current_user.full_name,
            created_at=now,
        )

    db.commit()
    refreshed = get_group_or_404(db, groupId)
    return to_ticket_group(refreshed)


@router.get("/manager/analytics/summary", response_model=ManagerAnalyticsSummary)
def get_manager_analytics_summary(
    _: AuthenticatedUser = Depends(require_role(UserRole.manager)),
    db: Session = Depends(get_db),
) -> ManagerAnalyticsSummary:
    groups = db.query(TicketGroupModel).options(joinedload(TicketGroupModel.tickets)).all()
    groups_by_status_rows = db.query(TicketGroupModel.status, func.count(TicketGroupModel.id)).group_by(TicketGroupModel.status).all()
    tickets_by_status_rows = db.query(TicketModel.status, func.count(TicketModel.id)).group_by(TicketModel.status).all()
    groups_by_status = {status: count for status, count in groups_by_status_rows}
    tickets_by_status = {status: count for status, count in tickets_by_status_rows}
    return to_analytics_summary(groups_by_status, tickets_by_status, groups)


@router.get("/health", include_in_schema=False)
def healthcheck() -> Response:
    return Response(status_code=204)
