"""
QA 테스트 리포트 생성기

산출물: 테스트 리포트 + 전략 검증 결과
"""
import sys
import os
import subprocess
import json
from datetime import datetime
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))


@dataclass
class TestSuiteResult:
    """테스트 스위트 결과"""
    suite_name: str
    total: int
    passed: int
    failed: int
    skipped: int
    errors: int
    duration_sec: float
    failed_tests: List[str] = field(default_factory=list)

    @property
    def pass_rate(self) -> float:
        return self.passed / self.total * 100 if self.total > 0 else 0.0

    @property
    def is_passing(self) -> bool:
        return self.failed == 0 and self.errors == 0


class QAReporter:
    """
    QA 팀 통합 리포트 생성기

    pytest 결과 + 백테스트 결과 + 페이퍼 트레이딩 결과를
    통합하여 최종 QA 리포트를 생성합니다.
    """

    def __init__(self, project_root: Optional[str] = None):
        self.project_root = project_root or os.path.dirname(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        )
        self.report_timestamp = datetime.now()

    def run_pytest(self, test_dir: str = "tests", verbose: bool = False) -> Dict[str, Any]:
        """
        pytest 실행 및 결과 수집

        Returns:
            pytest 실행 결과 딕셔너리
        """
        cmd = [
            sys.executable, "-m", "pytest",
            test_dir,
            "--tb=short",
            "-q",
        ]
        if verbose:
            cmd.append("-v")

        try:
            result = subprocess.run(
                cmd,
                cwd=self.project_root,
                capture_output=True,
                text=True,
                timeout=300,
            )
            return {
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr,
                'passed': result.returncode == 0,
            }
        except subprocess.TimeoutExpired:
            return {'returncode': -1, 'stdout': '', 'stderr': 'TIMEOUT', 'passed': False}
        except Exception as e:
            return {'returncode': -1, 'stdout': '', 'stderr': str(e), 'passed': False}

    def run_backtest_report(self, symbols: Optional[List[str]] = None) -> Dict[str, Any]:
        """
        백테스트 실행 및 결과 수집

        Args:
            symbols: 테스트할 종목 목록 (None이면 기본 종목)

        Returns:
            {심볼: 백테스트 결과 딕셔너리}
        """
        from qa_team.backtest import BacktestEngine, BacktestConfig
        import numpy as np

        config = BacktestConfig(initial_capital=1_000_000)
        engine = BacktestEngine(config)

        # 시뮬레이션 데이터로 테스트
        np.random.seed(42)
        test_symbols = symbols or ['SIM_BULL', 'SIM_BEAR', 'SIM_SIDEWAYS']

        results = {}
        from tests.conftest import make_ohlcv

        trend_map = {
            'SIM_BULL': 'up',
            'SIM_BEAR': 'down',
            'SIM_SIDEWAYS': 'sideways',
        }

        for sym in test_symbols:
            trend = trend_map.get(sym, 'up')
            df = make_ohlcv(300, trend, seed=42)
            try:
                result = engine.run(symbol=sym, df=df)
                results[sym] = {
                    'total_return_pct': result.total_return_pct,
                    'max_drawdown_pct': result.max_drawdown_pct,
                    'sharpe_ratio': result.sharpe_ratio,
                    'win_rate_pct': result.win_rate_pct,
                    'profit_factor': result.profit_factor,
                    'total_trades': result.total_trades,
                    'passed': result.passed,
                    'fail_reasons': result.fail_reasons,
                }
            except Exception as e:
                results[sym] = {'error': str(e), 'passed': False}

        return results

    def run_paper_trading_report(self) -> Dict[str, Any]:
        """
        페이퍼 트레이딩 검증 실행 및 결과 수집

        Returns:
            파이프라인 검증 결과 딕셔너리
        """
        from qa_team.paper_trading import PaperTradingSimulator
        from tests.conftest import make_ohlcv

        simulator = PaperTradingSimulator()
        simulator.risk_manager.initialize_trading_day(1_000_000)

        # 표준 시나리오 실행
        scenarios = [
            {
                'name': '정상 매수',
                'signals': [{'symbol': 'AAPL', 'action': 'BUY', 'quantity': 5, 'price': 180.0, 'score': 80.0}]
            },
            {
                'name': '일일 손실 한도 초과',
                'signals': [],  # 한도 초과 상태에서 시작
                'pre_loss': -60_000,  # -6%
            },
            {
                'name': '다중 종목',
                'signals': [
                    {'symbol': f'SYM{i}', 'action': 'BUY', 'quantity': 3, 'price': 100.0 + i * 50, 'score': 80.0}
                    for i in range(3)
                ]
            },
        ]

        results = {}
        for scenario in scenarios:
            sim = PaperTradingSimulator()
            sim.risk_manager.initialize_trading_day(1_000_000)
            if 'pre_loss' in scenario:
                sim.risk_manager.daily_tracker.record_realized_trade(scenario['pre_loss'])

            result = sim.run_scenario(scenario['name'], scenario['signals'])
            results[scenario['name']] = {
                'executed': result.total_orders_executed,
                'rejected': result.total_orders_rejected,
                'pipeline_ok': len(result.pipeline_errors) == 0,
                'risk_ok': result.risk_manager_ok,
                'exec_ok': result.execution_engine_ok,
                'notify_ok': result.notification_format_ok,
                'all_passed': result.all_passed,
            }

        return results

    def generate_report(self, output_file: Optional[str] = None) -> str:
        """
        전체 QA 리포트 생성

        Args:
            output_file: 리포트 저장 경로 (None이면 stdout만)

        Returns:
            리포트 문자열
        """
        ts = self.report_timestamp.strftime("%Y-%m-%d %H:%M:%S")
        lines = [
            "=" * 70,
            "QA 팀 테스트 리포트",
            f"생성 시각: {ts}",
            "=" * 70,
        ]

        # 1. 단위/통합 테스트 실행
        lines.append("\n[1] 단위 테스트 / 통합 테스트 (pytest)")
        lines.append("-" * 70)
        pytest_result = self.run_pytest()
        if pytest_result['passed']:
            lines.append("결과: PASS")
        else:
            lines.append("결과: FAIL")
        if pytest_result['stdout']:
            # pytest 출력에서 요약 줄만 추출
            for line in pytest_result['stdout'].split('\n'):
                if any(keyword in line for keyword in ['passed', 'failed', 'error', 'warning', '====', '----']):
                    lines.append(f"  {line}")

        # 2. 백테스트 결과
        lines.append("\n[2] 백테스트 결과 (전략 검증)")
        lines.append("-" * 70)
        try:
            backtest_results = self.run_backtest_report()
            for sym, res in backtest_results.items():
                if 'error' in res:
                    lines.append(f"  {sym}: ERROR - {res['error']}")
                else:
                    status = "PASS" if res['passed'] else "FAIL"
                    lines.append(
                        f"  {sym} [{status}]: "
                        f"수익률={res['total_return_pct']:+.1f}%, "
                        f"MDD={res['max_drawdown_pct']:.1f}%, "
                        f"승률={res['win_rate_pct']:.0f}%, "
                        f"거래수={res['total_trades']}"
                    )
                    if res.get('fail_reasons'):
                        for reason in res['fail_reasons']:
                            lines.append(f"    - {reason}")
        except Exception as e:
            lines.append(f"  백테스트 실행 오류: {e}")

        # 3. 페이퍼 트레이딩 결과
        lines.append("\n[3] 페이퍼 트레이딩 검증 (파이프라인)")
        lines.append("-" * 70)
        try:
            pt_results = self.run_paper_trading_report()
            for scenario_name, res in pt_results.items():
                status = "PASS" if res['all_passed'] else "FAIL"
                lines.append(
                    f"  {scenario_name} [{status}]: "
                    f"실행={res['executed']}, 거부={res['rejected']}, "
                    f"파이프라인={'OK' if res['pipeline_ok'] else 'FAIL'}"
                )
        except Exception as e:
            lines.append(f"  페이퍼 트레이딩 실행 오류: {e}")

        # 4. 최종 판정
        lines.append("\n" + "=" * 70)
        all_ok = pytest_result['passed']
        lines.append(f"최종 QA 판정: {'PASS' if all_ok else 'FAIL'}")
        lines.append("=" * 70)

        report = "\n".join(lines)

        if output_file:
            os.makedirs(os.path.dirname(output_file), exist_ok=True)
            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(report)
            print(f"리포트 저장: {output_file}")

        return report
