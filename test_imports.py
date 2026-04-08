"""
임포트 테스트 스크립트
"""
import sys
from pathlib import Path

# 현재 디렉토리를 Python 경로에 추가
current_dir = Path(__file__).parent
if str(current_dir) not in sys.path:
    sys.path.insert(0, str(current_dir))

print("=" * 70)
print("임포트 테스트 시작")
print("=" * 70)

try:
    print("\n[1] execution_team.core 임포트 테스트...")
    from execution_team.core import ExecutionEngine, OrderManager, OrderSignal, OrderAction, OrderType
    print("✓ execution_team.core 임포트 성공")
except Exception as e:
    print(f"✗ execution_team.core 임포트 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n[2] execution_team.brokers 임포트 테스트...")
    from execution_team.brokers import AlpacaBroker
    print("✓ execution_team.brokers 임포트 성공")
except Exception as e:
    print(f"✗ execution_team.brokers 임포트 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n[3] data_collection.monitoring 임포트 테스트...")
    from data_collection.monitoring import WatchlistGenerator, HighFrequencyMonitor
    print("✓ data_collection.monitoring 임포트 성공")
except Exception as e:
    print(f"✗ data_collection.monitoring 임포트 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n[4] utils 임포트 테스트...")
    from utils import RiskManager, RiskConfig
    print("✓ utils 임포트 성공")
except Exception as e:
    print(f"✗ utils 임포트 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

try:
    print("\n[5] strategy_engine.multi_strategy 임포트 테스트...")
    from strategy_engine.multi_strategy import StrategyManager, StrategyConfig
    print("✓ strategy_engine.multi_strategy 임포트 성공")
except Exception as e:
    print(f"✗ strategy_engine.multi_strategy 임포트 실패: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

print("\n" + "=" * 70)
print("✓ 모든 임포트 테스트 성공!")
print("=" * 70)
