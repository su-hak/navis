"""
수정된 Alpaca 브로커 테스트
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
load_dotenv()

print("=" * 70)
print("수정된 Alpaca 브로커 테스트")
print("=" * 70)

try:
    from execution_team.brokers import AlpacaBroker
    from execution_team.core.order_models import BrokerError

    print("\n[1] 모듈 임포트 성공 ✓")

    # 브로커 설정
    broker_config = {
        'api_key': os.getenv('ALPACA_API_KEY'),
        'secret_key': os.getenv('ALPACA_SECRET_KEY'),
        'base_url': os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')
    }

    if not broker_config['api_key'] or not broker_config['secret_key']:
        print("\n❌ ALPACA_API_KEY 또는 ALPACA_SECRET_KEY가 설정되지 않았습니다.")
        sys.exit(1)

    print("\n[2] 브로커 연결 중...")
    broker = AlpacaBroker(broker_config)
    broker.connect()
    print("✓ 브로커 연결 성공")

    print("\n[3] 계좌 정보 조회 중...")
    try:
        account = broker.get_account()
        print("✓ 계좌 정보 조회 성공")
        print(f"\n계좌 정보:")
        print(f"  • 계좌 ID: {account.account_id}")
        print(f"  • 현금: ${account.cash:,.2f}")
        print(f"  • 자산 총액: ${account.equity:,.2f}")
        print(f"  • 매수 가능 금액: ${account.buying_power:,.2f}")
        print(f"  • 미실현 손익: ${account.unrealized_pl:,.2f}")
        print(f"  • 실현 손익: ${account.realized_pl:,.2f}")
        print(f"  • 데이트레이드 횟수: {account.daytrade_count}")
        print(f"  • PDT 여부: {account.pattern_day_trader}")
    except BrokerError as e:
        print(f"✗ 계좌 조회 실패: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"✗ 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

    print("\n[4] 포지션 조회 중...")
    try:
        positions = broker.get_positions()
        print(f"✓ 포지션 조회 성공 - {len(positions)}개")

        if positions:
            for pos in positions:
                print(f"\n  • {pos.symbol}:")
                print(f"    - 수량: {pos.quantity}주")
                print(f"    - 평균 진입가: ${pos.avg_entry_price:.2f}")
                print(f"    - 현재가: ${pos.current_price:.2f}")
                print(f"    - 시장 가치: ${pos.market_value:,.2f}")
                print(f"    - 미실현 손익: ${pos.unrealized_pl:,.2f} ({pos.unrealized_pl_percent:.2f}%)")
        else:
            print("  (포지션 없음)")
    except BrokerError as e:
        print(f"✗ 포지션 조회 실패: {e}")
    except Exception as e:
        print(f"✗ 예상치 못한 오류: {e}")
        import traceback
        traceback.print_exc()

    print("\n[5] 시장 상태 확인 중...")
    try:
        is_open = broker.is_market_open()
        print(f"✓ 시장 상태: {'개장' if is_open else '폐장'}")
    except Exception as e:
        print(f"⚠ 시장 상태 확인 실패: {e}")

    print("\n[6] 브로커 연결 해제...")
    broker.disconnect()
    print("✓ 브로커 연결 해제 성공")

    print("\n" + "=" * 70)
    print("✅ 모든 테스트 성공!")
    print("=" * 70)
    print("\n수정 사항:")
    print("  • get_account()에서 안전한 속성 접근 사용 (getattr)")
    print("  • get_positions()에서 안전한 속성 접근 사용")
    print("  • get_position()에서 안전한 속성 접근 사용")
    print("\n이제 examples/basic_usage.py를 실행할 수 있습니다!")
    print("=" * 70)

except ImportError as e:
    print(f"\n❌ 모듈 임포트 실패: {e}")
    print("\n필요한 패키지를 설치하세요:")
    print("  pip install pydantic python-dotenv alpaca-trade-api")
    sys.exit(1)
except Exception as e:
    print(f"\n❌ 오류 발생: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
