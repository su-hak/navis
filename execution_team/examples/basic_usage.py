"""
주문 실행 팀 - 기본 사용 예제

이 예제는 주문 실행 엔진의 기본적인 사용법을 보여줍니다.
"""
import sys
import logging
from pathlib import Path

# 프로젝트 루트를 경로에 추가
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from execution_team.core import (
    ExecutionEngine, OrderManager, OrderSignal,
    OrderAction, OrderType, TimeInForce
)
from execution_team.brokers import AlpacaBroker
from execution_team.config import config

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def main():
    """메인 함수"""

    print("=" * 60)
    print("주문 실행 팀 - 기본 사용 예제")
    print("=" * 60)

    # 1. 브로커 초기화
    print("\n[1] 브로커 연결 중...")
    try:
        broker_config = {
            'api_key': config.broker.api_key,
            'secret_key': config.broker.secret_key,
            'base_url': config.broker.base_url
        }
        broker = AlpacaBroker(broker_config)
        broker.connect()
        print("✓ 브로커 연결 성공")
    except Exception as e:
        print(f"✗ 브로커 연결 실패: {e}")
        return

    # 2. 주문 관리자 초기화
    print("\n[2] 주문 관리자 초기화 중...")
    order_manager = OrderManager(storage_path="logs/execution/orders")
    print("✓ 주문 관리자 초기화 완료")

    # 3. 실행 엔진 초기화
    print("\n[3] 실행 엔진 초기화 중...")
    engine = ExecutionEngine(
        broker=broker,
        order_manager=order_manager,
        enable_circuit_breaker=True
    )
    print("✓ 실행 엔진 초기화 완료")

    # 4. 계좌 정보 조회
    print("\n[4] 계좌 정보 조회 중...")
    account = engine.get_account()
    if account:
        print(f"✓ 계좌 ID: {account.account_id}")
        print(f"  현금: ${account.cash:,.2f}")
        print(f"  자산 총액: ${account.equity:,.2f}")
        print(f"  매수 가능 금액: ${account.buying_power:,.2f}")
    else:
        print("✗ 계좌 정보 조회 실패")
        return

    # 5. 시장가 매수 주문 실행 (예시)
    print("\n[5] 시장가 매수 주문 실행 중...")

    # 주문 신호 생성
    buy_signal = OrderSignal(
        symbol="AAPL",              # 애플 주식
        action=OrderAction.BUY,     # 매수
        order_type=OrderType.MARKET,  # 시장가
        quantity=1,                 # 1주
        strategy_id="example_strategy",
        reason="기본 사용 예제"
    )

    print(f"  주문: {buy_signal.action.value} {buy_signal.quantity} {buy_signal.symbol}")

    # 실제 주문 실행 (주석 처리 - 실제 실행 시 주석 해제)
    # result = engine.execute_order(buy_signal)
    #
    # if result.success:
    #     print(f"✓ 주문 실행 성공")
    #     print(f"  주문 ID: {result.order_id}")
    #     print(f"  상태: {result.status.value}")
    #     if result.filled_price:
    #         print(f"  체결가: ${result.filled_price:.2f}")
    #     print(f"  실행 시간: {result.execution_time_ms:.2f}ms")
    # else:
    #     print(f"✗ 주문 실행 실패: {result.error_message}")

    print("\n  ⚠ 실제 주문을 실행하려면 코드의 주석을 해제하세요")

    # 6. 지정가 매수 주문 예시
    print("\n[6] 지정가 매수 주문 예시")

    limit_signal = OrderSignal(
        symbol="TSLA",
        action=OrderAction.BUY,
        order_type=OrderType.LIMIT,
        quantity=1,
        limit_price=200.0,          # 지정가 $200
        time_in_force=TimeInForce.DAY,
        strategy_id="example_strategy",
        reason="지정가 매수 예제"
    )

    print(f"  주문: {limit_signal.action.value} {limit_signal.quantity} {limit_signal.symbol} @ ${limit_signal.limit_price}")
    print("  ⚠ 실제 주문을 실행하려면 코드의 주석을 해제하세요")

    # 7. 현재 포지션 조회
    print("\n[7] 현재 포지션 조회 중...")
    positions = engine.get_positions()
    if positions:
        print(f"✓ {len(positions)}개의 포지션 보유 중")
        for pos in positions:
            print(f"  {pos.symbol}: {pos.quantity}주 @ ${pos.avg_entry_price:.2f}")
            print(f"    현재가: ${pos.current_price:.2f}")
            print(f"    평가손익: ${pos.unrealized_pl:.2f} ({pos.unrealized_pl_percent:.2f}%)")
    else:
        print("  포지션 없음")

    # 8. 주문 통계
    print("\n[8] 주문 통계")
    stats = engine.get_execution_stats()
    print(f"  전체 주문: {stats['total']}개")
    print(f"  상태별 분포: {stats['by_status']}")
    print(f"  성공률: {stats['success_rate']:.2f}%")

    # 9. 정리
    print("\n[9] 정리 중...")
    broker.disconnect()
    print("✓ 브로커 연결 해제")

    print("\n" + "=" * 60)
    print("예제 실행 완료")
    print("=" * 60)


if __name__ == "__main__":
    main()
