"""
Бизнес логикийн давхарга.

HTTP-ээс хамааралгүй цэвэр функцууд энд байрлана: баталгааны төлөв
тодорхойлох, 30/14/7 хоногийн сануулга гаргах, мэдэгдлийн текст бэлтгэх,
ORM объектыг API-ийн хариу болгон хувиргах. Ингэж тусгаарласнаар логикийг
вэб сервергүйгээр unit test-ээр шалгах боломжтой болно.
"""
from collections import Counter
from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from . import schemas
from .config import get_settings
from .models import Device, ServiceTicket

settings = get_settings()

REMINDER_WINDOW_WARRANTY = 30  # баталгааны сануулга эхлэх хоног
REMINDER_WINDOW_SERVICE = 14   # төлөвлөгөөт үйлчилгээний сануулга эхлэх хоног
STALE_TICKET_DAYS = 3          # хариу өгөөгүй удсан дуудлагын босго


def days_until(target: date | None, today: date | None = None) -> int | None:
    """Өгөгдсөн огноо хүртэл үлдсэн хоногийг тооцно. Өнгөрсөн бол сөрөг утгатай."""
    if target is None:
        return None
    return (target - (today or date.today())).days


def warranty_state(days_left: int | None) -> str:
    """
    Баталгааны үлдсэн хоногоос хүнд ойлгомжтой төлөвийг гаргана.

    Энэ ангилал нь frontend дээр өнгөөр ялгагдана:
    хүчинтэй (ногоон), 30 хоногт дуусах (шар), 7 хоногт дуусах (улаан).
    """
    if days_left is None:
        return "Тодорхойгүй"
    if days_left < 0:
        return "Дууссан"
    if days_left <= 7:
        return "7 хоногт дуусна"
    if days_left <= 30:
        return "30 хоногт дуусна"
    return "Хүчинтэй"


def reminder_tier(days_left: int) -> str:
    """Сануулгын түвшинг 7, 14, 30 хоногийн гурван шатлалд хуваана."""
    if days_left <= 7:
        return "7"
    if days_left <= 14:
        return "14"
    return "30"


def next_device_code(db: Session) -> str:
    """
    Дараагийн төхөөрөмжийн кодыг (MJ-0001, MJ-0002, …) үүсгэнэ.

    Одоо байгаа кодуудын хамгийн их дугаарыг олж нэгийг нэмнэ. Устгагдсан
    кодыг дахин ашиглахгүй тул QR шошго хоорондоо хэзээ ч давхцахгүй.
    """
    codes = db.scalars(select(Device.device_code)).all()
    numbers = [int(c.split("-")[-1]) for c in codes if c.split("-")[-1].isdigit()]
    return f"MJ-{(max(numbers, default=0) + 1):04d}"


def device_to_out(device: Device, today: date | None = None) -> schemas.DeviceOut:
    """ORM төхөөрөмжийг баталгааны тооцоолсон талбаруудтай хамт API хариу болгоно."""
    left = days_until(device.warranty_end_date, today)
    return schemas.DeviceOut(
        device_id=device.device_id,
        device_code=device.device_code,
        customer_id=device.customer_id,
        customer_name=device.customer.organization_name if device.customer else None,
        category=device.category,
        brand=device.brand,
        model=device.model,
        serial_number=device.serial_number,
        install_date=device.install_date,
        warranty_end_date=device.warranty_end_date,
        next_service_date=device.next_service_date,
        location=device.location,
        status=device.status,
        manual_url=device.manual_url,
        warranty_days_left=left,
        warranty_state=warranty_state(left),
    )


def ticket_to_out(ticket: ServiceTicket) -> schemas.TicketOut:
    """ORM дуудлагыг төхөөрөмжийн код, загвар, харилцагчийн нэртэй хамт буцаана."""
    device = ticket.device
    return schemas.TicketOut(
        ticket_id=ticket.ticket_id,
        device_id=ticket.device_id,
        device_code=device.device_code if device else None,
        device_model=device.model if device else None,
        customer_name=device.customer.organization_name if device and device.customer else None,
        reported_date=ticket.reported_date,
        problem_description=ticket.problem_description,
        diagnosis=ticket.diagnosis,
        action_taken=ticket.action_taken,
        parts_used=ticket.parts_used,
        technician=ticket.technician,
        status=ticket.status,
        closed_date=ticket.closed_date,
    )


def sync_device_status(db: Session, device: Device) -> None:
    """
    Төхөөрөмжийн төлөвийг нээлттэй дуудлагатай уялдуулна.

    Нээлттэй дуудлага байвал «Засварт», бүгд хаагдвал «Ажиллаж байгаа»
    болгоно. «Ашиглалтаас гарсан» төхөөрөмжийн төлөвийг өөрчлөхгүй.
    """
    if device.status == "Ашиглалтаас гарсан":
        return
    open_count = db.scalar(
        select(func.count())
        .select_from(ServiceTicket)
        .where(ServiceTicket.device_id == device.device_id, ServiceTicket.status != "Хаагдсан")
    )
    device.status = "Засварт" if open_count else "Ажиллаж байгаа"


def build_message(kind: str, device: Device, target: date, days_left: int) -> str:
    """
    Харилцагчид SMS, WhatsApp, Facebook-ээр илгээх мэдэгдлийн текстийг бэлтгэнэ.

    Текст нь хүлээн авагчийн нэр, төхөөрөмжийн загвар, серийн дугаар,
    огноо болон сервисийн утсыг агуулж, илгээхэд бэлэн байдлаар гарна.
    """
    customer = device.customer
    greeting = f"Сайн байна уу, {customer.contact_person or 'эрхэм харилцагч'}."
    name = " ".join(x for x in (device.brand, device.model) if x)
    phone = f" · {settings.service_phone}" if settings.service_phone else ""
    when = target.strftime("%Y.%m.%d")
    if kind == "warranty":
        body = (
            f"{customer.organization_name}-д суурилуулсан {name} (SN {device.serial_number}) "
            f"төхөөрөмжийн баталгаат хугацаа {when}-нд, {days_left} хоногийн дараа дуусна. "
            "Баталгаат хугацаанд үнэ төлбөргүй үзлэг хийлгэх бол бидэнтэй холбогдоно уу."
        )
    elif days_left < 0:
        body = (
            f"{name} (SN {device.serial_number}) төхөөрөмжийн төлөвлөгөөт үйлчилгээ {when}-нд "
            "хийгдэх ёстой байсан бөгөөд хугацаа хэтэрсэн байна. Тохиромжтой цагаа мэдэгдэнэ үү."
        )
    else:
        body = (
            f"{name} (SN {device.serial_number}) төхөөрөмжийн төлөвлөгөөт үйлчилгээ {when}-нд "
            "хийгдэнэ. Тохиромжтой цагаа мэдэгдэнэ үү."
        )
    return f"{greeting}\n{body}\n{settings.company_name}{phone}"


def build_reminders(devices: list[Device], today: date | None = None) -> list[schemas.ReminderOut]:
    """
    Ашиглалтад байгаа төхөөрөмжүүдээс сануулгын жагсаалт гаргана.

    Хоёр төрлийн сануулга үүснэ:
      1. Баталгаат хугацаа 30 хоногийн дотор дуусах төхөөрөмж;
      2. Төлөвлөгөөт үйлчилгээ 14 хоногийн дотор болох эсвэл хоцорсон төхөөрөмж.
    Үр дүнг хамгийн яаралтайгаас нь эхлэн эрэмбэлнэ.
    """
    today = today or date.today()
    out: list[schemas.ReminderOut] = []
    for d in devices:
        if d.status == "Ашиглалтаас гарсан":
            continue
        common = dict(
            device_code=d.device_code,
            device_model=" ".join(x for x in (d.brand, d.model) if x),
            serial_number=d.serial_number,
            customer_name=d.customer.organization_name,
            customer_contact=d.customer.contact_person,
            customer_phone=d.customer.phone,
        )
        w = days_until(d.warranty_end_date, today)
        if w is not None and 0 <= w <= REMINDER_WINDOW_WARRANTY:
            out.append(schemas.ReminderOut(
                **common, kind="warranty", title="Баталгаат хугацаа дуусна",
                target_date=d.warranty_end_date, days_left=w, tier=reminder_tier(w),
                message=build_message("warranty", d, d.warranty_end_date, w),
            ))
        s = days_until(d.next_service_date, today)
        if s is not None and s <= REMINDER_WINDOW_SERVICE:
            out.append(schemas.ReminderOut(
                **common, kind="service",
                title="Төлөвлөгөөт үйлчилгээ хоцорсон" if s < 0 else "Төлөвлөгөөт үйлчилгээ",
                target_date=d.next_service_date, days_left=s, tier=reminder_tier(s),
                message=build_message("service", d, d.next_service_date, s),
            ))
    return sorted(out, key=lambda r: r.days_left)


def monthly_stats(devices: list[Device], tickets: list[ServiceTicket], today: date | None = None,
                  months: int = 6) -> list[schemas.MonthStat]:
    """
    Сүүлийн N сарын суурилуулалт ба засварын дуудлагын тоог тооцно.

    Удирдлагын сарын тайлан (тайлангийн 5.3-ын 5-р заалт) болон самбарын
    графикт ашиглагдана. Өгөгдөлгүй сар ч 0 утгатай гарна.
    """
    today = today or date.today()
    keys = []
    y, m = today.year, today.month
    for _ in range(months):
        keys.append(f"{y:04d}-{m:02d}")
        y, m = (y - 1, 12) if m == 1 else (y, m - 1)
    keys.reverse()
    installs = Counter(d.install_date.strftime("%Y-%m") for d in devices if d.install_date)
    calls = Counter(t.reported_date.strftime("%Y-%m") for t in tickets if t.reported_date)
    return [schemas.MonthStat(month=k, installs=installs[k], tickets=calls[k]) for k in keys]
