FROM python:3.12-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir --retries 5 --timeout 120 -i https://pypi.tuna.tsinghua.edu.cn/simple -r requirements.txt
COPY . .
RUN adduser --disabled-password --gecos '' appuser
USER appuser
EXPOSE 8003
