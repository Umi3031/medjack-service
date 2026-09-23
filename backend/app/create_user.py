"""
Командын мөрөөр хэрэглэгч нэмэх, нууц үг солих хэрэгсэл.

Жишээ:
    python -m app.create_user bold --name "Б. Болд" --role engineer
    python -m app.create_user admin --reset        # админы нууц үг солих

Нууц үгийг дэлгэцэнд харуулахгүйгээр (getpass) хоёр удаа асууж баталгаажуулна.
"""
import argparse
import getpass
import sys

from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .models import USER_ROLES, User
from .security import hash_password


def main() -> None:
    """Командын аргументийг уншиж, хэрэглэгч үүсгэх эсвэл нууц үгийг шинэчилнэ."""
    parser = argparse.ArgumentParser(description="МЕДЖЕК Сервис: хэрэглэгч удирдах")
    parser.add_argument("username", help="нэвтрэх нэр")
    parser.add_argument("--name", default=None, help="овог нэр")
    parser.add_argument("--role", choices=USER_ROLES, default="engineer", help="эрх (анхдагч: engineer)")
    parser.add_argument("--reset", action="store_true", help="байгаа хэрэглэгчийн нууц үгийг солих")
    args = parser.parse_args()

    password = getpass.getpass("Шинэ нууц үг: ")
    if len(password) < 8:
        sys.exit("Нууц үг дор хаяж 8 тэмдэгттэй байх ёстой.")
    if password != getpass.getpass("Нууц үгээ давтана уу: "):
        sys.exit("Нууц үг таарсангүй.")

    Base.metadata.create_all(bind=engine)
    with SessionLocal() as db:
        user = db.scalar(select(User).where(User.username == args.username))
        if args.reset:
            if user is None:
                sys.exit(f"'{args.username}' нэртэй хэрэглэгч олдсонгүй.")
            user.password_hash = hash_password(password)
            print(f"'{args.username}' хэрэглэгчийн нууц үг солигдлоо.")
        else:
            if user is not None:
                sys.exit(f"'{args.username}' нэртэй хэрэглэгч аль хэдийн байна. --reset ашиглана уу.")
            db.add(User(username=args.username, full_name=args.name,
                        password_hash=hash_password(password), role=args.role))
            print(f"'{args.username}' хэрэглэгч ({args.role}) үүслээ.")
        db.commit()


if __name__ == "__main__":
    main()
