"""
Удирдлагын самбарын API.

    GET /api/dashboard  — үндсэн үзүүлэлт, 30/14/7 хоногийн сануулга,
                          сүүлийн 6 сарын статистик
"""
from datetime import date

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from .. import schemas
from ..database import get_db
from ..models import Device, ServiceTicket
from ..security import get_current_user
from ..services import STALE_TICKET_DAYS, build_reminders, days_until, monthly_stats

router = APIRouter(prefix="/api/dashboard", tags=["Самбар"], dependencies=[Depends(get_current_user)])


@router.get("", response_model=schemas.DashboardOut)
def dashboard(db: Session = Depends(get_db)):
    """
    Самбарт шаардлагатай бүх үзүүлэлтийг нэг хүсэлтээр тооцож буцаана.

    - ашиглалтад байгаа болон баталгаат хугацаатай төхөөрөмжийн тоо;
    - нээлттэй дуудлага, түүний дотор 3-аас дээш хоног хүлээгдсэн дуудлага;
    - хаагдсан дуудлагыг шийдвэрлэсэн дундаж хугацаа (хоногоор);
    - сануулгын жагсаалт ба сарын статистик.
    """
    today = date.today()
    devices = db.scalars(select(Device).options(selectinload(Device.customer))).all()
    tickets = db.scalars(select(ServiceTicket)).all()

    active = [d for d in devices if d.status != "Ашиглалтаас гарсан"]
    under_warranty = sum(
        1 for d in active
        if d.warranty_end_date is not None and days_until(d.warranty_end_date, today) >= 0
    )
    open_tickets = [t for t in tickets if t.status != "Хаагдсан"]
    stale = sum(1 for t in open_tickets if (today - t.reported_date).days > STALE_TICKET_DAYS)
    durations = [(t.closed_date - t.reported_date).days for t in tickets if t.status == "Хаагдсан" and t.closed_date]

    return schemas.DashboardOut(
        today=today,
        active_devices=len(active),
        under_warranty=under_warranty,
        open_tickets=len(open_tickets),
        stale_tickets=stale,
        avg_close_days=round(sum(durations) / len(durations), 1) if durations else None,
        reminders=build_reminders(list(devices), today),
        months=monthly_stats(list(devices), list(tickets), today),
    )
