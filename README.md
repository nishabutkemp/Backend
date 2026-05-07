# Pulse Tickets Backend

FastAPI backend for the Pulse Tickets MVP, implemented against `../openapi.yaml`.

## Stack

- Python 3.12
- FastAPI
- PostgreSQL
- SQLAlchemy
- Docker / Docker Compose

## Features

- `POST /v1/auth/login`
- `GET /v1/me`
- `POST /v1/ai/enhance-ticket-description`
- `POST /v1/tickets`
- `GET /v1/tickets/my`
- `GET /v1/tickets/my/{ticketId}`
- `GET /v1/manager/ticket-groups`
- `GET /v1/manager/ticket-groups/{groupId}`
- `PATCH /v1/manager/ticket-groups/{groupId}/status`
- `PUT /v1/manager/ticket-groups/{groupId}/comment`
- `GET /v1/manager/analytics/summary`

## Auth

JWT access tokens are issued by `POST /v1/auth/login`.

Demo credentials:

- Employee: `employee@pulse.local` / `employee123`
- Manager: `manager@pulse.local` / `manager123`

## AI Integration

Backend supports Yandex Cloud ML for:

- ticket description enhancement
- ticket group classification

Configure in `.env`:

```bash
YANDEX_FOLDER_ID=your_folder_id
YANDEX_AUTH_TOKEN=your_iam_or_api_token
YANDEX_GPT_MODEL=yandexgpt-lite
YANDEX_GPT_TEMPERATURE=0.3
YANDEX_GPT_MAX_TOKENS=2000
```

If Yandex credentials are missing or the provider call fails, the backend falls back to the built-in deterministic MVP mock.

## Run with Docker

```bash
cd backend
cp .env.example .env
docker compose up --build
```

API будет доступно на `http://localhost:8000`, Swagger UI на `http://localhost:8000/docs`.

## Reset DB

Чтобы полностью сбросить БД в дефолтное demo-состояние, запусти:

```bash
cd backend
sh scripts/reset_db.sh
```

Скрипт:

- удаляет прикладные таблицы
- пересоздаёт схему
- заново сидирует test/demo accounts, ticket groups и demo tickets

Получение токена:

```bash
curl -X POST http://localhost:8000/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email":"employee@pulse.local","password":"employee123"}'
```

## Demo data

На старте инициализируются:

- employee user: `Ivan Petrov`
- manager user: `Anna Sidorova`
- demo tickets `PT-121` ... `PT-124`
- demo manager groups for email, VPN, monitor and onboarding scenarios

## Notes

- Все даты возвращаются в ISO 8601.
- Списки поддерживают `page`, `pageSize`, `status`, `query`.
- `status` передаётся как CSV, например `open,in_review`.
- AI enhancement и AI grouping реализованы как deterministic MVP mock.
- При наличии Yandex Cloud ML включается реальный AI provider, иначе остаётся fallback/mock.
- Инициализация БД выполняется командой `python -m app.scripts.init_db` перед запуском API.
