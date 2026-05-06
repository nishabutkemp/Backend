from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.core.auth import hash_password
from app.core.config import get_settings
from app.db.models import TicketGroupModel, TicketHistoryEventModel, TicketModel, UserModel
from app.db.session import Base, get_db
from app.main import app


TEST_EMPLOYEE_EMAIL = "employee@pulse.local"
TEST_EMPLOYEE_PASSWORD = "employee123"
TEST_MANAGER_EMAIL = "manager@pulse.local"
TEST_MANAGER_PASSWORD = "manager123"


@pytest.fixture
def client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )
    TestingSessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False)
    Base.metadata.create_all(bind=engine)

    session = TestingSessionLocal()
    try:
        seed_demo_data(session)
        session.commit()
    finally:
        session.close()

    def override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    get_settings.cache_clear()

    with TestClient(app) as test_client:
        yield test_client

    app.dependency_overrides.clear()
    Base.metadata.drop_all(bind=engine)


def add_history(ticket, *, event_id: str, event_type: str, label: str, actor_type: str, actor_display_name: str, created_at: datetime, actor_id: str | None = None, from_status: str | None = None, to_status: str | None = None):
    return TicketHistoryEventModel(
        id=event_id,
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


def seed_demo_data(session):
    employee = UserModel(
        id="usr_employee_demo",
        full_name="Ivan Petrov",
        initials="IP",
        role="employee",
        email=TEST_EMPLOYEE_EMAIL,
        password_hash=hash_password(TEST_EMPLOYEE_PASSWORD),
    )
    manager = UserModel(
        id="usr_manager_demo",
        full_name="Anna Sidorova",
        initials="AS",
        role="manager",
        email=TEST_MANAGER_EMAIL,
        password_hash=hash_password(TEST_MANAGER_PASSWORD),
    )
    outsider = UserModel(
        id="usr_employee_other",
        full_name="Olga Smirnova",
        initials="OS",
        role="employee",
        email="other@pulse.local",
        password_hash=hash_password("other123"),
    )
    session.add_all([employee, manager, outsider])

    email_group = TicketGroupModel(
        id="grp_corporate_email",
        classifier_key="corporate_email",
        title="Ошибка входа в корпоративную почту после смены пароля",
        ai_summary="Several employees report losing access to corporate email after password changes or Outlook re-authentication.",
        status="in_review",
        manager_comment="Проверяем проблему с доступом после смены пароля. Вернёмся с обновлением сегодня до конца дня.",
        last_ticket_created_at=datetime(2026, 5, 6, 9, 0, tzinfo=UTC),
        created_at=datetime(2026, 5, 6, 9, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 6, 9, 45, tzinfo=UTC),
    )
    vpn_group = TicketGroupModel(
        id="grp_vpn_access",
        classifier_key="vpn_access",
        title="Проблемы с доступом к VPN",
        ai_summary="Multiple employees report unstable VPN access that interrupts work with internal tools.",
        status="in_review",
        manager_comment="Проверяем синхронизацию доступа после смены пароля. Обновим статус после проверки с IT.",
        last_ticket_created_at=datetime(2026, 5, 6, 11, 0, tzinfo=UTC),
        created_at=datetime(2026, 5, 6, 11, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 6, 11, 45, tzinfo=UTC),
    )
    monitor_group = TicketGroupModel(
        id="grp_monitor_request",
        classifier_key="monitor_request",
        title="Запрос на дополнительный монитор",
        ai_summary="Employees request additional monitor equipment to improve their daily workstation setup.",
        status="open",
        manager_comment=None,
        last_ticket_created_at=datetime(2026, 5, 6, 10, 0, tzinfo=UTC),
        created_at=datetime(2026, 5, 6, 10, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 6, 10, 0, tzinfo=UTC),
    )
    onboarding_group = TicketGroupModel(
        id="grp_onboarding",
        classifier_key="onboarding",
        title="Вопросы по онбордингу новых сотрудников",
        ai_summary="Employees share recurring onboarding issues and suggestions for improving the new hire experience.",
        status="open",
        manager_comment=None,
        last_ticket_created_at=datetime(2026, 5, 6, 12, 0, tzinfo=UTC),
        created_at=datetime(2026, 5, 6, 12, 0, tzinfo=UTC),
        updated_at=datetime(2026, 5, 6, 12, 0, tzinfo=UTC),
    )
    session.add_all([email_group, vpn_group, monitor_group, onboarding_group])
    session.flush()

    tickets = [
        TicketModel(
            id="tkt_seed_pt_124",
            number="PT-124",
            title="Нет доступа к корпоративной почте",
            description="[AI-enhanced] После смены пароля Outlook перестал принимать вход и я не могу открыть корпоративную почту.",
            original_description="После смены пароля не открывается почта",
            ai_enhanced=True,
            status="in_review",
            manager_comment=email_group.manager_comment,
            author_id=employee.id,
            group_id=email_group.id,
            created_at=datetime(2026, 5, 6, 9, 0, tzinfo=UTC),
            updated_at=datetime(2026, 5, 6, 9, 45, tzinfo=UTC),
            resolved_at=None,
        ),
        TicketModel(
            id="tkt_seed_pt_123",
            number="PT-123",
            title="Запрос на новый монитор для работы",
            description="Нужен второй монитор для работы с аналитикой и таблицами, одного экрана недостаточно.",
            original_description=None,
            ai_enhanced=False,
            status="open",
            manager_comment=None,
            author_id=employee.id,
            group_id=monitor_group.id,
            created_at=datetime(2026, 5, 6, 10, 0, tzinfo=UTC),
            updated_at=datetime(2026, 5, 6, 10, 0, tzinfo=UTC),
            resolved_at=None,
        ),
        TicketModel(
            id="tkt_seed_pt_122",
            number="PT-122",
            title="Проблемы с VPN-подключением",
            description="VPN отключается несколько раз в день, из-за этого теряется доступ к внутренним инструментам.",
            original_description=None,
            ai_enhanced=False,
            status="in_review",
            manager_comment=vpn_group.manager_comment,
            author_id=employee.id,
            group_id=vpn_group.id,
            created_at=datetime(2026, 5, 6, 11, 0, tzinfo=UTC),
            updated_at=datetime(2026, 5, 6, 11, 45, tzinfo=UTC),
            resolved_at=None,
        ),
        TicketModel(
            id="tkt_seed_pt_121",
            number="PT-121",
            title="Предложение по улучшению онбординга",
            description="Стоит добавить единый чеклист и список доступов для новых сотрудников в первую неделю.",
            original_description=None,
            ai_enhanced=False,
            status="open",
            manager_comment=None,
            author_id=employee.id,
            group_id=onboarding_group.id,
            created_at=datetime(2026, 5, 6, 12, 0, tzinfo=UTC),
            updated_at=datetime(2026, 5, 6, 12, 0, tzinfo=UTC),
            resolved_at=None,
        ),
        TicketModel(
            id="tkt_foreign",
            number="PT-120",
            title="Чужой тикет",
            description="Этот тикет не должен быть виден другому сотруднику.",
            original_description=None,
            ai_enhanced=False,
            status="open",
            manager_comment=None,
            author_id=outsider.id,
            group_id=monitor_group.id,
            created_at=datetime(2026, 5, 6, 8, 0, tzinfo=UTC),
            updated_at=datetime(2026, 5, 6, 8, 0, tzinfo=UTC),
            resolved_at=None,
        ),
    ]
    session.add_all(tickets)
    session.flush()

    for ticket in tickets:
        session.add(
            add_history(
                ticket,
                event_id=f"the_created_{ticket.id}",
                event_type="ticket_created",
                label="Ticket created",
                actor_type="user",
                actor_display_name="Ivan Petrov" if ticket.author_id == employee.id else "Olga Smirnova",
                actor_id=ticket.author_id,
                created_at=ticket.created_at,
                to_status="open",
            )
        )
        session.add(
            add_history(
                ticket,
                event_id=f"the_group_{ticket.id}",
                event_type="group_assigned",
                label="Ticket assigned to AI group",
                actor_type="ai",
                actor_display_name="AI Grouper",
                created_at=ticket.created_at + timedelta(minutes=1),
            )
        )

    for ticket in (tickets[0], tickets[2]):
        session.add(
            add_history(
                ticket,
                event_id=f"the_status_{ticket.id}",
                event_type="group_status_changed",
                label="Group status changed by manager",
                actor_type="user",
                actor_display_name="Anna Sidorova",
                actor_id=manager.id,
                created_at=ticket.created_at + timedelta(minutes=30),
                from_status="open",
                to_status="in_review",
            )
        )
        session.add(
            add_history(
                ticket,
                event_id=f"the_comment_{ticket.id}",
                event_type="manager_comment_updated",
                label="Manager comment updated",
                actor_type="user",
                actor_display_name="Anna Sidorova",
                actor_id=manager.id,
                created_at=ticket.created_at + timedelta(minutes=45),
            )
        )


@pytest.fixture
def employee_headers(client):
    response = client.post(
        "/v1/auth/login",
        json={"email": TEST_EMPLOYEE_EMAIL, "password": TEST_EMPLOYEE_PASSWORD},
    )
    assert response.status_code == 200
    token = response.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def manager_headers(client):
    response = client.post(
        "/v1/auth/login",
        json={"email": TEST_MANAGER_EMAIL, "password": TEST_MANAGER_PASSWORD},
    )
    assert response.status_code == 200
    token = response.json()["accessToken"]
    return {"Authorization": f"Bearer {token}"}
