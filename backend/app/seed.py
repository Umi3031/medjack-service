"""
Жишээ өгөгдөл оруулах скрипт.

Хамгаалалт болон туршилтад зориулж харилцагч, төхөөрөмж, засварын
дуудлагын жишээг оруулна. Өгөгдлийн сан хоосон үед л ажиллах тул бодит
өгөгдлийг санамсаргүйгээр дарж бичихгүй.

Ажиллуулах:  python -m app.seed
"""
from datetime import date, timedelta

from sqlalchemy import select

from .database import Base, SessionLocal, engine
from .main import ensure_admin
from .models import Customer, Device, ServiceTicket


def run() -> None:
    """
    Хүснэгтүүдийг үүсгэж, хоосон бол жишээ өгөгдлөөр дүүргэнэ.

    Огноонуудыг өнөөдрөөс хамааруулан тооцдог тул скриптийг хэзээ
    ажиллуулсан ч самбар дээр 7, 14, 30 хоногийн сануулгууд харагдана.
    """
    Base.metadata.create_all(bind=engine)
    ensure_admin()
    t = date.today()
    d = lambda n: t + timedelta(days=n)  # noqa: E731  өнөөдрөөс n хоногийн зайтай огноо

    with SessionLocal() as db:
        if db.scalar(select(Customer.customer_id).limit(1)) is not None:
            print("Өгөгдөл аль хэдийн байна. Жишээ өгөгдөл оруулсангүй.")
            return

        c1 = Customer(organization_name="Батсүмбэр сумын Эрүүл мэндийн төв",
                      address="Төв аймаг, Батсүмбэр сум", contact_person="Лабораторийн эрхлэгч")
        c2 = Customer(organization_name="Жишээ клиник А", address="Улаанбаатар, Баянгол дүүрэг",
                      contact_person="Ерөнхий сувилагч")
        c3 = Customer(organization_name="Жишээ лаборатори Б", address="Улаанбаатар, Сүхбаатар дүүрэг",
                      contact_person="Лаборант")
        c4 = Customer(organization_name="Жишээ сумын ЭМТ В", address="Орон нутаг", contact_person="Их эмч")
        db.add_all([c1, c2, c3, c4])
        db.flush()

        rows = [
            ("MJ-0001", c1, "Биохимийн анализатор", None, "Full-auto Chemistry Analyzer", "BCA-2605-0142",
             d(-83), d(282), d(9), "Клиник лаборатори"),
            ("MJ-0002", c2, "ЭКГ аппарат", None, "ECG-912", "E912-24-00871", d(-722), d(6), d(69), "Дотрын кабинет"),
            ("MJ-0003", c2, "Хяналтын монитор", None, "Multi-parameter Monitor 12\"", "PM12-25-3310",
             d(-352), d(13), d(8), "Эрчимт эмчилгээ"),
            ("MJ-0004", c3, "Инкубатор", "FAITHFUL", "DH-360", "FH-DH360-5521", d(-89), d(276), d(94), "Бактериологи"),
            ("MJ-0005", c3, "Биологийн аюулгүйн шүүгээ", "SCITEK", "BSC-1100 II A2", "SCT-BSC-11807",
             d(-89), d(276), d(94), "Бактериологи"),
            ("MJ-0006", c4, "Автоклав", "BIOBASE", "BKM-Z24B", "BB-Z24-60219", d(-166), d(199), d(17), "Ариутгалын өрөө"),
            ("MJ-0007", c4, "ЭКГ аппарат", None, "ECG-912", "E912-23-00412", d(-1227), d(-496), d(-8), "Хүлээн авах"),
            ("MJ-0008", c1, "ЭКГ аппарат", None, "ECG-912", "E912-25-01133", d(-346), d(19), d(111), "Амбулатори"),
        ]
        devices = {}
        for code, cust, cat, brand, model, sn, inst, warr, nxt, loc in rows:
            devices[code] = Device(device_code=code, customer_id=cust.customer_id, category=cat, brand=brand,
                                   model=model, serial_number=sn, install_date=inst, warranty_end_date=warr,
                                   next_service_date=nxt, location=loc, status="Ажиллаж байгаа")
        db.add_all(devices.values())
        db.flush()

        db.add_all([
            ServiceTicket(device_id=devices["MJ-0007"].device_id, reported_date=d(-140),
                          problem_description="Хэвлэгч цаас татахгүй, бичлэг тасалдана",
                          diagnosis="Хэвлэгчийн роликийн элэгдэл",
                          action_taken="Роликийг цэвэрлэж тохируулсан, дулааны толгойг шалгасан",
                          technician="Техникийн инженер", status="Хаагдсан", closed_date=d(-139)),
            ServiceTicket(device_id=devices["MJ-0001"].device_id, reported_date=d(-76),
                          problem_description="Суурилуулалтын дараах тохиргоо: шинжилгээний нэршил, урвалжийн байрлал",
                          diagnosis="Програм дээрх нэршил лабораторийн ажлын дадалтай зөрсөн",
                          action_taken="Тестийн нэршил, урвалжийн байрлалыг жагсаалтаар тулгаж засаж, операторт сургалт өгсөн",
                          technician="Техникийн инженер", status="Хаагдсан", closed_date=d(-75)),
            ServiceTicket(device_id=devices["MJ-0006"].device_id, reported_date=d(-33),
                          problem_description="Даралт зорилтот утгад хүрэх хугацаа уртассан",
                          diagnosis="Хаалганы жийргэвч элэгдсэн",
                          action_taken="Жийргэвчийг сольж, туршилтын мөчлөг ажиллуулсан",
                          parts_used="Хаалганы силикон жийргэвч ×1",
                          technician="Техникийн инженер", status="Хаагдсан", closed_date=d(-32)),
            ServiceTicket(device_id=devices["MJ-0003"].device_id, reported_date=d(-4),
                          problem_description="SpO2 утга тогтворгүй, дохиолол (alarm) давтан дуугарна",
                          diagnosis="Мэдрэгчийн кабелийн холболт сул байж болзошгүй",
                          technician="Техникийн инженер", status="Хийгдэж байгаа"),
        ])
        devices["MJ-0003"].status = "Засварт"
        db.commit()
        print("Жишээ өгөгдөл амжилттай орлоо: 4 харилцагч, 8 төхөөрөмж, 4 дуудлага.")


if __name__ == "__main__":
    run()
