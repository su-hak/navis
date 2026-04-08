"""
자동매매 상태 확인 스크립트

현재 계좌 상태, 포지션, 주문 현황을 확인합니다.
"""
import sys
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

try:
    from execution_team.core import ExecutionEngine, OrderManager
    from execution_team.brokers import AlpacaBroker
except ImportError as e:
    print(f"❌ 모듈 임포트 실패: {e}")
    sys.exit(1)


def main():
    """메인 함수"""
    print("=" * 70)
    print("자동매매 상태 확인")
    print("=" * 70)

    try:
        # 브로커 연결
        print("\n[1] 브로커 연결 중...")
        broker_config = {
            'api_key': os.getenv('ALPACA_API_KEY'),
            'secret_key': os.getenv('ALPACA_SECRET_KEY'),
            'base_url': os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
        }

        if not broker_config['api_key'] or not broker_config['secret_key']:
            print("❌ ALPACA_API_KEY 또는 ALPACA_SECRET_KEY가 설정되지 않았습니다.")
            sys.exit(1)

        broker = AlpacaBroker(broker_config)
        broker.connect()
        print(f"✓ 브로커 연결 성공 ({broker_config['base_url']})")

        # 주문 관리자
        order_manager = OrderManager(
            storage_path=os.getenv('ORDER_STORAGE_PATH', 'logs/execution/orders')
        )

        # 실행 엔진
        engine = ExecutionEngine(
            broker=broker,
            order_manager=order_manager,
            enable_circuit_breaker=False
        )

        # 계좌 정보
        print("\n[2] 계좌 정보")
        print("-" * 70)
        account = engine.get_account()
        print(f"  • 계좌 ID: {account.account_id}")
        print(f"  • 현금: ${account.cash:,.2f}")
        print(f"  • 자산 총액: ${account.equity:,.2f}")
        print(f"  • 포트폴리오 가치: ${account.portfolio_value:,.2f}")
        print(f"  • 매수 가능 금액: ${account.buying_power:,.2f}")
        print(f"  • 미실현 손익: ${account.unrealized_pl:,.2f}")
        print(f"  • 실현 손익: ${account.realized_pl:,.2f}")
        print(f"  • 데이트레이드 횟수: {account.daytrade_count}")
        print(f"  • PDT 여부: {'예' if account.pattern_day_trader else '아니오'}")

        # 포지션
        print("\n[3] 현재 포지션")
        print("-" * 70)
        positions = engine.get_positions()

        if positions:
            print(f"✓ {len(positions)}개의 포지션 보유 중\n")
            for pos in positions:
                pl_sign = "+" if pos.unrealized_pl >= 0 else ""
                print(f"  [{pos.symbol}]")
                print(f"    • 수량: {pos.quantity}주")
                print(f"    • 평균 진입가: ${pos.avg_entry_price:.2f}")
                print(f"    • 현재가: ${pos.current_price:.2f}")
                print(f"    • 시장 가치: ${pos.market_value:,.2f}")
                print(f"    • 미실현 손익: {pl_sign}${pos.unrealized_pl:,.2f} ({pl_sign}{pos.unrealized_pl_percent:.2f}%)")
                print()
        else:
            print("  포지션 없음")

        # 주문 통계
        print("\n[4] 주문 통계")
        print("-" * 70)
        stats = engine.get_execution_stats()
        print(f"  • 총 주문 수: {stats['total']}개")
        print(f"  • 성공률: {stats['success_rate']:.1f}%")

        if stats['by_status']:
            print("\n  상태별 분포:")
            for status, count in stats['by_status'].items():
                print(f"    - {status}: {count}개")

        if stats['by_symbol']:
            print("\n  종목별 분포:")
            for symbol, count in stats['by_symbol'].items():
                print(f"    - {symbol}: {count}개")

        # 자동매매 설정
        print("\n[5] 자동매매 설정")
        print("-" * 70)
        auto_enabled = os.getenv('AUTO_TRADING_ENABLED', 'false').lower() == 'true'
        print(f"  • 자동매매: {'활성화 ✓' if auto_enabled else '비활성화 ✗'}")

        if auto_enabled:
            # 퍼센트 기반 설정 표시
            investment_pct = float(os.getenv('MAX_INVESTMENT_PERCENT', '10.0'))
            loss_pct = float(os.getenv('MAX_DAILY_LOSS_PERCENT', '5.0'))

            # 현재 현금 기준 실제 금액 계산
            investment_amount = account.cash * (investment_pct / 100.0)
            loss_amount = account.cash * (loss_pct / 100.0)

            print(f"  • 1회 최대 투자: 현금의 {investment_pct}% (현재: ${investment_amount:,.2f})")
            print(f"  • 1일 최대 손실: 현금의 {loss_pct}% (현재: ${loss_amount:,.2f})")
            print(f"  • 최대 동시 보유: {int(os.getenv('MAX_POSITIONS', '5'))}개")
            print(f"  • 분석 주기: {int(os.getenv('TRADING_INTERVAL_MINUTES', '60'))}분")

        # 시장 상태
        print("\n[6] 시장 상태")
        print("-" * 70)
        is_open = broker.is_market_open()
        print(f"  • 미국 주식 시장: {'개장 중 🟢' if is_open else '폐장 중 🔴'}")

        if not is_open:
            print("\n  ⚠️ 시장이 폐장 중입니다.")
            print("  • 미국 주식 시장 시간: 월~금 9:30 AM - 4:00 PM ET")
            print("  • 한국 시간: 23:30 - 06:00 (서머타임 22:30 - 05:00)")

        # 브로커 연결 해제
        broker.disconnect()

        print("\n" + "=" * 70)
        print("✓ 상태 확인 완료")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
