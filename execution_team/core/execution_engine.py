"""
주문 실행 엔진 (핵심 모듈)
전략 신호를 받아 실제 주문을 실행하는 메인 엔진
"""
import logging
import time
from typing import Optional, List
from datetime import datetime

from .order_models import (
    OrderSignal, Order, OrderResult, OrderStatus, Position, AccountInfo,
    BrokerError, ValidationError, ExecutionError
)
from .order_manager import OrderManager
from ..brokers.broker_interface import BrokerInterface
from ..utils.retry_handler import retry_broker_call, CircuitBreaker

logger = logging.getLogger(__name__)


class ExecutionEngine:
    """
    주문 실행 엔진

    역할:
    1. 주문 신호 수신 및 검증
    2. 주문 생성 및 브로커 전송
    3. 체결 확인 및 상태 업데이트
    4. 예외 처리 및 재시도
    """

    def __init__(
        self,
        broker: BrokerInterface,
        order_manager: OrderManager,
        enable_circuit_breaker: bool = True
    ):
        """
        초기화

        Args:
            broker: 브로커 구현체
            order_manager: 주문 관리자
            enable_circuit_breaker: 서킷 브레이커 활성화 여부
        """
        self.broker = broker
        self.order_manager = order_manager

        # 서킷 브레이커
        self.circuit_breaker = None
        if enable_circuit_breaker:
            self.circuit_breaker = CircuitBreaker(
                failure_threshold=5,
                recovery_timeout=60.0,
                expected_exception=BrokerError
            )

        logger.info("ExecutionEngine 초기화 완료")

    # ============ 메인 실행 함수 ============

    def execute_order(self, signal: OrderSignal) -> OrderResult:
        """
        주문 실행 (메인 함수)

        Args:
            signal: 주문 신호

        Returns:
            OrderResult: 실행 결과

        실행 흐름:
        1. 신호 검증
        2. Pre-flight 체크
        3. 주문 생성 및 저장
        4. 브로커 전송 (재시도 포함)
        5. 체결 확인
        6. 결과 반환
        """
        start_time = time.time()
        order: Optional[Order] = None

        try:
            # 1. 신호 검증
            logger.info(
                f"주문 실행 시작 - {signal.action.value} {signal.quantity} "
                f"{signal.symbol} @ {signal.order_type.value}"
            )
            self._validate_signal(signal)

            # 2. Pre-flight 체크
            self._pre_flight_check(signal)

            # 3. 주문 생성
            order = self.order_manager.create_order(signal)

            # 4. 주문 제출
            broker_order_id = self._submit_order_with_retry(order)

            # 상태 업데이트
            self.order_manager.update_status(
                order.order_id,
                OrderStatus.SUBMITTED,
                broker_order_id=broker_order_id
            )

            # 5. 체결 확인 (시장가인 경우 빠르게 체결됨)
            if signal.order_type.name == "MARKET":
                self._wait_for_fill(order.order_id, timeout=10)

            # 6. 결과 생성
            order = self.order_manager.get_order(order.order_id)
            execution_time = (time.time() - start_time) * 1000  # ms

            result = OrderResult(
                success=True,
                order_id=order.order_id,
                broker_order_id=order.broker_order_id,
                status=order.status,
                filled_quantity=order.filled_quantity,
                filled_price=order.filled_price,
                commission=order.commission,
                filled_at=order.filled_at,
                execution_time_ms=execution_time
            )

            logger.info(
                f"주문 실행 완료 - ID: {order.order_id}, "
                f"상태: {order.status.value}, 시간: {execution_time:.2f}ms"
            )

            return result

        except (ValidationError, BrokerError, ExecutionError) as e:
            # 예상된 에러
            logger.error(f"주문 실행 실패: {e}")

            if order:
                self.order_manager.update_status(
                    order.order_id,
                    OrderStatus.FAILED,
                    error_message=str(e)
                )

            execution_time = (time.time() - start_time) * 1000

            return OrderResult(
                success=False,
                order_id=order.order_id if order else "unknown",
                status=OrderStatus.FAILED,
                error_message=str(e),
                execution_time_ms=execution_time
            )

        except Exception as e:
            # 예상치 못한 에러
            logger.exception(f"예상치 못한 오류: {e}")

            if order:
                self.order_manager.update_status(
                    order.order_id,
                    OrderStatus.FAILED,
                    error_message=f"Internal error: {str(e)}"
                )

            return OrderResult(
                success=False,
                order_id=order.order_id if order else "unknown",
                status=OrderStatus.FAILED,
                error_message=f"Internal error: {str(e)}"
            )

    # ============ 주문 조회 및 취소 ============

    def get_order_status(self, order_id: str) -> Optional[OrderStatus]:
        """주문 상태 조회"""
        order = self.order_manager.get_order(order_id)
        return order.status if order else None

    def cancel_order(self, order_id: str) -> bool:
        """
        주문 취소

        Args:
            order_id: 주문 ID

        Returns:
            bool: 취소 성공 여부
        """
        try:
            order = self.order_manager.get_order(order_id)
            if not order:
                logger.error(f"주문 없음 - ID: {order_id}")
                return False

            if not order.broker_order_id:
                logger.error(f"브로커 주문 ID 없음 - ID: {order_id}")
                return False

            # 브로커에 취소 요청
            success = self.broker.cancel_order(order.broker_order_id)

            if success:
                self.order_manager.update_status(order_id, OrderStatus.CANCELLED)
                logger.info(f"주문 취소 성공 - ID: {order_id}")
            else:
                logger.warning(f"주문 취소 실패 - ID: {order_id}")

            return success

        except BrokerError as e:
            logger.error(f"주문 취소 중 에러: {e}")
            return False

    def get_positions(self) -> List[Position]:
        """현재 포지션 조회"""
        try:
            return self.broker.get_positions()
        except BrokerError as e:
            logger.error(f"포지션 조회 실패: {e}")
            return []

    def get_account(self) -> Optional[AccountInfo]:
        """계좌 정보 조회"""
        try:
            return self.broker.get_account()
        except BrokerError as e:
            logger.error(f"계좌 조회 실패: {e}")
            return None

    # ============ 내부 헬퍼 메서드 ============

    def _validate_signal(self, signal: OrderSignal) -> None:
        """
        신호 검증

        Raises:
            ValidationError: 유효하지 않은 신호
        """
        # 종목 심볼 검증
        if not signal.symbol or len(signal.symbol) == 0:
            raise ValidationError("종목 심볼이 비어있습니다")

        # 수량 검증
        if signal.quantity <= 0:
            raise ValidationError(f"잘못된 수량: {signal.quantity}")

        # 지정가 검증
        if signal.order_type.name == "LIMIT":
            if not signal.limit_price or signal.limit_price <= 0:
                raise ValidationError("LIMIT 주문은 limit_price가 필요합니다")

        # 스탑가 검증
        if signal.order_type.name in ["STOP", "STOP_LIMIT"]:
            if not signal.stop_price or signal.stop_price <= 0:
                raise ValidationError("STOP 주문은 stop_price가 필요합니다")

        logger.debug(f"신호 검증 완료 - {signal.symbol}")

    def _pre_flight_check(self, signal: OrderSignal) -> None:
        """
        Pre-flight 체크

        - 브로커 연결 상태
        - 시장 개장 여부 (옵션)
        - 계좌 잔고
        - 중복 주문 방지

        Raises:
            ExecutionError: 체크 실패
        """
        # 브로커 연결 확인
        if not self.broker.is_connected():
            raise ExecutionError("브로커에 연결되지 않았습니다")

        # 시장 개장 확인 (옵션 - 주석 처리 가능)
        # try:
        #     if not self.broker.is_market_open():
        #         logger.warning("시장이 폐장 상태입니다")
        # except Exception as e:
        #     logger.warning(f"시장 상태 확인 실패: {e}")

        # 계좌 잔고 확인 (매수인 경우)
        if signal.action.name == "BUY":
            try:
                account = self.broker.get_account()
                required_cash = self._estimate_required_cash(signal)

                if account.buying_power < required_cash:
                    raise ExecutionError(
                        f"매수 가능 금액 부족 - "
                        f"필요: ${required_cash:,.2f}, "
                        f"가용: ${account.buying_power:,.2f}"
                    )
            except BrokerError as e:
                logger.warning(f"계좌 확인 실패: {e}")

        logger.debug("Pre-flight 체크 완료")

    def _estimate_required_cash(self, signal: OrderSignal) -> float:
        """
        필요 현금 추정

        Args:
            signal: 주문 신호

        Returns:
            필요한 현금 (개략)
        """
        if signal.order_type.name == "LIMIT" and signal.limit_price:
            price = signal.limit_price
        else:
            # 시장가인 경우 현재가 조회
            try:
                price = self.broker.get_current_price(signal.symbol)
            except:
                # 실패 시 임의로 높은 값 (안전 마진)
                logger.warning(f"현재가 조회 실패 - {signal.symbol}, 추정값 사용")
                price = 1000.0

        return price * signal.quantity * 1.05  # 5% 안전 마진

    def _submit_order_with_retry(self, order: Order) -> str:
        """
        주문 제출 (재시도 포함)

        Args:
            order: 주문 객체

        Returns:
            str: 브로커 주문 ID

        Raises:
            BrokerError: 제출 실패
        """
        # 서킷 브레이커 적용
        if self.circuit_breaker:
            try:
                broker_order_id = self.circuit_breaker.call(
                    self._submit_order_once,
                    order
                )
                return broker_order_id
            except Exception as e:
                logger.error(f"서킷 브레이커 차단 또는 실패: {e}")
                raise BrokerError(str(e), retryable=False)
        else:
            return self._submit_order_once(order)

    def _submit_order_once(self, order: Order) -> str:
        """
        주문 제출 (단일 시도, 재시도 로직 적용)

        Args:
            order: 주문 객체

        Returns:
            str: 브로커 주문 ID
        """
        # 재시도 로직 적용
        broker_order_id = retry_broker_call(
            self.broker.submit_order,
            order
        )

        # 재시도 횟수 기록
        if order.retry_count > 0:
            logger.info(f"재시도 후 주문 제출 성공 - {order.retry_count}회 재시도")

        return broker_order_id

    def _wait_for_fill(self, order_id: str, timeout: float = 30.0) -> None:
        """
        체결 대기

        Args:
            order_id: 주문 ID
            timeout: 타임아웃 (초)
        """
        start_time = time.time()
        check_interval = 0.5  # 0.5초마다 체크

        while (time.time() - start_time) < timeout:
            order = self.order_manager.get_order(order_id)
            if not order or not order.broker_order_id:
                break

            try:
                # 브로커에서 주문 상태 조회
                order_info = self.broker.get_order(order.broker_order_id)

                # 상태 업데이트
                self.order_manager.update_status(
                    order_id,
                    order_info['status']
                )

                # 체결 정보 업데이트
                if order_info['filled_quantity'] > 0:
                    self.order_manager.update_filled(
                        order_id,
                        order_info['filled_quantity'],
                        order_info['filled_price'],
                        order_info.get('commission', 0.0)
                    )

                # 체결 완료 or 종료 상태면 리턴
                order = self.order_manager.get_order(order_id)
                if order.is_terminal:
                    logger.info(f"주문 종료 - ID: {order_id}, 상태: {order.status.value}")
                    return

            except BrokerError as e:
                logger.warning(f"주문 상태 조회 실패: {e}")

            time.sleep(check_interval)

        logger.warning(f"체결 확인 타임아웃 - ID: {order_id}")

    # ============ 통계 및 관리 ============

    def get_execution_stats(self) -> dict:
        """
        실행 통계

        Returns:
            주문 통계 정보
        """
        return self.order_manager.get_stats()

    def reset_circuit_breaker(self) -> None:
        """서킷 브레이커 리셋"""
        if self.circuit_breaker:
            self.circuit_breaker.reset()
            logger.info("서킷 브레이커 리셋")
