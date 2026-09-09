from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session as OrmSession

from .config import DATABASE_URL
from .models import Base
from .migration import run_sqlite_migrations


def make_engine(database_url: str = DATABASE_URL) -> Engine:
    if database_url.startswith("sqlite"):
        if database_url.startswith("sqlite:///"):
            db_path = database_url.removeprefix("sqlite:///")
            if db_path and db_path != ":memory:":
                db_file = Path(db_path)
                db_file.parent.mkdir(parents=True, exist_ok=True)
        engine = create_engine(database_url, future=True)

        @event.listens_for(engine, "connect")
        def set_sqlite_pragma(dbapi_connection, connection_record):
            cursor = dbapi_connection.cursor()
            cursor.execute("PRAGMA foreign_keys=ON;")
            cursor.close()

        return engine
    return create_engine(database_url, future=True, pool_pre_ping=True)


class Database:
    def __init__(self, database_url: str = DATABASE_URL):
        self.engine = make_engine(database_url)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)
        run_sqlite_migrations(self.engine)

    def session(self) -> OrmSession:
        return self.SessionLocal()
