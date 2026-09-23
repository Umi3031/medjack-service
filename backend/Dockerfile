# Build context нь төслийн үндсэн хавтас
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    TZ=Asia/Ulaanbaatar

WORKDIR /srv/backend

# Эхлээд зөвхөн хамаарлыг суулгана: код өөрчлөгдөхөд энэ давхарга кэшээс ашиглагдана
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY frontend /srv/frontend

# Root эрхгүй хэрэглэгчээр ажиллуулж аюулгүй байдлыг сайжруулна
RUN useradd --create-home appuser
USER appuser

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers", "--forwarded-allow-ips=*"]
