"""
API-ийн оролт, гаралтын өгөгдлийн схем (Pydantic).

`...In` классууд нь клиентээс ирэх өгөгдлийг шалгана: заавал бөглөх
талбар, урт, зөвшөөрөгдсөн утга, огнооны логик. `...Out` классууд нь
клиент рүү буцаах JSON-ийн бүтцийг тогтооно. Ингэснээр өгөгдлийн сангийн
дотоод бүтэц (жишээ нь нууц үгийн хэш) гадагш алдагдахгүй.
"""
from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DeviceStatus = Literal["Ажиллаж байгаа", "Засварт", "Ашиглалтаас гарсан"]
TicketStatus = Literal["Нээлттэй", "Хийгдэж байгаа", "Хаагдсан"]


def _blank_to_none(v):
    """Хоосон мөрийг `None` болгож, өгөгдлийн санд '' биш NULL хадгална."""
    if isinstance(v, str):
        v = v.strip()
        return v or None
    return v


# ---------------------------------------------------------------- Нэвтрэлт
class LoginIn(BaseModel):
    """Нэвтрэх хүсэлт: хэрэглэгчийн нэр ба нууц үг."""

    username: str = Field(min_length=1, max_length=60)
    password: str = Field(min_length=1, max_length=200)


class TokenOut(BaseModel):
    """Амжилттай нэвтэрсний дараа олгох JWT токен ба хэрэглэгчийн мэдээлэл."""

    access_token: str
    token_type: str = "bearer"
    username: str
    full_name: str | None
    role: str


class UserOut(BaseModel):
    """Одоо нэвтэрсэн хэрэглэгчийн нийтэд ил мэдээлэл."""

    model_config = ConfigDict(from_attributes=True)
    username: str
    full_name: str | None
    role: str


# --------------------------------------------------------------- Харилцагч
class CustomerIn(BaseModel):
    """Харилцагч нэмэх, засах үед ирэх өгөгдөл."""

    organization_name: str = Field(min_length=2, max_length=200)
    address: str | None = Field(default=None, max_length=300)
    contact_person: str | None = Field(default=None, max_length=120)
    phone: str | None = Field(default=None, max_length=30)

    clean_optional = field_validator("address", "contact_person", "phone", mode="before")(_blank_to_none)


class CustomerOut(CustomerIn):
    """Харилцагчийн мэдээлэл ба түүнд бүртгэлтэй төхөөрөмжийн тоо."""

    model_config = ConfigDict(from_attributes=True)
    customer_id: int
    device_count: int = 0


# -------------------------------------------------------------- Төхөөрөмж
class DeviceIn(BaseModel):
    """
    Төхөөрөмж нэмэх, засах үед ирэх өгөгдөл.

    Серийн дугаарын илүүдэл зайг арилгаж, баталгаа дуусах огноо
    суурилуулсан огнооноос өмнө байвал алдаа буцаана.
    """

    customer_id: int
    category: str = Field(min_length=2, max_length=80)
    brand: str | None = Field(default=None, max_length=80)
    model: str = Field(min_length=1, max_length=120)
    serial_number: str = Field(min_length=3, max_length=80)
    install_date: date
    warranty_end_date: date | None = None
    next_service_date: date | None = None
    location: str | None = Field(default=None, max_length=150)
    status: DeviceStatus = "Ажиллаж байгаа"
    manual_url: str | None = None

    clean_optional = field_validator(
        "brand", "location", "manual_url", "warranty_end_date", "next_service_date", mode="before"
    )(_blank_to_none)

    @field_validator("serial_number")
    @classmethod
    def strip_serial(cls, v: str) -> str:
        """Серийн дугаарыг хайлтад тохиромжтой болгож, хоосон зайг арилгана."""
        return v.strip()

    @model_validator(mode="after")
    def check_dates(self):
        """Баталгааны хугацаа суурилуулалтаас өмнө дуусах логик алдааг хориглоно."""
        if self.warranty_end_date and self.warranty_end_date < self.install_date:
            raise ValueError("Баталгаа дуусах огноо суурилуулсан огнооноос өмнө байж болохгүй.")
        return self


class DeviceOut(DeviceIn):
    """Төхөөрөмжийн паспорт: үндсэн мэдээлэл дээр тооцоолсон талбаруудыг нэмнэ."""

    model_config = ConfigDict(from_attributes=True)
    device_id: int
    device_code: str
    customer_name: str | None = None
    warranty_days_left: int | None = None
    warranty_state: str = "Тодорхойгүй"


# ------------------------------------------------------- Засварын дуудлага
class TicketIn(BaseModel):
    """
    Засварын дуудлага бүртгэх, шинэчлэх үед ирэх өгөгдөл.

    Дуудлагыг «Хаагдсан» төлөвт шилжүүлэхэд хийсэн ажлыг заавал бичих
    ёстой. Хаасан огноо өгөөгүй бол өнөөдрийн огноог автоматаар онооно.
    """

    device_id: int
    reported_date: date
    problem_description: str = Field(min_length=3)
    diagnosis: str | None = None
    action_taken: str | None = None
    parts_used: str | None = Field(default=None, max_length=300)
    technician: str | None = Field(default=None, max_length=120)
    status: TicketStatus = "Нээлттэй"
    closed_date: date | None = None

    clean_optional = field_validator(
        "diagnosis", "action_taken", "parts_used", "technician", "closed_date", mode="before"
    )(_blank_to_none)

    @model_validator(mode="after")
    def check_closing(self):
        """Хаагдсан дуудлагын бүрэн бүтэн байдлыг шалгана."""
        if self.status == "Хаагдсан":
            if not self.action_taken:
                raise ValueError("Дуудлагыг хаахын өмнө хийсэн ажлыг бичнэ үү.")
            if self.closed_date is None:
                self.closed_date = date.today()
            if self.closed_date < self.reported_date:
                raise ValueError("Хаасан огноо дуудлага ирсэн огнооноос өмнө байж болохгүй.")
        else:
            self.closed_date = None
        return self


class TicketOut(TicketIn):
    """Дуудлагын мэдээлэл ба холбогдох төхөөрөмж, харилцагчийн нэр."""

    model_config = ConfigDict(from_attributes=True)
    ticket_id: int
    device_code: str | None = None
    device_model: str | None = None
    customer_name: str | None = None


class DeviceDetailOut(DeviceOut):
    """Паспортын дэлгэрэнгүй: төхөөрөмж ба түүний засварын бүрэн түүх."""

    customer_contact: str | None = None
    customer_phone: str | None = None
    tickets: list[TicketOut] = []


# ---------------------------------------------------- Самбар ба сануулга
class ReminderOut(BaseModel):
    """Нэг сануулга: аль төхөөрөмж, ямар төрлийн, хэд хоног үлдсэн."""

    device_code: str
    device_model: str
    serial_number: str
    customer_name: str
    customer_contact: str | None
    customer_phone: str | None
    kind: Literal["warranty", "service"]
    title: str
    target_date: date
    days_left: int
    tier: Literal["7", "14", "30"]
    message: str


class MonthStat(BaseModel):
    """Сар бүрийн суурилуулалт ба засварын дуудлагын тоо."""

    month: str
    installs: int
    tickets: int


class DashboardOut(BaseModel):
    """Удирдлагын самбарт харуулах нэгдсэн үзүүлэлтүүд."""

    today: date
    active_devices: int
    under_warranty: int
    open_tickets: int
    stale_tickets: int
    avg_close_days: float | None
    reminders: list[ReminderOut]
    months: list[MonthStat]


class PublicPassportOut(BaseModel):
    """
    QR код уншуулахад нэвтрэлгүйгээр харагдах хязгаарлагдмал паспорт.

    Харилцагчийн холбоо барих мэдээлэл, засварын дэлгэрэнгүй тэмдэглэл
    зэрэг нууцлалтай өгөгдлийг энд оруулаагүй.
    """

    device_code: str
    category: str
    brand: str | None
    model: str
    serial_number: str
    customer_name: str
    location: str | None
    install_date: date
    warranty_end_date: date | None
    warranty_days_left: int | None
    warranty_state: str
    next_service_date: date | None
    status: str
    manual_url: str | None
    ticket_count: int
    last_service_date: date | None
    company_name: str
    service_phone: str
