"""
주문 실행 엔진 테스트
"""
import pytest
from unittest.mock import Mock, patch

from execution_team.core import (
    ExecutionEngine, OrderManager, OrderSignal, OrderAction,
    OrderType, TimeInForce, OrderStatus, BrokerError
)
from execution_team.brokers import BrokerInterface


class MockBroker(BrokerInterface):
    """테스트용 Mock 브로커"""

    def __init__(self, config: dict):
        super().__init__(config)
        self.submitted_orders = []
        self.fail_submit = False

    def connect(self) -> bool:
        self._initialized = True
        return True

    def disconnect(self) -> None:
        self._initialized = False

    def submit_order(self, order) -> str:
        if self.fail_submit:
            raise BrokerError("Submit failed", retryable=False)

        broker_order_id = f"MOCK_{len(self.submitted_orders)}"
        self.submitted_orders.append({
            'order': order,
            'broker_order_id': broker_order_id
        })
        return broker_order_id

    def get_order(self, broker_order_id: str) -> dict:
        return {
            'status': OrderStatus.FILLED,
            'filled_quantity': 10,
            'filled_price': 210.0,
            'commission': 0.0
        }

    def cancel_order(self, broker_order_id: str) -> bool:
        return True

    def get_account(self):
        from execution_team.core.order_models import AccountInfo
        return AccountInfo(
            account_id="test",
            cash=10000.0,
            portfolio_value=10000.0,
            buying_power=10000.0,
            equity=10000.0,
            unrealized_pl=0.0,
            realized_pl=0.0
        )

    def get_positions(self):
        return []

    def get_position(self, symbol: str):
        return None

    def is_market_open(self) -> bool:
        return True

    def get_current_price(self, symbol: str) -> float:
        return 210.0


@pytest.fixture
def mock_broker():
    """Mock 브로커 fixture"""
    broker = MockBroker({'test': 'config'})
    broker.connect()
    return broker


@pytest.fixture
def order_manager(tmp_path):
    """주문 관리자 fixture"""
    return OrderManager(storage_path=str(tmp_path))


@pytest.fixture
def execution_engine(mock_broker, order_manager):
    """실행 엔진 fixture"""
    return ExecutionEngine(
        broker=mock_broker,
        order_manager=order_manager,
        enable_circuit_breaker=False
    )


def test_execute_market_buy_order(execution_engine, mock_broker):
    """시장가 매수 주문 테스트"""
    signal = OrderSignal(
        symbol="TSLA",
        action=OrderAction.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
        strategy_id="test_strategy"
    )

    result = execution_engine.execute_order(signal)

    assert result.success is True
    assert result.status == OrderStatus.FILLED
    assert len(mock_broker.submitted_orders) == 1


def test_execute_limit_sell_order(execution_engine, mock_broker):
    """지정가 매도 주문 테스트"""
    signal = OrderSignal(
        symbol="AAPL",
        action=OrderAction.SELL,
        order_type=OrderType.LIMIT,
        quantity=5,
        limit_price=150.0
    )

    result = execution_engine.execute_order(signal)

    assert result.success is True
    assert len(mock_broker.submitted_orders) == 1
    submitted = mock_broker.submitted_orders[0]['order']
    assert submitted.symbol == "AAPL"
    assert submitted.action == OrderAction.SELL
    assert submitted.limit_price == 150.0


def test_execute_order_validation_error(execution_engine):
    """주문 검증 에러 테스트"""
    # 잘못된 수량
    signal = OrderSignal(
        symbol="TSLA",
        action=OrderAction.BUY,
        order_type=OrderType.MARKET,
        quantity=-10  # 음수
    )

    result = execution_engine.execute_order(signal)

    assert result.success is False
    assert "잘못된 수량" in result.error_message


def test_execute_order_broker_error(execution_engine, mock_broker):
    """브로커 에러 테스트"""
    mock_broker.fail_submit = True

    signal = OrderSignal(
        symbol="TSLA",
        action=OrderAction.BUY,
        order_type=OrderType.MARKET,
        quantity=10
    )

    result = execution_engine.execute_order(signal)

    assert result.success is False
    assert result.status == OrderStatus.FAILED


def test_cancel_order(execution_engine, mock_broker):
    """주문 취소 테스트"""
    # 먼저 주문 실행
    signal = OrderSignal(
        symbol="TSLA",
        action=OrderAction.BUY,
        order_type=OrderType.LIMIT,
        quantity=10,
        limit_price=200.0
    )

    result = execution_engine.execute_order(signal)
    order_id = result.order_id

    # 주문 취소
    success = execution_engine.cancel_order(order_id)

    assert success is True


def test_get_order_status(execution_engine):
    """주문 상태 조회 테스트"""
    signal = OrderSignal(
        symbol="TSLA",
        action=OrderAction.BUY,
        order_type=OrderType.MARKET,
        quantity=10
    )

    result = execution_engine.execute_order(signal)
    status = execution_engine.get_order_status(result.order_id)

    assert status is not None
    assert status == OrderStatus.FILLED


def test_get_positions(execution_engine):
    """포지션 조회 테스트"""
    positions = execution_engine.get_positions()
    assert isinstance(positions, list)


def test_get_account(execution_engine):
    """계좌 조회 테스트"""
    account = execution_engine.get_account()
    assert account is not None
    assert account.account_id == "test"
    assert account.equity == 10000.0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
