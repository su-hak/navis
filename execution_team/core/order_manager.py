"""
주문 상태 관리 시스템
주문의 생명주기 추적 및 DB 저장
"""
import logging
from typing import Dict, List, Optional
from datetime import datetime
import json
from pathlib import Path

from .order_models import (
    Order, OrderStatus, OrderSignal, OrderAction, OrderType, TimeInForce
)

logger = logging.getLogger(__name__)


class OrderManager:
    """
    주문 상태 관리자
    주문의 생성, 상태 변경, 조회를 담당
    """

    def __init__(self, storage_path: Optional[str] = None):
        """
        초기화

        Args:
            storage_path: 주문 저장 경로 (None이면 메모리만 사용)
        """
        self.orders: Dict[str, Order] = {}  # order_id → Order
        self.broker_order_map: Dict[str, str] = {}  # broker_order_id → order_id
        self.storage_path = storage_path

        if self.storage_path:
            Path(self.storage_path).mkdir(parents=True, exist_ok=True)
            self._load_orders()

        logger.info(f"OrderManager 초기화 - 저장소: {storage_path or '메모리'}")

    # ============ 주문 생성 및 등록 ============

    def create_order(self, signal: OrderSignal) -> Order:
        """
        신호로부터 주문 생성

        Args:
            signal: 주문 신호

        Returns:
            생성된 주문 객체
        """
        order = Order(
            symbol=signal.symbol,
            action=signal.action,
            order_type=signal.order_type,
            quantity=signal.quantity,
            limit_price=signal.limit_price,
            stop_price=signal.stop_price,
            time_in_force=signal.time_in_force,
            strategy_id=signal.strategy_id,
            reason=signal.reason,
            metadata=signal.metadata or {}
        )

        self.register_order(order)

        logger.info(
            f"주문 생성 - ID: {order.order_id}, "
            f"{order.action.value} {order.quantity} {order.symbol}"
        )

        return order

    def register_order(self, order: Order) -> None:
        """
        주문 등록 (저장소에 추가)

        Args:
            order: 등록할 주문
        """
        self.orders[order.order_id] = order
        self._save_order(order)

    # ============ 주문 상태 업데이트 ============

    def update_status(
        self,
        order_id: str,
        status: OrderStatus,
        broker_order_id: Optional[str] = None,
        error_message: Optional[str] = None
    ) -> None:
        """
        주문 상태 업데이트

        Args:
            order_id: 주문 ID
            status: 새로운 상태
            broker_order_id: 브로커 주문 ID (처음 제출 시)
            error_message: 에러 메시지 (실패 시)
        """
        order = self.get_order(order_id)
        if not order:
            logger.error(f"주문 없음 - ID: {order_id}")
            return

        old_status = order.status
        order.status = status

        # 브로커 주문 ID 매핑
        if broker_order_id:
            order.broker_order_id = broker_order_id
            self.broker_order_map[broker_order_id] = order_id

        # 에러 메시지
        if error_message:
            order.error_message = error_message

        # 타임스탬프 업데이트
        if status == OrderStatus.SUBMITTED and not order.submitted_at:
            order.submitted_at = datetime.now()
        elif status == OrderStatus.FILLED and not order.filled_at:
            order.filled_at = datetime.now()

        self._save_order(order)

        logger.info(
            f"주문 상태 변경 - ID: {order_id}, "
            f"{old_status.value} → {status.value}"
        )

    def update_filled(
        self,
        order_id: str,
        filled_quantity: int,
        filled_price: float,
        commission: float = 0.0
    ) -> None:
        """
        체결 정보 업데이트

        Args:
            order_id: 주문 ID
            filled_quantity: 체결된 수량
            filled_price: 평균 체결가
            commission: 수수료
        """
        order = self.get_order(order_id)
        if not order:
            logger.error(f"주문 없음 - ID: {order_id}")
            return

        order.filled_quantity = filled_quantity
        order.filled_price = filled_price
        order.commission = commission

        # 완전 체결 여부 확인
        if filled_quantity >= order.quantity:
            order.status = OrderStatus.FILLED
            order.filled_at = datetime.now()
            logger.info(f"주문 완전 체결 - ID: {order_id}, 가격: ${filled_price:.2f}")
        elif filled_quantity > 0:
            order.status = OrderStatus.PARTIALLY_FILLED
            logger.info(
                f"주문 부분 체결 - ID: {order_id}, "
                f"{filled_quantity}/{order.quantity} @ ${filled_price:.2f}"
            )

        self._save_order(order)

    def increment_retry(self, order_id: str) -> int:
        """
        재시도 횟수 증가

        Args:
            order_id: 주문 ID

        Returns:
            현재 재시도 횟수
        """
        order = self.get_order(order_id)
        if not order:
            return 0

        order.retry_count += 1
        self._save_order(order)

        return order.retry_count

    # ============ 주문 조회 ============

    def get_order(self, order_id: str) -> Optional[Order]:
        """
        주문 ID로 조회

        Args:
            order_id: 주문 ID

        Returns:
            주문 객체 (없으면 None)
        """
        return self.orders.get(order_id)

    def get_order_by_broker_id(self, broker_order_id: str) -> Optional[Order]:
        """
        브로커 주문 ID로 조회

        Args:
            broker_order_id: 브로커 주문 ID

        Returns:
            주문 객체 (없으면 None)
        """
        order_id = self.broker_order_map.get(broker_order_id)
        if not order_id:
            return None
        return self.get_order(order_id)

    def get_orders(
        self,
        status: Optional[OrderStatus] = None,
        symbol: Optional[str] = None,
        action: Optional[OrderAction] = None
    ) -> List[Order]:
        """
        조건으로 주문 목록 조회

        Args:
            status: 상태 필터
            symbol: 종목 필터
            action: 액션 필터

        Returns:
            주문 목록
        """
        orders = list(self.orders.values())

        if status:
            orders = [o for o in orders if o.status == status]
        if symbol:
            orders = [o for o in orders if o.symbol == symbol]
        if action:
            orders = [o for o in orders if o.action == action]

        return orders

    def get_active_orders(self) -> List[Order]:
        """활성 주문 목록 (체결 대기 중)"""
        return [o for o in self.orders.values() if o.is_active]

    def get_filled_orders(self) -> List[Order]:
        """체결 완료된 주문 목록"""
        return [o for o in self.orders.values() if o.is_filled]

    # ============ 통계 ============

    def get_stats(self) -> dict:
        """
        주문 통계

        Returns:
            {
                'total': 전체 주문 수,
                'by_status': {...},
                'by_symbol': {...},
                'success_rate': 성공률
            }
        """
        orders = list(self.orders.values())
        total = len(orders)

        if total == 0:
            return {
                'total': 0,
                'by_status': {},
                'by_symbol': {},
                'success_rate': 0.0
            }

        # 상태별
        by_status = {}
        for order in orders:
            status = order.status.value
            by_status[status] = by_status.get(status, 0) + 1

        # 종목별
        by_symbol = {}
        for order in orders:
            by_symbol[order.symbol] = by_symbol.get(order.symbol, 0) + 1

        # 성공률
        filled_count = by_status.get(OrderStatus.FILLED.value, 0)
        success_rate = (filled_count / total) * 100 if total > 0 else 0.0

        return {
            'total': total,
            'by_status': by_status,
            'by_symbol': by_symbol,
            'success_rate': success_rate
        }

    # ============ 저장/로드 ============

    def _save_order(self, order: Order) -> None:
        """주문 저장 (JSON 파일)"""
        if not self.storage_path:
            return

        try:
            file_path = Path(self.storage_path) / f"{order.order_id}.json"
            with open(file_path, 'w') as f:
                json.dump(order.dict(), f, indent=2, default=str)
        except Exception as e:
            logger.error(f"주문 저장 실패 - {order.order_id}: {e}")

    def _load_orders(self) -> None:
        """저장된 주문 로드"""
        if not self.storage_path:
            return

        try:
            storage_dir = Path(self.storage_path)
            if not storage_dir.exists():
                return

            for file_path in storage_dir.glob("*.json"):
                try:
                    with open(file_path, 'r') as f:
                        data = json.load(f)
                        order = Order(**data)
                        self.orders[order.order_id] = order

                        # 브로커 ID 매핑 복원
                        if order.broker_order_id:
                            self.broker_order_map[order.broker_order_id] = order.order_id

                except Exception as e:
                    logger.error(f"주문 로드 실패 - {file_path}: {e}")

            logger.info(f"{len(self.orders)}개 주문 로드 완료")

        except Exception as e:
            logger.error(f"주문 로드 중 오류: {e}")

    def clear_old_orders(self, days: int = 30) -> int:
        """
        오래된 주문 삭제

        Args:
            days: 며칠 이전 주문 삭제

        Returns:
            삭제된 주문 수
        """
        from datetime import timedelta

        cutoff_date = datetime.now() - timedelta(days=days)
        deleted_count = 0

        order_ids_to_delete = []
        for order_id, order in self.orders.items():
            if order.created_at < cutoff_date and order.is_terminal:
                order_ids_to_delete.append(order_id)

        for order_id in order_ids_to_delete:
            order = self.orders.pop(order_id)

            # 브로커 매핑 삭제
            if order.broker_order_id:
                self.broker_order_map.pop(order.broker_order_id, None)

            # 파일 삭제
            if self.storage_path:
                file_path = Path(self.storage_path) / f"{order_id}.json"
                if file_path.exists():
                    file_path.unlink()

            deleted_count += 1

        logger.info(f"{deleted_count}개 오래된 주문 삭제 ({days}일 이전)")
        return deleted_count
