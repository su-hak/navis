"""
재시도 핸들러
네트워크 오류 등 일시적 실패 시 자동 재시도
"""
import logging
import time
from typing import Callable, TypeVar, Optional, Type
from functools import wraps

from ..core.order_models import BrokerError

logger = logging.getLogger(__name__)

T = TypeVar('T')


class RetryConfig:
    """재시도 설정"""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 10.0,
        exponential_base: float = 2.0,
        jitter: bool = True
    ):
        """
        Args:
            max_attempts: 최대 시도 횟수 (1 = 재시도 없음)
            base_delay: 기본 대기 시간 (초)
            max_delay: 최대 대기 시간 (초)
            exponential_base: 지수 백오프 계수
            jitter: 지터 사용 여부 (랜덤화)
        """
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter


class RetryHandler:
    """재시도 핸들러"""

    def __init__(self, config: Optional[RetryConfig] = None):
        self.config = config or RetryConfig()

    def retry(
        self,
        func: Callable[..., T],
        *args,
        retryable_exceptions: tuple = (BrokerError,),
        should_retry: Optional[Callable[[Exception], bool]] = None,
        **kwargs
    ) -> T:
        """
        함수 실행 및 재시도

        Args:
            func: 실행할 함수
            *args: 함수 인자
            retryable_exceptions: 재시도 가능한 예외 타입들
            should_retry: 재시도 여부 판단 함수 (예외 → bool)
            **kwargs: 함수 키워드 인자

        Returns:
            함수 실행 결과

        Raises:
            마지막 시도의 예외
        """
        last_exception = None

        for attempt in range(1, self.config.max_attempts + 1):
            try:
                result = func(*args, **kwargs)

                # 성공 시 재시도 횟수 로깅
                if attempt > 1:
                    logger.info(f"재시도 성공 - 시도 {attempt}/{self.config.max_attempts}")

                return result

            except retryable_exceptions as e:
                last_exception = e

                # BrokerError의 retryable 플래그 확인
                if isinstance(e, BrokerError) and not e.retryable:
                    logger.warning(f"재시도 불가능한 에러: {e}")
                    raise

                # 커스텀 재시도 판단 함수
                if should_retry and not should_retry(e):
                    logger.warning(f"재시도 조건 미충족: {e}")
                    raise

                # 마지막 시도였다면 예외 발생
                if attempt >= self.config.max_attempts:
                    logger.error(
                        f"최대 재시도 횟수 초과 ({self.config.max_attempts}회) - "
                        f"마지막 에러: {e}"
                    )
                    raise

                # 대기 시간 계산
                delay = self._calculate_delay(attempt)

                logger.warning(
                    f"재시도 예정 - 시도 {attempt}/{self.config.max_attempts}, "
                    f"대기 {delay:.2f}초, 에러: {e}"
                )

                time.sleep(delay)

            except Exception as e:
                # 재시도 불가능한 예외는 즉시 발생
                logger.error(f"재시도 불가능한 예외 발생: {type(e).__name__} - {e}")
                raise

        # 여기 도달하면 안 되지만 안전장치
        if last_exception:
            raise last_exception
        raise RuntimeError("예상치 못한 재시도 로직 종료")

    def _calculate_delay(self, attempt: int) -> float:
        """
        대기 시간 계산 (Exponential Backoff with Jitter)

        Args:
            attempt: 현재 시도 횟수 (1부터 시작)

        Returns:
            대기 시간 (초)
        """
        import random

        # 지수 백오프 계산
        delay = self.config.base_delay * (self.config.exponential_base ** (attempt - 1))

        # 최대 대기 시간 제한
        delay = min(delay, self.config.max_delay)

        # Jitter 추가 (0.5 ~ 1.5배 랜덤)
        if self.config.jitter:
            delay = delay * (0.5 + random.random())

        return delay


def with_retry(
    max_attempts: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 10.0,
    retryable_exceptions: tuple = (BrokerError,)
):
    """
    재시도 데코레이터

    사용 예:
    ```python
    @with_retry(max_attempts=3, base_delay=2.0)
    def submit_order(order):
        # 주문 제출 로직
        pass
    ```

    Args:
        max_attempts: 최대 시도 횟수
        base_delay: 기본 대기 시간
        max_delay: 최대 대기 시간
        retryable_exceptions: 재시도 가능한 예외들
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        def wrapper(*args, **kwargs) -> T:
            config = RetryConfig(
                max_attempts=max_attempts,
                base_delay=base_delay,
                max_delay=max_delay
            )
            handler = RetryHandler(config)

            return handler.retry(
                func,
                *args,
                retryable_exceptions=retryable_exceptions,
                **kwargs
            )

        return wrapper

    return decorator


# ============ 특화된 재시도 전략 ============

def retry_broker_call(func: Callable[..., T], *args, **kwargs) -> T:
    """
    브로커 API 호출 재시도
    네트워크 오류, 일시적 서버 오류 등에 대해 재시도

    사용 예:
    ```python
    result = retry_broker_call(broker.submit_order, order)
    ```
    """
    config = RetryConfig(
        max_attempts=3,
        base_delay=1.0,
        max_delay=5.0
    )
    handler = RetryHandler(config)

    def should_retry_broker(e: Exception) -> bool:
        """브로커 에러 재시도 여부 판단"""
        if isinstance(e, BrokerError):
            return e.retryable
        return False

    return handler.retry(
        func,
        *args,
        retryable_exceptions=(BrokerError,),
        should_retry=should_retry_broker,
        **kwargs
    )


def retry_critical_operation(func: Callable[..., T], *args, **kwargs) -> T:
    """
    중요한 작업 재시도 (더 많은 시도, 더 긴 대기)

    체결 확인, 계좌 조회 등 반드시 성공해야 하는 작업에 사용

    사용 예:
    ```python
    order_info = retry_critical_operation(broker.get_order, order_id)
    ```
    """
    config = RetryConfig(
        max_attempts=5,
        base_delay=2.0,
        max_delay=15.0
    )
    handler = RetryHandler(config)

    return handler.retry(
        func,
        *args,
        retryable_exceptions=(BrokerError, Exception),
        **kwargs
    )


# ============ Circuit Breaker ============

class CircuitBreaker:
    """
    서킷 브레이커
    연속 실패 시 일정 시간 동안 요청 차단
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        expected_exception: Type[Exception] = Exception
    ):
        """
        Args:
            failure_threshold: 실패 임계값
            recovery_timeout: 복구 대기 시간 (초)
            expected_exception: 감지할 예외 타입
        """
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception

        self.failure_count = 0
        self.last_failure_time: Optional[float] = None
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN

    def call(self, func: Callable[..., T], *args, **kwargs) -> T:
        """
        함수 호출 (서킷 브레이커 적용)

        Returns:
            함수 실행 결과

        Raises:
            Exception: 서킷이 OPEN 상태이거나 함수 실행 실패
        """
        # OPEN 상태: 차단 중
        if self.state == "OPEN":
            if self._should_attempt_reset():
                logger.info("서킷 브레이커 HALF_OPEN 전환")
                self.state = "HALF_OPEN"
            else:
                raise Exception(
                    f"서킷 브레이커 OPEN - "
                    f"{self.failure_count}회 연속 실패 후 차단됨"
                )

        try:
            result = func(*args, **kwargs)

            # 성공 시 리셋
            if self.state == "HALF_OPEN":
                logger.info("서킷 브레이커 CLOSED 복구")
                self._reset()

            return result

        except self.expected_exception as e:
            self._record_failure()
            raise

    def _record_failure(self) -> None:
        """실패 기록"""
        self.failure_count += 1
        self.last_failure_time = time.time()

        if self.failure_count >= self.failure_threshold:
            logger.error(
                f"서킷 브레이커 OPEN - "
                f"{self.failure_count}회 연속 실패"
            )
            self.state = "OPEN"

    def _should_attempt_reset(self) -> bool:
        """복구 시도 여부 판단"""
        if self.last_failure_time is None:
            return False

        elapsed = time.time() - self.last_failure_time
        return elapsed >= self.recovery_timeout

    def _reset(self) -> None:
        """상태 리셋"""
        self.failure_count = 0
        self.last_failure_time = None
        self.state = "CLOSED"

    def reset(self) -> None:
        """강제 리셋 (외부 호출용)"""
        logger.info("서킷 브레이커 강제 리셋")
        self._reset()
