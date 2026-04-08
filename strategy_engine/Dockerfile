# Strategy Engine API Dockerfile
FROM python:3.11-slim

# 작업 디렉토리 설정
WORKDIR /app

# 의존성 파일 복사
COPY requirements_api.txt .

# 의존성 설치
RUN pip install --no-cache-dir -r requirements_api.txt

# 전략 엔진 코드 복사
COPY . .

# 부모 디렉토리를 PYTHONPATH에 추가
ENV PYTHONPATH=/app:$PYTHONPATH

# 포트 설정
EXPOSE 8001

# 헬스체크
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8001/health')" || exit 1

# 서버 실행
CMD ["uvicorn", "strategy_engine.api.strategy_api:app", "--host", "0.0.0.0", "--port", "8001"]
