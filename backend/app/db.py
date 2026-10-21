from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

from .config import get_settings


class Base(DeclarativeBase):
    pass


# pool_pre_ping/pool_recycle: o banco gratuito (Neon) desliga quando fica parado e derruba as conexões antigas.
engine = create_engine(get_settings().database_url, pool_pre_ping=True, pool_recycle=300)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
