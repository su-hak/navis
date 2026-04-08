"""
빠른 동작 확인 테스트
패키지 의존성 없이 핵심 로직만 테스트
"""
import sys
import os

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

print("=" * 60)
print("주문 실행 팀 - 빠른 동작 확인")
print("=" * 60)

# 1. 모듈 임포트 테스트
print("\n[1] 모듈 임포트 테스트...")
try:
    from execution_team.core.order_models import (
        OrderSignal, Order, OrderResult, OrderStatus,
        OrderAction, OrderType, TimeInForce
    )
    print("✓ order_models 임포트 성공")
except Exception as e:
    print(f"✗ order_models 임포트 실패: {e}")
    sys.exit(1)

try:
    from execution_team.core.order_manager import OrderManager
    print("✓ order_manager 임포트 성공")
except Exception as e:
    print(f"✗ order_manager 임포트 실패: {e}")
    sys.exit(1)

try:
    from execution_team.brokers.broker_interface import BrokerInterface
    print("✓ broker_interface 임포트 성공")
except Exception as e:
    print(f"✗ broker_interface 임포트 실패: {e}")
    sys.exit(1)

# 2. 데이터 모델 테스트
print("\n[2] 데이터 모델 테스트...")
try:
    # OrderSignal 생성
    signal = OrderSignal(
        symbol="AAPL",
        action=OrderAction.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
        strategy_id="test_strategy"
    )
    print(f"✓ OrderSignal 생성 성공: {signal.action.value} {signal.quantity} {signal.symbol}")

    # Order 생성
    order = Order(
        symbol=signal.symbol,
        action=signal.action,
        order_type=signal.order_type,
        quantity=signal.quantity,
        strategy_id=signal.strategy_id
    )
    print(f"✓ Order 생성 성공: ID={order.order_id[:8]}..., Status={order.status.value}")

    # OrderResult 생성
    result = OrderResult(
        success=True,
        order_id=order.order_id,
        status=OrderStatus.FILLED,
        filled_quantity=10,
        filled_price=180.50
    )
    print(f"✓ OrderResult 생성 성공: Success={result.success}, Price=${result.filled_price}")

except Exception as e:
    print(f"✗ 데이터 모델 테스트 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 3. OrderManager 테스트
print("\n[3] OrderManager 테스트...")
try:
    import tempfile
    temp_dir = tempfile.mkdtemp()

    manager = OrderManager(storage_path=temp_dir)
    print(f"✓ OrderManager 초기화 성공")

    # 주문 생성 및 등록
    test_signal = OrderSignal(
        symbol="TSLA",
        action=OrderAction.BUY,
        order_type=OrderType.MARKET,
        quantity=5
    )

    test_order = manager.create_order(test_signal)
    print(f"✓ 주문 생성 및 등록 성공: ID={test_order.order_id[:8]}...")

    # 주문 조회
    retrieved_order = manager.get_order(test_order.order_id)
    assert retrieved_order is not None
    print(f"✓ 주문 조회 성공: {retrieved_order.symbol}")

    # 상태 업데이트
    manager.update_status(test_order.order_id, OrderStatus.SUBMITTED)
    retrieved_order = manager.get_order(test_order.order_id)
    assert retrieved_order.status == OrderStatus.SUBMITTED
    print(f"✓ 상태 업데이트 성공: {retrieved_order.status.value}")

    # 체결 정보 업데이트
    manager.update_filled(test_order.order_id, 5, 210.50, 0.0)
    retrieved_order = manager.get_order(test_order.order_id)
    assert retrieved_order.filled_quantity == 5
    assert retrieved_order.status == OrderStatus.FILLED
    print(f"✓ 체결 정보 업데이트 성공: {retrieved_order.filled_quantity}주 @ ${retrieved_order.filled_price}")

    # 통계 조회
    stats = manager.get_stats()
    print(f"✓ 통계 조회 성공: 총 {stats['total']}개 주문, 성공률 {stats['success_rate']:.1f}%")

    # 정리
    import shutil
    shutil.rmtree(temp_dir)

except Exception as e:
    print(f"✗ OrderManager 테스트 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 4. Mock 브로커 테스트
print("\n[4] Mock 브로커 테스트...")
try:
    from execution_team.core.order_models import AccountInfo, Position

    class MockBroker(BrokerInterface):
        """테스트용 Mock 브로커"""

        def __init__(self, config):
            super().__init__(config)
            self.orders = []

        def connect(self):
            self._initialized = True
            return True

        def disconnect(self):
            self._initialized = False

        def submit_order(self, order):
            self.orders.append(order)
            return f"MOCK_{len(self.orders)}"

        def get_order(self, broker_order_id):
            return {
                'status': OrderStatus.FILLED,
                'filled_quantity': 10,
                'filled_price': 210.0,
                'commission': 0.0
            }

        def cancel_order(self, broker_order_id):
            return True

        def get_account(self):
            return AccountInfo(
                account_id="mock_account",
                cash=10000.0,
                portfolio_value=10000.0,
                buying_power=10000.0,
                equity=10000.0,
                unrealized_pl=0.0,
                realized_pl=0.0
            )

        def get_positions(self):
            return []

        def get_position(self, symbol):
            return None

        def is_market_open(self):
            return True

        def get_current_price(self, symbol):
            return 210.0

    # Mock 브로커 생성 및 연결
    broker = MockBroker({'test': 'config'})
    broker.connect()
    print(f"✓ Mock 브로커 연결 성공")

    # 주문 제출
    mock_order = Order(
        symbol="NVDA",
        action=OrderAction.BUY,
        order_type=OrderType.MARKET,
        quantity=3
    )
    broker_order_id = broker.submit_order(mock_order)
    print(f"✓ 주문 제출 성공: {broker_order_id}")

    # 계좌 조회
    account = broker.get_account()
    print(f"✓ 계좌 조회 성공: 자산 ${account.equity:,.2f}")

    # 주문 조회
    order_info = broker.get_order(broker_order_id)
    print(f"✓ 주문 조회 성공: {order_info['status'].value}")

    broker.disconnect()
    print(f"✓ Mock 브로커 연결 해제 성공")

except Exception as e:
    print(f"✗ Mock 브로커 테스트 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 5. ExecutionEngine 테스트 (Mock 브로커 사용)
print("\n[5] ExecutionEngine 테스트...")
try:
    from execution_team.core.execution_engine import ExecutionEngine

    # Mock 브로커 및 주문 관리자 생성
    temp_dir = tempfile.mkdtemp()
    broker = MockBroker({'test': 'config'})
    broker.connect()
    manager = OrderManager(storage_path=temp_dir)

    # ExecutionEngine 생성
    engine = ExecutionEngine(
        broker=broker,
        order_manager=manager,
        enable_circuit_breaker=False  # 테스트용
    )
    print(f"✓ ExecutionEngine 초기화 성공")

    # 주문 실행
    signal = OrderSignal(
        symbol="AAPL",
        action=OrderAction.BUY,
        order_type=OrderType.MARKET,
        quantity=10,
        strategy_id="test_strategy"
    )

    result = engine.execute_order(signal)
    print(f"✓ 주문 실행 성공: ID={result.order_id[:8]}...")
    print(f"  - 성공 여부: {result.success}")
    print(f"  - 상태: {result.status.value}")
    print(f"  - 체결가: ${result.filled_price}")
    print(f"  - 체결 수량: {result.filled_quantity}주")

    # 계좌 조회
    account = engine.get_account()
    print(f"✓ 계좌 조회: 자산 ${account.equity:,.2f}")

    # 통계 조회
    stats = engine.get_execution_stats()
    print(f"✓ 통계: {stats['total']}개 주문, 성공률 {stats['success_rate']:.1f}%")

    # 정리
    broker.disconnect()
    shutil.rmtree(temp_dir)

except Exception as e:
    print(f"✗ ExecutionEngine 테스트 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 6. 재시도 핸들러 테스트
print("\n[6] 재시도 핸들러 테스트...")
try:
    from execution_team.utils.retry_handler import RetryHandler, RetryConfig, CircuitBreaker
    from execution_team.core.order_models import BrokerError

    # RetryConfig 생성
    config = RetryConfig(max_attempts=3, base_delay=0.1, max_delay=1.0)
    handler = RetryHandler(config)
    print(f"✓ RetryHandler 생성 성공")

    # 성공 케이스
    def success_func():
        return "success"

    result = handler.retry(success_func)
    assert result == "success"
    print(f"✓ 재시도 핸들러 성공 케이스 통과")

    # 실패 후 성공 케이스
    call_count = [0]
    def fail_then_success():
        call_count[0] += 1
        if call_count[0] < 2:
            raise BrokerError("Temporary error", retryable=True)
        return "success after retry"

    result = handler.retry(fail_then_success, retryable_exceptions=(BrokerError,))
    assert result == "success after retry"
    print(f"✓ 재시도 후 성공 케이스 통과 ({call_count[0]}회 시도)")

    # 서킷 브레이커 테스트
    breaker = CircuitBreaker(failure_threshold=3, recovery_timeout=0.1)
    print(f"✓ CircuitBreaker 생성 성공")

    # 성공 케이스
    result = breaker.call(success_func)
    assert result == "success"
    print(f"✓ 서킷 브레이커 정상 동작 확인")

except Exception as e:
    print(f"✗ 재시도 핸들러 테스트 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

# 최종 결과
print("\n" + "=" * 60)
print("✅ 모든 테스트 성공!")
print("=" * 60)
print("\n주요 확인 사항:")
print("  ✓ 모든 모듈 정상 임포트")
print("  ✓ 데이터 모델 정상 동작")
print("  ✓ OrderManager 정상 동작")
print("  ✓ Mock 브로커 정상 동작")
print("  ✓ ExecutionEngine 정상 동작")
print("  ✓ 재시도 핸들러 정상 동작")
print("\n주문 실행 팀 구현이 정상적으로 작동합니다!")
print("=" * 60)
