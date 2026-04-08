"""
AI Team 실행 헬퍼 스크립트

프로젝트 루트에서 AI Team을 쉽게 실행하기 위한 스크립트
"""

import os
import sys
import logging
from dotenv import load_dotenv

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

    # ANTHROPIC_API_KEY 확인
    if not os.getenv('ANTHROPIC_API_KEY'):
        errors.append("ANTHROPIC_API_KEY가 설정되지 않았습니다.")
        errors.append("  .env 파일에 ANTHROPIC_API_KEY=sk-ant-your-key-here를 추가하세요.")
        errors.append("  Anthropic API 키 발급: https://console.anthropic.com/")

    if errors:
        logger.error("다음 요구사항을 충족하지 못했습니다:")
        for error in errors:
            logger.error(f"  {error}")
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
    logger.info(f"API 문서: http://localhost:{port}/docs")
    logger.info("종료하려면 Ctrl+C를 누르세요.")

    try:
        uvicorn.run(
            app,
            host=host,
            port=port,
            log_level="info"
        )
    except KeyboardInterrupt:
        logger.info("\nAPI 서버를 종료합니다.")
    except Exception as e:
        logger.error(f"오류 발생: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
