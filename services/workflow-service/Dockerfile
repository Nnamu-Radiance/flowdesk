FROM python:3.12-slim

WORKDIR /app

COPY services/workflow-service/requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 120 -r requirements.txt

COPY services/workflow-service/ .
COPY shared/ ./shared/

RUN adduser --disabled-password --gecos '' appuser
USER appuser

EXPOSE 8002
