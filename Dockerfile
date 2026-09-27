FROM python:3.12-slim

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

COPY requirements.txt .
RUN pip install -r requirements.txt

COPY app ./app
COPY schema.sql .

RUN mkdir -p /app/config /app/output && chmod -R a+rX /app/app && chmod 644 /app/schema.sql

ENV CONFIG_DIR=/app/config \
    OUTPUT_DIR=/app/output \
    PORT=8765

EXPOSE 8765

CMD ["python", "-m", "app.api"]
