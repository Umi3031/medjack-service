"""
Харилцагч байгууллагын CRUD API.

    GET    /api/customers          — жагсаалт (төхөөрөмжийн тоотой)
    POST   /api/customers          — шинээр бүртгэх
    PUT    /api/customers/{id}     — засах
    DELETE /api/customers/{id}     — устгах (зөвхөн админ)
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import schemas
from ..database import get_db
from ..models import Customer, Device
from ..security import get_current_user, require_admin

router = APIRouter(prefix="/api/customers", tags=["Харилцагч"], dependencies=[Depends(get_current_user)])


def _get_or_404(db: Session, customer_id: int) -> Customer:
    """Харилцагчийг ID-аар хайж, олдохгүй бол 404 алдаа өгнө."""
    customer = db.get(Customer, customer_id)
    if customer is None:
        raise HTTPException(status_code=404, detail="Харилцагч олдсонгүй.")
    return customer


def _to_out(customer: Customer, device_count: int) -> schemas.CustomerOut:
    """ORM объектыг төхөөрөмжийн тоотой хамт API хариу болгоно."""
    return schemas.CustomerOut(
        customer_id=customer.customer_id,
        organization_name=customer.organization_name,
        address=customer.address,
        contact_person=customer.contact_person,
        phone=customer.phone,
        device_count=device_count,
    )


@router.get("", response_model=list[schemas.CustomerOut])
def list_customers(db: Session = Depends(get_db)):
    """
    Бүх харилцагчийг нэрээр нь эрэмбэлж буцаана.

    Төхөөрөмжийн тоог нэг SQL асуулгаар (LEFT JOIN + GROUP BY) тооцдог тул
    харилцагч бүрт тусдаа асуулга илгээх N+1 асуудал үүсэхгүй.
    """
    rows = db.execute(
        select(Customer, func.count(Device.device_id))
        .outerjoin(Device, Device.customer_id == Customer.customer_id)
        .group_by(Customer.customer_id)
        .order_by(Customer.organization_name)
    ).all()
    return [_to_out(c, n) for c, n in rows]


@router.post("", response_model=schemas.CustomerOut, status_code=201)
def create_customer(data: schemas.CustomerIn, db: Session = Depends(get_db)):
    """Шинэ харилцагч бүртгэнэ."""
    customer = Customer(**data.model_dump())
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return _to_out(customer, 0)


@router.put("/{customer_id}", response_model=schemas.CustomerOut)
def update_customer(customer_id: int, data: schemas.CustomerIn, db: Session = Depends(get_db)):
    """Харилцагчийн мэдээллийг бүхэлд нь шинэчилнэ."""
    customer = _get_or_404(db, customer_id)
    for key, value in data.model_dump().items():
        setattr(customer, key, value)
    db.commit()
    return _to_out(customer, len(customer.devices))


@router.delete("/{customer_id}", status_code=204, dependencies=[Depends(require_admin)])
def delete_customer(customer_id: int, db: Session = Depends(get_db)):
    """
    Харилцагчийг устгана.

    Төхөөрөмж бүртгэлтэй харилцагчийг устгавал паспорт болон засварын
    түүх эзэнгүй болох тул ийм тохиолдолд 409 алдаа буцааж хориглоно.
    """
    customer = _get_or_404(db, customer_id)
    if customer.devices:
        raise HTTPException(status_code=409, detail="Төхөөрөмж бүртгэлтэй харилцагчийг устгах боломжгүй.")
    db.delete(customer)
    db.commit()
