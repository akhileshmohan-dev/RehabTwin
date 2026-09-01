import os
from pathlib import Path


def default_database_url() -> str:
    # SQLite is the default for local/offline RehabTwin development.
    db_path = Path(os.getenv("REHABTWIN_DB_PATH", "data/rehabtwin_thread.db"))
    db_path.parent.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{db_path.as_posix()}"


DATABASE_URL = os.getenv("DATABASE_URL", default_database_url())
