"""
Өгөгдлийн сангийн хүснэгтүүдийн ORM загвар.

Тайлангийн 5.2-т боловсруулсан ER загвар (Customer → Device → ServiceTicket)
дээр суурилж, системд нэвтрэх хэрэглэгчийн `app_user` хүснэгтийг нэмсэн.
Хамаарал:
    Customer 1 ── N Device 1 ── N ServiceTicket
"""
from datetime import date, datetime

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base

DEVICE_STATUSES = ("Ажиллаж байгаа", "Засварт", "Ашиглалтаас гарсан")
TICKET_STATUSES = ("Нээлттэй", "Хийгдэж байгаа", "Хаагдсан")
USER_ROLES = ("admin", "engineer")


class Customer(Base):
    """
    Харилцагч байгууллага: эмнэлэг, лаборатори, эрүүл мэндийн төв.

    Нэг харилцагч олон төхөөрөмжтэй байж болно. Төхөөрөмж бүртгэлтэй
    харилцагчийг устгахыг API түвшинд хориглосон.
    """

    __tablename__ = "customer"

    customer_id: Mapped[int] = mapped_column(primary_key=True)
    organization_name: Mapped[str] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(String(300))
    contact_person: Mapped[str | None] = mapped_column(String(120))
    phone: Mapped[str | None] = mapped_column(String(30))
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())

    devices: Mapped[list["Device"]] = relationship(back_populates="customer")


class Device(Base):
    """
    Тоног төхөөрөмжийн паспорт.

    `device_code` (жишээ нь MJ-0001) нь QR код дээр хэвлэгдэх, хүнд
    ойлгомжтой өвөрмөц код. `serial_number` нь үйлдвэрлэгчийн серийн
    дугаар бөгөөд давхардахгүй байх нөхцөлтэй. Баталгаат хугацаа
    суурилуулсан огнооноос өмнө дуусахгүй байхыг CHECK нөхцөлөөр хамгаална.
    """

    __tablename__ = "device"
    __table_args__ = (
        CheckConstraint(
            "warranty_end_date IS NULL OR warranty_end_date >= install_date",
            name="chk_warranty_after_install",
        ),
    )

    device_id: Mapped[int] = mapped_column(primary_key=True)
    device_code: Mapped[str] = mapped_column(String(20), unique=True, index=True)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customer.customer_id", ondelete="RESTRICT"), index=True)
    category: Mapped[str] = mapped_column(String(80))
    brand: Mapped[str | None] = mapped_column(String(80))
    model: Mapped[str] = mapped_column(String(120))
    serial_number: Mapped[str] = mapped_column(String(80), unique=True)
    install_date: Mapped[date] = mapped_column(Date)
    warranty_end_date: Mapped[date | None] = mapped_column(Date, index=True)
    next_service_date: Mapped[date | None] = mapped_column(Date)
    location: Mapped[str | None] = mapped_column(String(150))
    status: Mapped[str] = mapped_column(String(30), default="Ажиллаж байгаа")
    manual_url: Mapped[str | None] = mapped_column(Text)

    customer: Mapped[Customer] = relationship(back_populates="devices")
    tickets: Mapped[list["ServiceTicket"]] = relationship(
        back_populates="device", order_by="ServiceTicket.reported_date.desc()"
    )


class ServiceTicket(Base):
    """
    Засвар үйлчилгээний дуудлага (service ticket).

    Дуудлага бүр нэг төхөөрөмжтэй холбогдож, гэмтлийн тайлбар, онош, хийсэн
    ажил, сольсон сэлбэг, гүйцэтгэсэн инженерийг хадгална. Ингэснээр
    инженер газар дээр очихдоо төхөөрөмжийн өмнөх түүхийг нэг дороос харна.
    """

    __tablename__ = "service_ticket"

    ticket_id: Mapped[int] = mapped_column(primary_key=True)
    device_id: Mapped[int] = mapped_column(ForeignKey("device.device_id", ondelete="RESTRICT"), index=True)
    reported_date: Mapped[date] = mapped_column(Date)
    problem_description: Mapped[str] = mapped_column(Text)
    diagnosis: Mapped[str | None] = mapped_column(Text)
    action_taken: Mapped[str | None] = mapped_column(Text)
    parts_used: Mapped[str | None] = mapped_column(String(300))
    technician: Mapped[str | None] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(20), default="Нээлттэй", index=True)
    closed_date: Mapped[date | None] = mapped_column(Date)

    device: Mapped[Device] = relationship(back_populates="tickets")


class User(Base):
    """
    Системд нэвтрэх ажилтан.

    Нууц үгийг хэзээ ч ил хэлбэрээр хадгалахгүй, зөвхөн PBKDF2 хэш болон
    давсыг (salt) хадгална. `role` талбар нь эрхийн ялгаатай удирдлагад
    ашиглагдана: `admin` бүх үйлдэл, `engineer` бүртгэх, засах эрхтэй.
    """

    __tablename__ = "app_user"

    user_id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(60), unique=True, index=True)
    full_name: Mapped[str | None] = mapped_column(String(120))
    password_hash: Mapped[str] = mapped_column(String(255))
    role: Mapped[str] = mapped_column(String(20), default="engineer")
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now())
