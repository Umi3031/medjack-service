"""
Засвар үйлчилгээний дуудлагын (service ticket) API.

    GET    /api/tickets            — жагсаалт (төлөвөөр шүүх)
    POST   /api/tickets            — дуудлага бүртгэх
    PUT    /api/tickets/{id}       — шинэчлэх, хаах
    DELETE /api/tickets/{id}       — устгах (зөвхөн админ)

Дуудлага нээгдэх, хаагдах бүрт холбогдох төхөөрөмжийн төлөв автоматаар
«Засварт» ↔ «Ажиллаж байгаа» хооронд шилжинэ.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import schemas
from ..database import get_db
from ..models import Device, ServiceTicket
from ..security import get_current_user, require_admin
from ..services import sync_device_status, ticket_to_out

router = APIRouter(prefix="/api/tickets", tags=["Засвар үйлчилгээ"], dependencies=[Depends(get_current_user)])

_LOAD = (selectinload(ServiceTicket.device).selectinload(Device.customer),)


def _get_or_404(db: Session, ticket_id: int) -> ServiceTicket:
    """Дуудлагыг дугаараар нь хайж, олдохгүй бол 404 алдаа өгнө."""
    ticket = db.scalar(select(ServiceTicket).options(*_LOAD).where(ServiceTicket.ticket_id == ticket_id))
    if ticket is None:
        raise HTTPException(status_code=404, detail="Дуудлага олдсонгүй.")
    return ticket


def _get_device(db: Session, device_id: int) -> Device:
    """Дуудлагад холбох төхөөрөмж байгаа эсэхийг шалгана."""
    device = db.get(Device, device_id)
    if device is None:
        raise HTTPException(status_code=422, detail="Сонгосон төхөөрөмж бүртгэлд алга.")
    return device


@router.get("", response_model=list[schemas.TicketOut])
def list_tickets(status: Literal["open", "closed", "all"] = "open", db: Session = Depends(get_db)):
    """
    Дуудлагын жагсаалтыг хамгийн сүүлд ирснээс нь эхлэн буцаана.

    `open` нь «Нээлттэй» болон «Хийгдэж байгаа» дуудлагыг, `closed` нь
    зөвхөн «Хаагдсан»-ыг, `all` нь бүгдийг харуулна.
    """
    stmt = select(ServiceTicket).options(*_LOAD)
    if status == "open":
        stmt = stmt.where(ServiceTicket.status != "Хаагдсан")
    elif status == "closed":
        stmt = stmt.where(ServiceTicket.status == "Хаагдсан")
    stmt = stmt.order_by(ServiceTicket.reported_date.desc(), ServiceTicket.ticket_id.desc())
    return [ticket_to_out(t) for t in db.scalars(stmt).all()]


@router.post("", response_model=schemas.TicketOut, status_code=201)
def create_ticket(data: schemas.TicketIn, db: Session = Depends(get_db)):
    """Шинэ засварын дуудлага бүртгэж, төхөөрөмжийн төлөвийг шинэчилнэ."""
    device = _get_device(db, data.device_id)
    ticket = ServiceTicket(**data.model_dump())
    db.add(ticket)
    db.flush()  # шинэ дуудлагыг төлөв тооцоход харагдуулах
    sync_device_status(db, device)
    db.commit()
    return ticket_to_out(_get_or_404(db, ticket.ticket_id))


@router.put("/{ticket_id}", response_model=schemas.TicketOut)
def update_ticket(ticket_id: int, data: schemas.TicketIn, db: Session = Depends(get_db)):
    """
    Дуудлагыг шинэчилнэ: онош, хийсэн ажил, сэлбэг нэмэх эсвэл хаах.

    Дуудлагыг өөр төхөөрөмж рүү шилжүүлсэн бол хуучин, шинэ хоёр
    төхөөрөмжийн төлөвийг хоёуланг нь дахин тооцно.
    """
    ticket = _get_or_404(db, ticket_id)
    old_device = ticket.device
    new_device = _get_device(db, data.device_id)
    for key, value in data.model_dump().items():
        setattr(ticket, key, value)
    db.flush()
    sync_device_status(db, new_device)
    if old_device.device_id != new_device.device_id:
        sync_device_status(db, old_device)
    db.commit()
    db.expire(ticket)  # холбоос (ticket.device) шинэ төхөөрөмжөөр дахин ачаалагдана
    return ticket_to_out(_get_or_404(db, ticket_id))


@router.delete("/{ticket_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_ticket(ticket_id: int, db: Session = Depends(get_db)):
    """Буруу бүртгэгдсэн дуудлагыг устгаж, төхөөрөмжийн төлөвийг сэргээнэ."""
    ticket = _get_or_404(db, ticket_id)
    device = ticket.device
    db.delete(ticket)
    db.flush()
    sync_device_status(db, device)
    db.commit()
