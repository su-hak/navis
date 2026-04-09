"""
QA 팀 메인 실행 스크립트

사용법:
    python qa_team/run_qa.py                    # 전체 QA 실행
    python qa_team/run_qa.py --backtest-only    # 백테스트만
    python qa_team/run_qa.py --pipeline-only    # 페이퍼 트레이딩만
    python qa_team/run_qa.py --report           # 리포트 생성 및 저장
"""
import sys
import os
import argparse
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def run_all_tests():
    """pytest 전체 테스트 실행"""
    import subprocess
    print("=" * 60)
    print("QA 팀 - 전체 테스트 실행")
    print("=" * 60)
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "tests/", "-v", "--tb=short"],
        cwd=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    )
    return result.returncode == 0


def run_backtest_demo():
    """백테스트 데모 실행"""
    import numpy as np
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tests.conftest import make_ohlcv
    from qa_team.backtest import BacktestEngine, BacktestConfig

    print("\n" + "=" * 60)
    print("백테스트 시뮬레이션")
    print("=" * 60)

    # 데모용: 시뮬레이션 데이터에 맞게 임계값 조정 (실제 운용 시 75점 사용)
    config = BacktestConfig(initial_capital=1_000_000, buy_score_threshold=58.0)
    engine = BacktestEngine(config)

    from tests.conftest import make_signal_friendly_ohlcv

    scenarios = [
        ("상승장_강세", "signal_friendly", 42),
        ("하락장", "down", 20),
        ("횡보장", "sideways", 30),
    ]

    for name, trend, seed in scenarios:
        if trend == "signal_friendly":
            df = make_signal_friendly_ohlcv(300, seed=seed)
        else:
            df = make_ohlcv(300, trend, seed=seed)
        try:
            result = engine.run(symbol=name, df=df)
            print(result.summary())
            print()
        except Exception as e:
            print(f"{name}: 오류 - {e}")


def run_paper_trading_demo():
    """페이퍼 트레이딩 데모 실행"""
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    from tests.conftest import make_ohlcv
    from qa_team.paper_trading import PaperTradingSimulator

    print("\n" + "=" * 60)
    print("페이퍼 트레이딩 검증")
    print("=" * 60)

    simulator = PaperTradingSimulator()

    # 시나리오 1: 정상 매수
    print("\n[시나리오 1] 정상 매수 주문")
    simulator.risk_manager.initialize_trading_day(1_000_000)
    result = simulator.run_scenario("정상 매수", [
        {'symbol': 'TSLA', 'action': 'BUY', 'quantity': 5, 'price': 210.0, 'score': 82.0},
        {'symbol': 'NVDA', 'action': 'BUY', 'quantity': 2, 'price': 500.0, 'score': 78.0},
    ])
    print(result.summary())

    # 시나리오 2: 일일 손실 한도 초과
    print("\n[시나리오 2] 일일 손실 한도 초과 후 주문 차단")
    sim2 = PaperTradingSimulator()
    sim2.risk_manager.initialize_trading_day(1_000_000)
    sim2.risk_manager.daily_tracker.record_realized_trade(-60_000)  # -6% 손실
    result2 = sim2.run_scenario("한도 초과", [
        {'symbol': 'AAPL', 'action': 'BUY', 'quantity': 10, 'price': 180.0, 'score': 80.0},
    ])
    print(result2.summary())

    # 시나리오 3: 전체 파이프라인
    print("\n[시나리오 3] 실전 파이프라인 (전략 엔진 포함)")
    sim3 = PaperTradingSimulator()
    df = make_ohlcv(250, "up", seed=42)
    result3 = sim3.run_full_pipeline_test("AAPL", df)
    print(result3.summary())


def generate_report():
    """전체 리포트 생성"""
    from qa_team.report import QAReporter

    reporter = QAReporter()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
        "qa_team", "reports", f"qa_report_{timestamp}.txt"
    )
    report = reporter.generate_report(output_file=output_path)
    print(report)
    return report


def main():
    parser = argparse.ArgumentParser(description="QA 팀 테스트 실행")
    parser.add_argument("--backtest-only", action="store_true", help="백테스트만 실행")
    parser.add_argument("--pipeline-only", action="store_true", help="페이퍼 트레이딩만 실행")
    parser.add_argument("--report", action="store_true", help="통합 리포트 생성")
    parser.add_argument("--all", action="store_true", help="전체 실행 (기본)")
    args = parser.parse_args()

    if args.backtest_only:
        run_backtest_demo()
    elif args.pipeline_only:
        run_paper_trading_demo()
    elif args.report:
        generate_report()
    else:
        # 기본: pytest + 데모
        passed = run_all_tests()
        run_backtest_demo()
        run_paper_trading_demo()
        sys.exit(0 if passed else 1)


if __name__ == "__main__":
    main()
