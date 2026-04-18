FROM python:3.11-slim

WORKDIR /app

COPY requirements_api.txt .
RUN pip install --no-cache-dir -r requirements_api.txt

# 소스를 strategy_engine 패키지 디렉토리로 복사
COPY . /app/strategy_engine/

ENV PYTHONPATH=/app

EXPOSE 8001

HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import requests; requests.get('http://localhost:8001/health')" || exit 1

CMD ["sh", "-c", "uvicorn strategy_engine.api.strategy_api:app --host 0.0.0.0 --port ${PORT:-8001}"]
