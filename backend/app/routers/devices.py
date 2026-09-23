"""
Төхөөрөмжийн паспортын API.

    GET    /api/devices                — хайлт, шүүлттэй жагсаалт
    GET    /api/devices/{code}         — паспорт ба засварын бүрэн түүх
    POST   /api/devices                — шинээр бүртгэх (код автоматаар)
    PUT    /api/devices/{code}         — засах
    DELETE /api/devices/{code}         — устгах (зөвхөн админ)
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from .. import schemas
from ..database import get_db
from ..models import Customer, Device
from ..security import get_current_user, require_admin
from ..services import device_to_out, next_device_code, ticket_to_out

router = APIRouter(prefix="/api/devices", tags=["Төхөөрөмж"], dependencies=[Depends(get_current_user)])


def _get_or_404(db: Session, code: str) -> Device:
    """Төхөөрөмжийг QR код дээрх кодоор нь хайж, олдохгүй бол 404 өгнө."""
    device = db.scalar(
        select(Device)
        .options(selectinload(Device.customer), selectinload(Device.tickets))
        .where(Device.device_code == code.upper())
    )
    if device is None:
        raise HTTPException(status_code=404, detail="Төхөөрөмж олдсонгүй.")
    return device


def _check_unique_serial(db: Session, serial: str, exclude_id: int | None = None) -> None:
    """
    Серийн дугаар давхардсан эсэхийг том, жижиг үсэг ялгахгүйгээр шалгана.

    Өгөгдлийн сангийн UNIQUE нөхцөлөөс гадна энд урьдчилан шалгаснаар
    хэрэглэгчид ойлгомжтой, аль төхөөрөмжтэй давхцсаныг заасан алдаа өгнө.
    """
    stmt = select(Device).where(func.lower(Device.serial_number) == serial.lower())
    if exclude_id is not None:
        stmt = stmt.where(Device.device_id != exclude_id)
    dup = db.scalar(stmt)
    if dup:
        raise HTTPException(
            status_code=409,
            detail=f"Энэ серийн дугаар {dup.device_code} кодтой төхөөрөмжид бүртгэгдсэн байна.",
        )


def _check_customer(db: Session, customer_id: int) -> None:
    """Сонгосон харилцагч бодитоор байгаа эсэхийг шалгана."""
    if db.get(Customer, customer_id) is None:
        raise HTTPException(status_code=422, detail="Сонгосон харилцагч бүртгэлд алга.")


@router.get("", response_model=list[schemas.DeviceOut])
def list_devices(
    q: str | None = Query(default=None, description="Код, серийн дугаар, загвар, харилцагчаар хайх"),
    warranty: Literal["all", "valid", "soon", "expired"] = "all",
    db: Session = Depends(get_db),
):
    """
    Төхөөрөмжийн жагсаалтыг хайлт болон баталгааны шүүлттэй буцаана.

    Текст хайлтыг SQL түвшинд (ILIKE) хийж, баталгааны шүүлтийг тооцоолсон
    үлдсэн хоногоор гүйцэтгэнэ. Шинээр суурилуулсан нь эхэндээ гарна.
    """
    stmt = select(Device).join(Customer).options(selectinload(Device.customer))
    if q:
        pattern = f"%{q.strip()}%"
        stmt = stmt.where(or_(
            Device.device_code.ilike(pattern),
            Device.serial_number.ilike(pattern),
            Device.model.ilike(pattern),
            Device.brand.ilike(pattern),
            Device.category.ilike(pattern),
            Device.location.ilike(pattern),
            Customer.organization_name.ilike(pattern),
        ))
    devices = [device_to_out(d) for d in db.scalars(stmt.order_by(Device.install_date.desc())).all()]

    def keep(d: schemas.DeviceOut) -> bool:
        left = d.warranty_days_left
        if warranty == "valid":
            return left is not None and left >= 0
        if warranty == "soon":
            return left is not None and 0 <= left <= 30
        if warranty == "expired":
            return left is not None and left < 0
        return True

    return [d for d in devices if keep(d)]


@router.get("/{code}", response_model=schemas.DeviceDetailOut)
def get_device(code: str, db: Session = Depends(get_db)):
    """Төхөөрөмжийн паспорт, харилцагчийн холбоо барих мэдээлэл, засварын түүхийг буцаана."""
    device = _get_or_404(db, code)
    base = device_to_out(device)
    return schemas.DeviceDetailOut(
        **base.model_dump(),
        customer_contact=device.customer.contact_person,
        customer_phone=device.customer.phone,
        tickets=[ticket_to_out(t) for t in device.tickets],
    )


@router.post("", response_model=schemas.DeviceOut, status_code=201)
def create_device(data: schemas.DeviceIn, db: Session = Depends(get_db)):
    """
    Шинэ төхөөрөмж бүртгэж, QR кодод ашиглах давтагдашгүй кодыг онооно.

    Бүртгэхээс өмнө харилцагч байгаа эсэх, серийн дугаар давхардсан
    эсэхийг шалгана.
    """
    _check_customer(db, data.customer_id)
    _check_unique_serial(db, data.serial_number)
    device = Device(**data.model_dump(), device_code=next_device_code(db))
    db.add(device)
    db.commit()
    return device_to_out(_get_or_404(db, device.device_code))


@router.put("/{code}", response_model=schemas.DeviceOut)
def update_device(code: str, data: schemas.DeviceIn, db: Session = Depends(get_db)):
    """Төхөөрөмжийн паспортын мэдээллийг шинэчилнэ. Код нь өөрчлөгдөхгүй."""
    device = _get_or_404(db, code)
    _check_customer(db, data.customer_id)
    _check_unique_serial(db, data.serial_number, exclude_id=device.device_id)
    for key, value in data.model_dump().items():
        setattr(device, key, value)
    db.commit()
    db.refresh(device)
    return device_to_out(device)


@router.delete("/{code}", status_code=204, dependencies=[Depends(require_admin)])
def delete_device(code: str, db: Session = Depends(get_db)):
    """
    Төхөөрөмжийг бүртгэлээс устгана.

    Засварын түүхтэй төхөөрөмжийг устгавал түүх алдагдах тул хориглож,
    оронд нь төлөвийг «Ашиглалтаас гарсан» болгохыг зөвлөнө.
    """
    device = _get_or_404(db, code)
    if device.tickets:
        raise HTTPException(
            status_code=409,
            detail="Засварын түүхтэй төхөөрөмжийг устгахгүй. Төлөвийг «Ашиглалтаас гарсан» болгоно уу.",
        )
    db.delete(device)
    db.commit()
