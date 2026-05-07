from app.db.session import Base, SessionLocal, engine
from app.scripts.init_db import ensure_demo_tickets, ensure_users, migrate_legacy_schema


def main() -> None:
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    migrate_legacy_schema()

    session = SessionLocal()
    try:
        users = ensure_users(session)
        ensure_demo_tickets(session, users["employee"], users["manager"])
        session.commit()
    finally:
        session.close()

    print("Database reset complete. Default demo data restored.")


if __name__ == "__main__":
    main()
