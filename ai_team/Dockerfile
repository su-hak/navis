# AI Team Dockerfile

FROM python:3.11-slim

WORKDIR /app

# 시스템 패키지 설치
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Python 의존성 설치
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 애플리케이션 코드 복사 (ai_team 패키지 구조 유지)
COPY . ./ai_team/

# Python path 설정 (/app을 추가해야 ai_team 패키지를 찾을 수 있음)
ENV PYTHONPATH=/app

# 포트 설정
EXPOSE 8001

# API 서버 실행
CMD ["python", "/app/ai_team/start.py"]
