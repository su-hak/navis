"""
AI Team API Server Runner

AI Team API 서버를 쉽게 실행하기 위한 스크립트
"""

import os
import sys
import logging
from pathlib import Path
from dotenv import load_dotenv

# 부모 디렉토리를 Python 경로에 추가
current_dir = Path(__file__).parent
parent_dir = current_dir.parent
sys.path.insert(0, str(parent_dir))

# 환경 변수 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def check_requirements():
    """필수 요구사항 확인"""
    errors = []

    # OpenAI API 키 확인
    if not os.getenv('ANTHROPIC_API_KEY'):
        errors.append("ANTHROPIC_API_KEY가 설정되지 않았습니다.")

    if errors:
        logger.error("다음 요구사항을 충족하지 못했습니다:")
        for error in errors:
            logger.error(f"  - {error}")
        logger.error("\n.env 파일을 확인하세요.")
        return False

    return True


def main():
    """메인 함수"""
    logger.info("AI Team API 서버 시작 중...")

    # 요구사항 확인
    if not check_requirements():
        sys.exit(1)

    # API 서버 실행
    import uvicorn
    from ai_team.api.main import app

    host = os.getenv('AI_TEAM_HOST', '0.0.0.0')
    port = int(os.getenv('AI_TEAM_PORT', 8001))

    logger.info(f"서버 주소: http://{host}:{port}")
    logger.info(f"API 문서: http://{host}:{port}/docs")

    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
