"""Railway 배포용 시작 스크립트 - $PORT 환경변수를 Python에서 직접 읽음"""
import os
import uvicorn

port = int(os.environ.get("PORT", 8001))

uvicorn.run(
    "ai_team.api.main:app",
    host="0.0.0.0",
    port=port,
    log_level="info",
)
