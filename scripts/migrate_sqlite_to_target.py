"""Migrate a RehabTwin Digital Thread SQLite database into any SQLAlchemy target.

Example:
    python scripts/migrate_sqlite_to_target.py \
      --source data/rehabtwin_thread.db \
      --target postgresql+psycopg://USER:PASSWORD@HOST/rehabtwin

The target schema is created from the SQLAlchemy models first. Data is then
copied table-by-table. The script is deliberately kept separate from the
runtime thread so migration does not affect normal operation.
"""

import argparse
from pathlib import Path
import sys

from sqlalchemy import create_engine, select
from sqlalchemy.orm import sessionmaker

PROJECT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT))

from digital_thread.models import Base, Session, Frame, Result  # noqa: E402


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", required=True, help="Path to SQLite .db file")
    parser.add_argument("--target", required=True, help="Target SQLAlchemy database URL")
    args = parser.parse_args()

    source_url = f"sqlite:///{Path(args.source).as_posix()}"
    source_engine = create_engine(source_url, future=True)
    target_engine = create_engine(args.target, future=True, pool_pre_ping=True)
    Base.metadata.create_all(target_engine)

    Source = sessionmaker(bind=source_engine, expire_on_commit=False)
    Target = sessionmaker(bind=target_engine, expire_on_commit=False)

    with Source() as src, Target() as dst:
        sessions = src.scalars(select(Session)).all()
        frames = src.scalars(select(Frame)).all()
        results = src.scalars(select(Result)).all()

        for item in sessions:
            dst.merge(item)
        dst.commit()
        for item in frames:
            dst.merge(item)
        dst.commit()
        for item in results:
            dst.merge(item)
        dst.commit()

    print(f"Migrated {len(sessions)} sessions, {len(frames)} frames, {len(results)} results.")


if __name__ == "__main__":
    main()
