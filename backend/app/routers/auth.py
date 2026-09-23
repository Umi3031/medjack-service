"""
Нэвтрэлтийн API.

    POST /api/auth/login  — хэрэглэгчийн нэр, нууц үгээр JWT токен авах
    GET  /api/auth/me     — одоо нэвтэрсэн хэрэглэгчийн мэдээлэл
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..models import User
from ..security import create_access_token, get_current_user, verify_password

router = APIRouter(prefix="/api/auth", tags=["Нэвтрэлт"])


@router.post("/login", response_model=schemas.TokenOut)
def login(data: schemas.LoginIn, db: Session = Depends(get_db)):
    """
    Хэрэглэгчийг баталгаажуулж токен олгоно.

    Хэрэглэгчийн нэр буруу эсвэл нууц үг буруу аль ч тохиолдолд ижил
    алдааны мессеж буцаана. Ингэснээр системд ямар хэрэглэгч байгааг
    гаднаас таах боломжгүй болно.
    """
    user = db.scalar(select(User).where(User.username == data.username.strip()))
    if user is None or not user.is_active or not verify_password(data.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Хэрэглэгчийн нэр эсвэл нууц үг буруу байна.")
    return schemas.TokenOut(
        access_token=create_access_token(user),
        username=user.username,
        full_name=user.full_name,
        role=user.role,
    )


@router.get("/me", response_model=schemas.UserOut)
def me(user: User = Depends(get_current_user)):
    """Токены эзэмшигч хэрэглэгчийн нэр, овог нэр, үүргийг буцаана."""
    return user
