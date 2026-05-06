from datetime import UTC, datetime, timedelta
from uuid import uuid4

from sqlalchemy import inspect, text
from sqlalchemy.orm import joinedload

from app.core.auth import hash_password
from app.core.config import get_settings
from app.db.models import TicketGroupModel, TicketHistoryEventModel, TicketModel, UserModel
from app.db.session import Base, SessionLocal, engine
from app.schemas.api import TicketStatus
from app.services.grouping import classify_ticket, generate_title, normalize_group_key


settings = get_settings()


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid4().hex}"


def add_history(ticket: TicketModel, *, event_type: str, label: str, actor_type: str, actor_display_name: str, created_at: datetime, actor_id: str | None = None, from_status: str | None = None, to_status: str | None = None) -> TicketHistoryEventModel:
    return TicketHistoryEventModel(
        id=new_id("the"),
        ticket=ticket,
        type=event_type,
        label=label,
        from_status=from_status,
        to_status=to_status,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_display_name=actor_display_name,
        created_at=created_at,
    )


def migrate_legacy_schema():
    inspector = inspect(engine)
    if "users" not in inspector.get_table_names():
        return

    user_columns = {column["name"] for column in inspector.get_columns("users")}
    statements: list[str] = []

    if "email" not in user_columns:
        statements.append("ALTER TABLE users ADD COLUMN email VARCHAR(255)")
    if "password_hash" not in user_columns:
        statements.append("ALTER TABLE users ADD COLUMN password_hash VARCHAR(255)")

    if not statements:
        return

    with engine.begin() as connection:
        for statement in statements:
            connection.execute(text(statement))

        connection.execute(
            text(
                """
                UPDATE users
                SET email = CASE role
                    WHEN 'employee' THEN 'employee@pulse.local'
                    WHEN 'manager' THEN 'manager@pulse.local'
                    ELSE CONCAT(id, '@pulse.local')
                END
                WHERE email IS NULL
                """
            )
        )
        connection.execute(
            text(
                """
                UPDATE users
                SET password_hash = CASE role
                    WHEN 'employee' THEN :employee_password_hash
                    WHEN 'manager' THEN :manager_password_hash
                    ELSE :fallback_password_hash
                END
                WHERE password_hash IS NULL
                """
            ),
            {
                "employee_password_hash": hash_password("employee123"),
                "manager_password_hash": hash_password("manager123"),
                "fallback_password_hash": hash_password("changeme123"),
            },
        )


def ensure_users(session):
    users = session.query(UserModel).all()
    if users:
        return {user.role: user for user in users}

    employee = UserModel(
        id="usr_employee_demo",
        full_name="Ivan Petrov",
        initials="IP",
        role="employee",
        email="employee@pulse.local",
        password_hash=hash_password("employee123"),
    )
    manager = UserModel(
        id="usr_manager_demo",
        full_name="Anna Sidorova",
        initials="AS",
        role="manager",
        email="manager@pulse.local",
        password_hash=hash_password("manager123"),
    )
    session.add_all([employee, manager])
    session.flush()
    return {"employee": employee, "manager": manager}


def ensure_group(session, key: str, now: datetime) -> TicketGroupModel:
    group = (
        session.query(TicketGroupModel)
        .options(joinedload(TicketGroupModel.tickets))
        .filter(TicketGroupModel.classifier_key == key)
        .one_or_none()
    )
    if group:
        return group

    templates = {
        normalize_group_key("Ошибка входа в корпоративную почту после смены пароля"): (
            "Ошибка входа в корпоративную почту после смены пароля",
            "Several employees report losing access to corporate email after password changes or Outlook re-authentication.",
            "Проверяем проблему с доступом после смены пароля. Вернёмся с обновлением сегодня до конца дня.",
            TicketStatus.in_review.value,
        ),
        normalize_group_key("Запрос на дополнительный монитор"): (
            "Запрос на дополнительный монитор",
            "Employees request additional monitor equipment to improve their daily workstation setup.",
            None,
            TicketStatus.open.value,
        ),
        normalize_group_key("Проблемы с доступом к VPN"): (
            "Проблемы с доступом к VPN",
            "Multiple employees report unstable VPN access that interrupts work with internal tools.",
            "Проверяем синхронизацию доступа после смены пароля. Обновим статус после проверки с IT.",
            TicketStatus.in_review.value,
        ),
        normalize_group_key("Вопросы по онбордингу новых сотрудников"): (
            "Вопросы по онбордингу новых сотрудников",
            "Employees share recurring onboarding issues and suggestions for improving the new hire experience.",
            None,
            TicketStatus.open.value,
        ),
    }
    title, summary, manager_comment, status = templates[key]
    group = TicketGroupModel(
        id=f"grp_{key}",
        classifier_key=key,
        title=title,
        ai_summary=summary,
        status=status,
        manager_comment=manager_comment,
        last_ticket_created_at=now,
        created_at=now,
        updated_at=now,
    )
    session.add(group)
    session.flush()
    return group


def ensure_demo_tickets(session, employee: UserModel, manager: UserModel):
    if session.query(TicketModel.id).first():
        return

    base_time = datetime(2026, 5, 6, 9, 0, tzinfo=UTC)
    demo = [
        ("PT-124", "Нет доступа к корпоративной почте", "После смены пароля Outlook перестал принимать вход и я не могу открыть корпоративную почту.", True, "После смены пароля не открывается почта", TicketStatus.in_review.value, 0),
        ("PT-123", "Запрос на новый монитор для работы", "Нужен второй монитор для работы с аналитикой и таблицами, одного экрана недостаточно.", False, None, TicketStatus.open.value, 1),
        ("PT-122", "Проблемы с VPN-подключением", "VPN отключается несколько раз в день, из-за этого теряется доступ к внутренним инструментам.", False, None, TicketStatus.in_review.value, 2),
        ("PT-121", "Предложение по улучшению онбординга", "Стоит добавить единый чеклист и список доступов для новых сотрудников в первую неделю.", False, None, TicketStatus.open.value, 3),
    ]

    for number, title, description, ai_enhanced, original, status, offset in demo:
        created_at = base_time + timedelta(hours=offset)
        template = classify_ticket(f"{title}\n{description}")
        group = ensure_group(session, template.key, created_at)
        ticket = TicketModel(
            id=f"tkt_seed_{number.lower()}",
            number=number,
            title=generate_title(title, description),
            description=description if not ai_enhanced else f"[AI-enhanced] {description}",
            original_description=original,
            ai_enhanced=ai_enhanced,
            status=status,
            manager_comment=group.manager_comment,
            author_id=employee.id,
            group_id=group.id,
            created_at=created_at,
            updated_at=created_at,
            resolved_at=created_at + timedelta(hours=4) if status == TicketStatus.resolved.value else None,
        )
        session.add(ticket)
        session.flush()

        session.add(
            add_history(
                ticket,
                event_type="ticket_created",
                label="Ticket created",
                actor_type="user",
                actor_id=employee.id,
                actor_display_name=employee.full_name,
                created_at=created_at,
                to_status=status,
            )
        )
        session.add(
            add_history(
                ticket,
                event_type="group_assigned",
                label="Ticket assigned to AI group",
                actor_type="ai",
                actor_display_name="AI Grouper",
                created_at=created_at,
            )
        )
        if group.status != TicketStatus.open.value:
            session.add(
                add_history(
                    ticket,
                    event_type="group_status_changed",
                    label="Group status changed by manager",
                    actor_type="user",
                    actor_id=manager.id,
                    actor_display_name=manager.full_name,
                    created_at=created_at + timedelta(minutes=30),
                    from_status=TicketStatus.open.value,
                    to_status=group.status,
                )
            )
        if group.manager_comment:
            session.add(
                add_history(
                    ticket,
                    event_type="manager_comment_updated",
                    label="Manager comment updated",
                    actor_type="user",
                    actor_id=manager.id,
                    actor_display_name=manager.full_name,
                    created_at=created_at + timedelta(minutes=45),
                )
            )

        group.last_ticket_created_at = max(group.last_ticket_created_at, created_at)
        group.updated_at = max(group.updated_at, created_at + timedelta(minutes=45))


def main():
    Base.metadata.create_all(bind=engine)
    migrate_legacy_schema()
    if not settings.seed_demo_data:
        return

    session = SessionLocal()
    try:
        users = ensure_users(session)
        ensure_demo_tickets(session, users["employee"], users["manager"])
        session.commit()
    finally:
        session.close()


if __name__ == "__main__":
    main()
