from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import sessionmaker, Session as OrmSession

from .config import DATABASE_URL
from .models import Base


def make_engine(database_url: str = DATABASE_URL) -> Engine:
    if database_url.startswith("sqlite:///"):
        db_file = Path(database_url.removeprefix("sqlite:///"))
        db_file.parent.mkdir(parents=True, exist_ok=True)
        return create_engine(database_url, future=True)
    return create_engine(database_url, future=True, pool_pre_ping=True)


class Database:
    def __init__(self, database_url: str = DATABASE_URL):
        self.engine = make_engine(database_url)
        self.SessionLocal = sessionmaker(bind=self.engine, expire_on_commit=False)

    def create_schema(self) -> None:
        Base.metadata.create_all(self.engine)

    def session(self) -> OrmSession:
        return self.SessionLocal()
