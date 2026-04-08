"""
빠른 테스트 - 전략 엔진 동작 확인

의존성 없이 간단하게 모듈이 제대로 import되는지 확인합니다.
"""

import sys
import os

# 프로젝트 루트를 path에 추가
project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, project_root)

print("=" * 60)
print("전략 엔진 모듈 Import 테스트")
print("=" * 60)

try:
    print("\n1. Indicators 모듈 테스트...")
    from strategy_engine.indicators import TechnicalIndicators
    print("   ✅ TechnicalIndicators import 성공")

    print("\n2. Filters 모듈 테스트...")
    from strategy_engine.filters import StockFilter, FilterCriteria
    print("   ✅ StockFilter import 성공")

    print("\n3. Scoring 모듈 테스트...")
    from strategy_engine.scoring import ScoreCalculator, ScoreWeights
    print("   ✅ ScoreCalculator import 성공")

    print("\n4. Signals 모듈 테스트...")
    from strategy_engine.signals import SignalGenerator, Signal, SignalType
    print("   ✅ SignalGenerator import 성공")

    print("\n5. API 모듈 테스트...")
    from strategy_engine.api import StrategyEngineAPI
    print("   ✅ StrategyEngineAPI import 성공")

    print("\n" + "=" * 60)
    print("🎉 모든 모듈 Import 성공!")
    print("=" * 60)

    print("\n다음 단계:")
    print("1. pandas, numpy 설치: pip install pandas numpy ta")
    print("2. 전체 테스트 실행: python strategy_engine/tests/test_strategy_engine.py")
    print("3. 예제 실행: python strategy_engine/example.py")

except ImportError as e:
    print(f"\n❌ Import 실패: {e}")
    print("\n해결 방법:")
    print("1. 현재 디렉토리가 C:\\navis인지 확인")
    print("2. 프로젝트 루트에서 실행: cd C:\\navis")
    print("3. 다시 시도: python strategy_engine/quick_test.py")
    sys.exit(1)

except Exception as e:
    print(f"\n❌ 오류 발생: {e}")
    sys.exit(1)
