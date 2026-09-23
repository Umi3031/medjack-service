"""
Өгөгдлийн сантай холбогдох давхарга.

SQLAlchemy 2.0-ийн engine, session болон ORM загваруудын суурь классыг
тодорхойлно. Бусад модулиуд өгөгдлийн сантай зөвхөн энэ модулиар дамжин
харьцана.
"""
from collections.abc import Iterator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import get_settings

settings = get_settings()

# SQLite нь олон thread-ээс нэг холболт ашиглахыг анхдагчаар хориглодог тул
# зөвхөн SQLite үед энэ хязгаарлалтыг унтраана.
_connect_args = {"check_same_thread": False} if settings.database_url.startswith("sqlite") else {}

engine = create_engine(
    settings.database_url,
    pool_pre_ping=True,  # тасарсан холболтыг ашиглахаас өмнө шалгаж сэргээнэ
    connect_args=_connect_args,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


class Base(DeclarativeBase):
    """Бүх ORM загвар (хүснэгт) удамших суурь класс."""


def get_db() -> Iterator[Session]:
    """
    FastAPI-ийн dependency: HTTP хүсэлт бүрт тусдаа session нээнэ.

    Хүсэлт боловсруулж дууссаны дараа, алдаа гарсан ч гэсэн, `finally`
    хэсэгт session-ийг заавал хааж холболтыг pool руу буцаана.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
