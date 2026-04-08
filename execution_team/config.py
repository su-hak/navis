"""
주문 실행 팀 설정
"""
import os
from pathlib import Path
from typing import Optional
from pydantic import BaseModel
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()


class BrokerConfig(BaseModel):
    """브로커 설정"""
    broker_type: str = "alpaca"  # alpaca, ibkr
    api_key: str
    secret_key: str
    base_url: str = "https://paper-api.alpaca.markets"  # Paper trading 기본값


class ExecutionConfig(BaseModel):
    """주문 실행 설정"""
    enable_circuit_breaker: bool = True
    max_retry_attempts: int = 3
    retry_base_delay: float = 1.0
    retry_max_delay: float = 10.0
    order_storage_path: Optional[str] = "logs/execution/orders"
    enable_pre_flight_check: bool = True
    enable_market_hours_check: bool = False  # 시장 시간 체크 (테스트 시 False)


class LoggingConfig(BaseModel):
    """로깅 설정"""
    log_level: str = "INFO"
    log_file: str = "logs/execution/execution.log"
    log_format: str = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"


class Config:
    """통합 설정"""

    def __init__(self):
        # 브로커 설정
        self.broker = BrokerConfig(
            broker_type=os.getenv("BROKER_TYPE", "alpaca"),
            api_key=os.getenv("ALPACA_API_KEY", ""),
            secret_key=os.getenv("ALPACA_SECRET_KEY", ""),
            base_url=os.getenv("ALPACA_BASE_URL", "https://paper-api.alpaca.markets")
        )

        # 실행 설정
        self.execution = ExecutionConfig(
            enable_circuit_breaker=os.getenv("ENABLE_CIRCUIT_BREAKER", "true").lower() == "true",
            max_retry_attempts=int(os.getenv("MAX_RETRY_ATTEMPTS", "3")),
            order_storage_path=os.getenv("ORDER_STORAGE_PATH", "logs/execution/orders")
        )

        # 로깅 설정
        self.logging = LoggingConfig(
            log_level=os.getenv("LOG_LEVEL", "INFO"),
            log_file=os.getenv("EXECUTION_LOG_FILE", "logs/execution/execution.log")
        )

    def validate(self) -> bool:
        """설정 검증 (경고만 출력, 앱 시작은 허용)"""
        import logging
        logger = logging.getLogger(__name__)

        if not self.broker.api_key or not self.broker.secret_key:
            logger.warning("⚠️ 브로커 API 키가 설정되지 않았습니다")
            logger.warning("⚠️ 환경변수를 설정하세요: ALPACA_API_KEY, ALPACA_SECRET_KEY")
            logger.warning("⚠️ 주문 실행 시 에러가 발생할 수 있습니다")
            return False

        return True


# 전역 설정 인스턴스
config = Config()
