"""
Alpaca API 속성 디버깅 스크립트
실제 API에서 반환하는 속성들을 확인
"""
import sys
import os
from dotenv import load_dotenv

# 환경 변수 로드
load_dotenv()

try:
    import alpaca_trade_api as tradeapi
except ImportError:
    print("alpaca-trade-api 패키지가 설치되지 않았습니다.")
    print("pip install alpaca-trade-api")
    sys.exit(1)

def debug_alpaca_account():
    """Alpaca 계좌 객체의 실제 속성 확인"""

    api_key = os.getenv('ALPACA_API_KEY')
    secret_key = os.getenv('ALPACA_SECRET_KEY')
    base_url = os.getenv('ALPACA_BASE_URL', 'https://paper-api.alpaca.markets')

    if not api_key or not secret_key:
        print("⚠ ALPACA_API_KEY 또는 ALPACA_SECRET_KEY가 설정되지 않았습니다.")
        return

    print("=" * 70)
    print("Alpaca API 속성 디버깅")
    print("=" * 70)

    try:
        # API 연결
        api = tradeapi.REST(
            key_id=api_key,
            secret_key=secret_key,
            base_url=base_url,
            api_version='v2'
        )

        print("\n[1] 계좌 정보 조회...")
        account = api.get_account()

        print("\n✓ 계좌 객체 타입:", type(account).__name__)
        print("\n사용 가능한 모든 속성:")
        print("-" * 70)

        # 모든 속성 출력
        for attr in dir(account):
            if not attr.startswith('_'):  # 내부 속성 제외
                try:
                    value = getattr(account, attr)
                    if not callable(value):  # 메서드 제외
                        print(f"  • {attr}: {value} (타입: {type(value).__name__})")
                except Exception as e:
                    print(f"  • {attr}: <접근 실패: {e}>")

        # 주요 속성 확인
        print("\n" + "=" * 70)
        print("주요 속성 확인:")
        print("-" * 70)

        important_attrs = [
            'id', 'cash', 'portfolio_value', 'buying_power', 'equity',
            'unrealized_pl', 'unrealized_plpc', 'realized_pl',
            'daytrade_count', 'pattern_day_trader', 'status'
        ]

        for attr in important_attrs:
            value = getattr(account, attr, '❌ 속성 없음')
            print(f"  {attr}: {value}")

        # 포지션 확인
        print("\n" + "=" * 70)
        print("[2] 포지션 확인...")
        print("-" * 70)

        try:
            positions = api.list_positions()
            print(f"\n✓ 현재 포지션 수: {len(positions)}개")

            if len(positions) > 0:
                print("\n첫 번째 포지션의 속성:")
                pos = positions[0]
                for attr in dir(pos):
                    if not attr.startswith('_'):
                        try:
                            value = getattr(pos, attr)
                            if not callable(value):
                                print(f"  • {attr}: {value}")
                        except:
                            pass
            else:
                print("  포지션이 없습니다.")
        except Exception as e:
            print(f"  ⚠ 포지션 조회 실패: {e}")

        print("\n" + "=" * 70)
        print("✅ 디버깅 완료")
        print("=" * 70)

    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    debug_alpaca_account()
