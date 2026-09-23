"""
Нэвтрэлтгүй нийтийн API: QR код ба төхөөрөмжийн товч паспорт.

    GET /api/public/config             — байгууллагын нэр, сервисийн утас
    GET /api/public/devices/{code}     — QR уншуулахад харагдах паспорт
    GET /api/public/qr/{code}.svg      — хэвлэхэд зориулсан QR зураг (SVG)

Эмнэлгийн ажилтан төхөөрөмж дээрх QR кодыг утсаараа уншуулахад
системийн эрхгүйгээр ч төхөөрөмжийн үндсэн мэдээлэл, баталгаа, гарын
авлага, сервисийн утсыг харна. Харилцагчийн холбоо барих мэдээлэл болон
засварын дэлгэрэнгүй тэмдэглэлийг энд ил гаргахгүй.
"""
import io

import qrcode
import qrcode.image.svg
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import schemas
from ..config import get_settings
from ..database import get_db
from ..models import Device
from ..services import days_until, warranty_state

router = APIRouter(prefix="/api/public", tags=["Нийтийн"])
settings = get_settings()


def passport_url(code: str) -> str:
    """QR кодод бичигдэх, тухайн төхөөрөмжийн нийтийн паспортын бүтэн хаяг."""
    return f"{settings.public_base_url.rstrip('/')}/passport.html?code={code}"


@router.get("/config")
def public_config():
    """Frontend-д шаардлагатай нийтийн тохиргоог буцаана."""
    return {
        "company_name": settings.company_name,
        "service_phone": settings.service_phone,
        "public_base_url": settings.public_base_url,
    }


@router.get("/devices/{code}", response_model=schemas.PublicPassportOut)
def public_passport(code: str, db: Session = Depends(get_db)):
    """
    QR код уншуулахад харагдах төхөөрөмжийн товч паспортыг буцаана.

    Засварын түүхээс зөвхөн тоо болон сүүлийн үйлчилгээний огноог өгнө.
    """
    device = db.scalar(
        select(Device)
        .options(selectinload(Device.customer), selectinload(Device.tickets))
        .where(Device.device_code == code.upper())
    )
    if device is None:
        raise HTTPException(status_code=404, detail="Төхөөрөмж олдсонгүй.")
    left = days_until(device.warranty_end_date)
    return schemas.PublicPassportOut(
        device_code=device.device_code,
        category=device.category,
        brand=device.brand,
        model=device.model,
        serial_number=device.serial_number,
        customer_name=device.customer.organization_name,
        location=device.location,
        install_date=device.install_date,
        warranty_end_date=device.warranty_end_date,
        warranty_days_left=left,
        warranty_state=warranty_state(left),
        next_service_date=device.next_service_date,
        status=device.status,
        manual_url=device.manual_url,
        ticket_count=len(device.tickets),
        last_service_date=device.tickets[0].reported_date if device.tickets else None,
        company_name=settings.company_name,
        service_phone=settings.service_phone,
    )


@router.get("/qr/{code}.svg")
def qr_svg(code: str, db: Session = Depends(get_db)):
    """
    Төхөөрөмжийн паспорт руу заасан QR кодыг вектор (SVG) хэлбэрээр үүсгэнэ.

    SVG нь ямар ч хэмжээгээр хэвлэхэд бүдгэрэхгүй. Шошго гэмтсэн ч
    уншигдах боломжтой байлгахын тулд алдаа засах M түвшнийг (≈15%) ашиглана.
    """
    code = code.upper()
    if db.scalar(select(Device.device_id).where(Device.device_code == code)) is None:
        raise HTTPException(status_code=404, detail="Төхөөрөмж олдсонгүй.")
    qr = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=2,
        image_factory=qrcode.image.svg.SvgPathImage,
    )
    qr.add_data(passport_url(code))
    qr.make(fit=True)
    buffer = io.BytesIO()
    qr.make_image().save(buffer)
    return Response(
        content=buffer.getvalue(),
        media_type="image/svg+xml",
        headers={"Cache-Control": "public, max-age=86400"},
    )
