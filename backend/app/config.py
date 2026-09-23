"""
Системийн тохиргооны модуль.

Бүх тохиргоог орчны хувьсагч (environment variable) эсвэл `.env` файлаас
уншина. Ингэснээр нууц үг, өгөгдлийн сангийн хаяг зэрэг мэдээлэл кодонд
шууд бичигдэхгүй бөгөөд хөгжүүлэлтийн болон сервер орчныг зөвхөн `.env`
файлаар ялгаж ажиллуулах боломжтой болно.
"""
from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Төслийн үндсэн хавтас: medjack-service/
PROJECT_ROOT = Path(__file__).resolve().parents[2]


class Settings(BaseSettings):
    """
    Програмын бүх тохиргоог нэг дор төвлөрүүлсэн класс.

    Талбар бүр ижил нэртэй орчны хувьсагчаас (том, жижиг үсэг ялгахгүй)
    утгаа авна. Жишээ нь `DATABASE_URL` хувьсагч `database_url` талбарт
    оноогдоно. Утга өгөөгүй тохиолдолд доорх анхдагч утгыг ашиглана.
    """

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # Өгөгдлийн сан. PostgreSQL-ийг үндсэн сонголт болгосон. Туршилтын үед
    # "sqlite:///./medjack.db" гэж өгвөл сервер суулгахгүйгээр ажиллана.
    database_url: str = "postgresql+psycopg://medjack:medjack@localhost:5432/medjack"

    # JWT токены тохиргоо
    jwt_secret: str = "change-this-secret-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 480  # нэг ажлын өдөр (8 цаг)

    # Анх ажиллуулахад автоматаар үүсэх админ хэрэглэгч
    admin_username: str = "admin"
    admin_password: str = "Medjack2026!"

    # QR код болон мэдэгдэлд харагдах байгууллагын мэдээлэл
    public_base_url: str = "http://localhost:8000"
    company_name: str = "МЕДЖЕК ХХК"
    service_phone: str = ""

    # Frontend файлуудын байршил
    frontend_dir: Path = PROJECT_ROOT / "frontend"


@lru_cache
def get_settings() -> Settings:
    """
    Тохиргооны объектыг нэг удаа үүсгээд дахин ашиглана (singleton).

    `lru_cache` ашигласнаар `.env` файлыг хүсэлт бүрт дахин уншихгүй тул
    гүйцэтгэл сайжирна.
    """
    return Settings()
