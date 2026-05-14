from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from sqlalchemy.pool import StaticPool

from .config import get_settings

settings = get_settings()

database_url = settings.DATABASE_URL
connect_args = {}
poolclass = None

if database_url.startswith("sqlite"):
    connect_args["check_same_thread"] = False
    if database_url == "sqlite://":
        poolclass = StaticPool

engine = create_engine(database_url, connect_args=connect_args, poolclass=poolclass)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_session() -> Generator:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
