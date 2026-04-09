FROM python:3.11-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 패키지 구조 유지: notification_team/
COPY . /app/notification_team

CMD uvicorn notification_team.main:app --host 0.0.0.0 --port ${PORT:-8005}
