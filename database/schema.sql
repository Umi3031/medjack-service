-- =====================================================================
-- МЕДЖЕК ХХК — Төхөөрөмжийн паспорт ба засвар үйлчилгээний өгөгдлийн сан
-- Зохиогч: Б. Өмирсерик (23B1NUM3031), 2026
-- Тайлбар: Програм асахдаа хүснэгтүүдийг SQLAlchemy-ээр автоматаар үүсгэдэг.
-- Энэ файл нь ижил бүтцийг цэвэр SQL-ээр харуулсан лавлах баримт бичиг
-- бөгөөд pgAdmin эсвэл psql-д шууд ажиллуулж туршиж болно:
--     psql -U medjack -d medjack -f database/schema.sql
-- =====================================================================

DROP VIEW  IF EXISTS v_reminders, v_device_passport CASCADE;
DROP TABLE IF EXISTS service_ticket, device, customer, app_user CASCADE;

-- 1. Харилцагч байгууллага ------------------------------------------------
CREATE TABLE customer (
    customer_id        SERIAL PRIMARY KEY,
    organization_name  VARCHAR(200) NOT NULL,
    address            VARCHAR(300),
    contact_person     VARCHAR(120),
    phone              VARCHAR(30),
    created_at         TIMESTAMP NOT NULL DEFAULT now()
);

-- 2. Тоног төхөөрөмж (төхөөрөмжийн паспорт) --------------------------------
CREATE TABLE device (
    device_id          SERIAL PRIMARY KEY,
    device_code        VARCHAR(20) UNIQUE NOT NULL,          -- QR код дээрх код: MJ-0001
    customer_id        INT NOT NULL REFERENCES customer(customer_id) ON DELETE RESTRICT,
    category           VARCHAR(80)  NOT NULL,
    brand              VARCHAR(80),
    model              VARCHAR(120) NOT NULL,
    serial_number      VARCHAR(80)  NOT NULL UNIQUE,         -- серийн дугаар давхардахгүй
    install_date       DATE NOT NULL,
    warranty_end_date  DATE,
    next_service_date  DATE,
    location           VARCHAR(150),
    status             VARCHAR(30) NOT NULL DEFAULT 'Ажиллаж байгаа'
                       CHECK (status IN ('Ажиллаж байгаа','Засварт','Ашиглалтаас гарсан')),
    manual_url         TEXT,
    CONSTRAINT chk_warranty CHECK (warranty_end_date IS NULL OR warranty_end_date >= install_date)
);
CREATE INDEX idx_device_customer ON device(customer_id);
CREATE INDEX idx_device_warranty ON device(warranty_end_date);

-- 3. Засварын дуудлага (Service Ticket) ------------------------------------
CREATE TABLE service_ticket (
    ticket_id            SERIAL PRIMARY KEY,
    device_id            INT NOT NULL REFERENCES device(device_id) ON DELETE RESTRICT,
    reported_date        DATE NOT NULL DEFAULT CURRENT_DATE,
    problem_description  TEXT NOT NULL,
    diagnosis            TEXT,
    action_taken         TEXT,
    parts_used           VARCHAR(300),
    technician           VARCHAR(120),
    status               VARCHAR(20) NOT NULL DEFAULT 'Нээлттэй'
                         CHECK (status IN ('Нээлттэй','Хийгдэж байгаа','Хаагдсан')),
    closed_date          DATE,
    -- Хаагдсан дуудлага заавал хийсэн ажил, хаасан огноотой байна
    CONSTRAINT chk_closed CHECK (
        status <> 'Хаагдсан' OR (closed_date IS NOT NULL AND action_taken IS NOT NULL)
    )
);
CREATE INDEX idx_ticket_device ON service_ticket(device_id);
CREATE INDEX idx_ticket_status ON service_ticket(status);

-- 4. Системийн хэрэглэгч (эрхийн ялгаатай удирдлага) ---------------------
CREATE TABLE app_user (
    user_id        SERIAL PRIMARY KEY,
    username       VARCHAR(60)  NOT NULL UNIQUE,
    full_name      VARCHAR(120),
    password_hash  VARCHAR(255) NOT NULL,              -- PBKDF2-SHA256 хэш, ил нууц үг биш
    role           VARCHAR(20)  NOT NULL DEFAULT 'engineer' CHECK (role IN ('admin','engineer')),
    is_active      BOOLEAN      NOT NULL DEFAULT TRUE,
    created_at     TIMESTAMP    NOT NULL DEFAULT now()
);

-- 5. Төхөөрөмжийн паспорт (QR уншуулахад харагдах мэдээлэл) ---------------
CREATE VIEW v_device_passport AS
SELECT d.device_code, d.category, d.brand, d.model, d.serial_number,
       c.organization_name, d.location, d.install_date, d.warranty_end_date,
       (d.warranty_end_date - CURRENT_DATE)            AS warranty_days_left,
       d.next_service_date, d.status,
       COUNT(t.ticket_id)                              AS ticket_count,
       MAX(t.reported_date)                            AS last_ticket_date
FROM device d
JOIN customer c            ON c.customer_id = d.customer_id
LEFT JOIN service_ticket t ON t.device_id  = d.device_id
GROUP BY d.device_id, c.organization_name;

-- 6. Автомат сануулга: 30 / 14 / 7 хоног -----------------------------------
CREATE VIEW v_reminders AS
SELECT d.device_code, d.model, d.serial_number, c.organization_name, c.phone,
       'Баталгаат хугацаа дуусна'::text             AS reminder_type,
       (d.warranty_end_date - CURRENT_DATE)         AS days_left,
       CASE WHEN d.warranty_end_date - CURRENT_DATE <= 7  THEN '7 хоног'
            WHEN d.warranty_end_date - CURRENT_DATE <= 14 THEN '14 хоног'
            ELSE '30 хоног' END                     AS tier
FROM device d JOIN customer c USING (customer_id)
WHERE d.status <> 'Ашиглалтаас гарсан'
  AND d.warranty_end_date BETWEEN CURRENT_DATE AND CURRENT_DATE + 30
UNION ALL
SELECT d.device_code, d.model, d.serial_number, c.organization_name, c.phone,
       CASE WHEN d.next_service_date < CURRENT_DATE THEN 'Төлөвлөгөөт үйлчилгээ хоцорсон'
            ELSE 'Төлөвлөгөөт үйлчилгээ' END,
       (d.next_service_date - CURRENT_DATE),
       CASE WHEN d.next_service_date - CURRENT_DATE <= 7 THEN '7 хоног' ELSE '14 хоног' END
FROM device d JOIN customer c USING (customer_id)
WHERE d.status <> 'Ашиглалтаас гарсан'
  AND d.next_service_date <= CURRENT_DATE + 14
ORDER BY days_left;

-- 7. Жишээ өгөгдөл (бодит харилцагчийн мэдээлэл биш) ----------------------
INSERT INTO customer (organization_name, address, contact_person) VALUES
 ('Батсүмбэр сумын Эрүүл мэндийн төв', 'Төв аймаг, Батсүмбэр сум',       'Лабораторийн эрхлэгч'),
 ('Жишээ клиник А',                   'Улаанбаатар, Баянгол дүүрэг',    'Ерөнхий сувилагч'),
 ('Жишээ лаборатори Б',               'Улаанбаатар, Сүхбаатар дүүрэг',  'Лаборант'),
 ('Жишээ сумын ЭМТ В',                'Орон нутаг',                     'Их эмч');

INSERT INTO device (device_code, customer_id, category, brand, model, serial_number,
                    install_date, warranty_end_date, next_service_date, location, status) VALUES
 ('MJ-0001',1,'Биохимийн анализатор',NULL,'Full-auto Chemistry Analyzer','BCA-2605-0142','2026-07-02','2027-07-02','2026-10-02','Клиник лаборатори','Ажиллаж байгаа'),
 ('MJ-0002',2,'ЭКГ аппарат',NULL,'ECG-912','E912-24-00871','2024-10-01','2026-09-29','2026-12-01','Дотрын кабинет','Ажиллаж байгаа'),
 ('MJ-0003',2,'Хяналтын монитор',NULL,'Multi-parameter Monitor 12"','PM12-25-3310','2025-10-06','2026-10-06','2026-10-01','Эрчимт эмчилгээ','Засварт'),
 ('MJ-0004',3,'Инкубатор','FAITHFUL','DH-360','FH-DH360-5521','2026-06-26','2027-06-26','2026-12-26','Бактериологи','Ажиллаж байгаа'),
 ('MJ-0005',3,'Биологийн аюулгүйн шүүгээ','SCITEK','BSC-1100 II A2','SCT-BSC-11807','2026-06-26','2027-06-26','2026-12-26','Бактериологи','Ажиллаж байгаа'),
 ('MJ-0006',4,'Автоклав','BIOBASE','BKM-Z24B','BB-Z24-60219','2026-04-10','2027-04-10','2026-10-10','Ариутгалын өрөө','Ажиллаж байгаа'),
 ('MJ-0007',4,'ЭКГ аппарат',NULL,'ECG-912','E912-23-00412','2023-05-15','2025-05-15','2026-09-15','Хүлээн авах','Ажиллаж байгаа'),
 ('MJ-0008',1,'ЭКГ аппарат',NULL,'ECG-912','E912-25-01133','2025-10-12','2026-10-12','2027-01-12','Амбулатори','Ажиллаж байгаа');

INSERT INTO service_ticket (device_id, reported_date, problem_description, diagnosis,
                            action_taken, parts_used, technician, status, closed_date) VALUES
 (7,'2026-05-06','Хэвлэгч цаас татахгүй, бичлэг тасалдана','Хэвлэгчийн роликийн элэгдэл',
  'Роликийг цэвэрлэж тохируулсан, дулааны толгойг шалгасан',NULL,'Техникийн инженер','Хаагдсан','2026-05-07'),
 (1,'2026-07-09','Суурилуулалтын дараах тохиргоо: шинжилгээний нэршил, урвалжийн байрлал',
  'Програм дээрх нэршил лабораторийн ажлын дадалтай зөрсөн',
  'Тестийн нэршил, урвалжийн байрлалыг жагсаалтаар тулгаж засаж, операторт сургалт өгсөн',NULL,'Техникийн инженер','Хаагдсан','2026-07-10'),
 (3,'2026-09-19','SpO2 утга тогтворгүй, дохиолол (alarm) давтан дуугарна','Мэдрэгчийн кабелийн холболт сул байж болзошгүй',
  NULL,NULL,'Техникийн инженер','Хийгдэж байгаа',NULL),
 (6,'2026-08-21','Даралт зорилтот утгад хүрэх хугацаа уртассан','Хаалганы жийргэвч элэгдсэн',
  'Жийргэвчийг сольж, туршилтын мөчлөг ажиллуулсан','Хаалганы силикон жийргэвч ×1','Техникийн инженер','Хаагдсан','2026-08-22');

-- 8. Хамгаалалтад үзүүлэх жишээ асуулга ------------------------------------
-- Серийн дугаараар төхөөрөмжийн бүрэн түүх:
--   SELECT * FROM v_device_passport WHERE serial_number = 'E912-23-00412';
--   SELECT * FROM service_ticket t JOIN device d USING (device_id)
--    WHERE d.serial_number = 'E912-23-00412' ORDER BY reported_date DESC;
-- Өнөөдрийн сануулгууд:
--   SELECT * FROM v_reminders;
-- Сарын тайлан (суурилуулалт ба засварын тоо):
--   SELECT to_char(install_date,'YYYY-MM') AS month, COUNT(*) FROM device GROUP BY 1 ORDER BY 1;
--   SELECT to_char(reported_date,'YYYY-MM') AS month, COUNT(*) FROM service_ticket GROUP BY 1 ORDER BY 1;
