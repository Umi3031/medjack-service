"""
Нэвтрэлт ба эрхийн удирдлага.

- Нууц үгийг PBKDF2-HMAC-SHA256 алгоритмаар, хэрэглэгч бүрт санамсаргүй
  давс (salt) үүсгэн хэшилнэ. Python-ийн стандарт сан ашигладаг тул
  нэмэлт C сан суулгах шаардлагагүй.
- Амжилттай нэвтэрсэн хэрэглэгчид хугацаатай JWT токен олгоно. Клиент
  дараагийн хүсэлт бүртээ `Authorization: Bearer <token>` толгой илгээнэ.
- `require_admin` dependency нь зөвхөн админ эрхтэй хэрэглэгчийг
  нэвтрүүлж, үүрэгт суурилсан хандалтын хяналтыг (RBAC) хэрэгжүүлнэ.
"""
import base64
import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import get_settings
from .database import get_db
from .models import User

settings = get_settings()
_bearer = HTTPBearer(auto_error=False)

PBKDF2_ITERATIONS = 390_000


def hash_password(password: str) -> str:
    """
    Нууц үгийг хадгалахад аюулгүй хэш болгон хувиргана.

    Үр дүн нь `pbkdf2_sha256$давталт$давс$хэш` хэлбэртэй мөр бөгөөд
    шалгахад шаардлагатай бүх параметрийг өөртөө агуулна. Ижил нууц үг ч
    давс өөр учраас хэрэглэгч бүрт өөр хэш үүснэ.
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, PBKDF2_ITERATIONS)
    return "pbkdf2_sha256${}${}${}".format(
        PBKDF2_ITERATIONS,
        base64.b64encode(salt).decode(),
        base64.b64encode(digest).decode(),
    )


def verify_password(password: str, stored: str) -> bool:
    """
    Оруулсан нууц үгийг хадгалсан хэштэй тулгаж шалгана.

    `hmac.compare_digest` нь харьцуулалтыг тогтмол хугацаанд гүйцэтгэдэг
    тул хугацааны зөрүүгээр нууц үг таах (timing attack) халдлагаас сэргийлнэ.
    """
    try:
        algorithm, iterations, salt_b64, hash_b64 = stored.split("$")
        if algorithm != "pbkdf2_sha256":
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), base64.b64decode(salt_b64), int(iterations)
        )
        return hmac.compare_digest(digest, base64.b64decode(hash_b64))
    except (ValueError, TypeError):
        return False


def create_access_token(user: User) -> str:
    """
    Хэрэглэгчид зориулсан хугацаатай JWT токен үүсгэнэ.

    Токен дотор хэрэглэгчийн нэр (`sub`), үүрэг (`role`) болон дуусах
    хугацаа (`exp`) бичигдэж, серверийн нууц түлхүүрээр гарын үсэг зурна.
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user.username,
        "role": user.role,
        "iat": now,
        "exp": now + timedelta(minutes=settings.jwt_expire_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> User:
    """
    Хүсэлтийн толгойн токеныг шалгаж, нэвтэрсэн хэрэглэгчийг буцаана.

    Токен байхгүй, хугацаа нь дууссан, гарын үсэг буруу, эсвэл хэрэглэгч
    идэвхгүй болсон тохиолдолд 401 алдаа өгч хүсэлтийг зогсооно.
    """
    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Нэвтрэх шаардлагатай.",
        headers={"WWW-Authenticate": "Bearer"},
    )
    if credentials is None:
        raise unauthorized
    try:
        payload = jwt.decode(
            credentials.credentials, settings.jwt_secret, algorithms=[settings.jwt_algorithm]
        )
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Нэвтрэлтийн хугацаа дууссан. Дахин нэвтэрнэ үү.")
    except jwt.InvalidTokenError:
        raise unauthorized

    user = db.scalar(select(User).where(User.username == payload.get("sub")))
    if user is None or not user.is_active:
        raise unauthorized
    return user


def require_admin(user: User = Depends(get_current_user)) -> User:
    """Зөвхөн `admin` үүрэгтэй хэрэглэгчийг нэвтрүүлнэ, бусдад 403 буцаана."""
    if user.role != "admin":
        raise HTTPException(status_code=403, detail="Энэ үйлдлийг зөвхөн админ хийх эрхтэй.")
    return user
