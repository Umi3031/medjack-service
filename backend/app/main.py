"""
МЕДЖЕК Сервис — FastAPI програмын эхлэх цэг.

Энэ модуль нь:
  1. эхлэхэд өгөгдлийн сангийн хүснэгтүүдийг үүсгэж, анхны админыг бүртгэнэ;
  2. REST API-ийн бүх маршрутыг (`/api/...`) холбоно;
  3. frontend-ийн статик файлуудыг (`/`) нэг серверээс түгээнэ.
Ажиллуулах:  uvicorn app.main:app --reload
API баримт бичиг: http://localhost:8000/docs
"""
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from sqlalchemy import select

from .config import get_settings
from .database import Base, SessionLocal, engine
from .models import User
from .routers import auth, customers, dashboard, devices, export, public, tickets
from .security import hash_password

settings = get_settings()


def ensure_admin() -> None:
    """
    Системд нэг ч хэрэглэгч байхгүй бол `.env`-д заасан админыг үүсгэнэ.

    Зөвхөн анх удаа ажиллуулахад хэрэгжинэ. Нэвтэрсний дараа нууц үгийг
    заавал солихыг зөвлөнө (README-г үзнэ үү).
    """
    with SessionLocal() as db:
        if db.scalar(select(User.user_id).limit(1)) is None:
            db.add(User(
                username=settings.admin_username,
                full_name="Системийн админ",
                password_hash=hash_password(settings.admin_password),
                role="admin",
            ))
            db.commit()


@asynccontextmanager
async def lifespan(_: FastAPI):
    """Сервер асах үед нэг удаа ажиллах бэлтгэл: хүснэгт үүсгэх, админ бүртгэх."""
    Base.metadata.create_all(bind=engine)
    ensure_admin()
    yield


app = FastAPI(
    title="МЕДЖЕК Сервис API",
    description="Эмнэлгийн тоног төхөөрөмжийн паспорт, баталгааны сануулга, засвар үйлчилгээний бүртгэл.",
    version="1.0.0",
    lifespan=lifespan,
)

for r in (auth, customers, devices, tickets, dashboard, public, export):
    app.include_router(r.router)


@app.get("/api/health", tags=["Систем"])
def health():
    """Сервер ажиллаж байгаа эсэхийг шалгах (мониторинг, Docker healthcheck)."""
    return {"status": "ok"}


# Статик файлуудыг API-ийн дараа холбоно. Эс тэгвээс `/` зам `/api`-г далдална.
app.mount("/", StaticFiles(directory=settings.frontend_dir, html=True), name="frontend")
