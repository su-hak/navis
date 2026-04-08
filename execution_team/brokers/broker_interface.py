"""
브로커 추상 인터페이스
다양한 브로커(Alpaca, IBKR 등)를 교체 가능하도록 추상화
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from ..core.order_models import (
    Order, OrderStatus, Position, AccountInfo, BrokerError
)


class BrokerInterface(ABC):
    """
    브로커 추상 인터페이스
    모든 브로커 구현체가 이 인터페이스를 구현해야 함
    """

    def __init__(self, config: dict):
        """
        브로커 초기화

        Args:
            config: 브로커 설정 (API 키, URL 등)
        """
        self.config = config
        self._initialized = False

    @abstractmethod
    def connect(self) -> bool:
        """
        브로커에 연결

        Returns:
            bool: 연결 성공 여부

        Raises:
            BrokerError: 연결 실패 시
        """
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """브로커 연결 해제"""
        pass

    @abstractmethod
    def submit_order(self, order: Order) -> str:
        """
        주문 제출

        Args:
            order: 제출할 주문 객체

        Returns:
            str: 브로커에서 할당한 주문 ID

        Raises:
            BrokerError: 주문 제출 실패 시
        """
        pass

    @abstractmethod
    def get_order(self, broker_order_id: str) -> dict:
        """
        주문 조회

        Args:
            broker_order_id: 브로커 주문 ID

        Returns:
            dict: 주문 정보
                {
                    'status': OrderStatus,
                    'filled_quantity': int,
                    'filled_price': float,
                    'commission': float,
                    ...
                }

        Raises:
            BrokerError: 조회 실패 시
        """
        pass

    @abstractmethod
    def cancel_order(self, broker_order_id: str) -> bool:
        """
        주문 취소

        Args:
            broker_order_id: 브로커 주문 ID

        Returns:
            bool: 취소 성공 여부

        Raises:
            BrokerError: 취소 실패 시
        """
        pass

    @abstractmethod
    def get_account(self) -> AccountInfo:
        """
        계좌 정보 조회

        Returns:
            AccountInfo: 계좌 정보

        Raises:
            BrokerError: 조회 실패 시
        """
        pass

    @abstractmethod
    def get_positions(self) -> List[Position]:
        """
        현재 포지션 조회

        Returns:
            List[Position]: 포지션 목록

        Raises:
            BrokerError: 조회 실패 시
        """
        pass

    @abstractmethod
    def get_position(self, symbol: str) -> Optional[Position]:
        """
        특정 종목 포지션 조회

        Args:
            symbol: 종목 심볼

        Returns:
            Optional[Position]: 포지션 (없으면 None)

        Raises:
            BrokerError: 조회 실패 시
        """
        pass

    @abstractmethod
    def is_market_open(self) -> bool:
        """
        시장 개장 여부 확인

        Returns:
            bool: 개장 중이면 True

        Raises:
            BrokerError: 확인 실패 시
        """
        pass

    @abstractmethod
    def get_current_price(self, symbol: str) -> float:
        """
        현재가 조회

        Args:
            symbol: 종목 심볼

        Returns:
            float: 현재가

        Raises:
            BrokerError: 조회 실패 시
        """
        pass

    # 헬퍼 메서드
    def is_connected(self) -> bool:
        """연결 상태 확인"""
        return self._initialized

    def validate_connection(self) -> None:
        """
        연결 상태 검증

        Raises:
            BrokerError: 연결되지 않은 경우
        """
        if not self.is_connected():
            raise BrokerError("브로커에 연결되지 않았습니다", retryable=True)

    def __enter__(self):
        """컨텍스트 매니저 진입"""
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """컨텍스트 매니저 종료"""
        self.disconnect()
