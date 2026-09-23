"""
Өгөгдөл экспортлох API (Google Sheets, Excel рүү).

    GET /api/export/{customers|devices|tickets}.csv

CSV файл UTF-8 BOM-той тул Excel болон Google Sheets кирилл үсгийг
алдаагүй уншина.
"""
import csv
import io
from datetime import date
from typing import Literal

from fastapi import APIRouter, Depends
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from ..database import get_db
from ..models import Customer, Device, ServiceTicket
from ..security import get_current_user

router = APIRouter(prefix="/api/export", tags=["Экспорт"], dependencies=[Depends(get_current_user)])


@router.get("/{kind}.csv")
def export_csv(kind: Literal["customers", "devices", "tickets"], db: Session = Depends(get_db)):
    """
    Сонгосон хүснэгтийг CSV файл болгон татуулна.

    Төхөөрөмж ба дуудлагын файлд ID-аас гадна хүнд ойлгомжтой код,
    харилцагчийн нэрийг нэмж оруулсан тул файлыг шууд тайланд ашиглаж болно.
    """
    buffer = io.StringIO()
    writer = csv.writer(buffer)

    if kind == "customers":
        writer.writerow(["customer_id", "organization_name", "address", "contact_person", "phone"])
        for c in db.scalars(select(Customer).order_by(Customer.customer_id)):
            writer.writerow([c.customer_id, c.organization_name, c.address, c.contact_person, c.phone])
    elif kind == "devices":
        writer.writerow(["device_code", "customer", "category", "brand", "model", "serial_number",
                         "install_date", "warranty_end_date", "next_service_date", "location", "status"])
        stmt = select(Device).options(selectinload(Device.customer)).order_by(Device.device_code)
        for d in db.scalars(stmt):
            writer.writerow([d.device_code, d.customer.organization_name, d.category, d.brand, d.model,
                             d.serial_number, d.install_date, d.warranty_end_date, d.next_service_date,
                             d.location, d.status])
    else:
        writer.writerow(["ticket_id", "device_code", "reported_date", "problem_description", "diagnosis",
                         "action_taken", "parts_used", "technician", "status", "closed_date"])
        stmt = select(ServiceTicket).options(selectinload(ServiceTicket.device)).order_by(ServiceTicket.ticket_id)
        for t in db.scalars(stmt):
            writer.writerow([t.ticket_id, t.device.device_code, t.reported_date, t.problem_description,
                             t.diagnosis, t.action_taken, t.parts_used, t.technician, t.status, t.closed_date])

    filename = f"medjack_{kind}_{date.today():%Y-%m-%d}.csv"
    return Response(
        content="\ufeff" + buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
