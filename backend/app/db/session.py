from sqlalchemy import create_engine, event
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings


settings = get_settings()

is_sqlite = settings.database_url.startswith("sqlite")
is_postgres = settings.database_url.startswith("postgresql")
if is_sqlite:
    connect_args = {"check_same_thread": False, "timeout": 60}
elif is_postgres:
    connect_args = {"connect_timeout": 5}
else:
    connect_args = {}
engine = create_engine(settings.database_url, connect_args=connect_args, future=True)


if is_sqlite:

    @event.listens_for(engine, "connect")
    def set_sqlite_pragmas(dbapi_connection, _connection_record) -> None:
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA synchronous=NORMAL")
        cursor.execute("PRAGMA busy_timeout=60000")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


SessionLocal = sessionmaker(
    bind=engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    future=True,
)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def session_scope() -> Session:
    return SessionLocal()
