import os
from pathlib import Path
from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

DATA_DIR = Path(os.getenv("DATA_DIR", "data"))
DATA_DIR.mkdir(parents=True, exist_ok=True)
URL = os.getenv("DATABASE_URL", f"sqlite:///{DATA_DIR / 'budget.db'}")
engine = create_engine(URL, connect_args={"check_same_thread": False} if URL.startswith("sqlite") else {})


@event.listens_for(engine, "connect")
def _pragma(conn, _):
    if engine.dialect.name == "sqlite":
        cur = conn.cursor()
        cur.execute("PRAGMA foreign_keys=ON")
        cur.execute("PRAGMA journal_mode=WAL")
        cur.close()


SessionLocal = sessionmaker(engine, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


def get_db():
    with SessionLocal() as db:
        yield db
