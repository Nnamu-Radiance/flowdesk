FROM python:3.12-slim

WORKDIR /app

COPY services/workflow-service/requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 120 -r requirements.txt

COPY services/workflow-service/ .
COPY shared/ ./shared/

RUN adduser --disabled-password --gecos '' appuser \
    && mkdir -p /app/media /app/staticfiles \
    && chown -R appuser:appuser /app/media /app/staticfiles
USER appuser

EXPOSE 8002
