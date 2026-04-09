"""
페이퍼 트레이딩 검증 테스트 (QA Team - Paper Trading)

기획서 9. 테스트 전략 - 페이퍼 트레이딩 검증

검증 항목:
1. 전체 파이프라인 통합 검증 (전략 → 리스크 → 실행)
2. 주문 실행 흐름 (신호 → 리스크 체크 → 브로커 → 체결)
3. 리스크 룰 준수 (일일한도/포지션 한도/중복 방지)
4. 텔레그램 알림 형식 검증
5. 주문 거부/조정 로직 검증
"""
import pytest
from conftest import make_ohlcv


# ============================================================
# 기본 파이프라인 검증
# ============================================================

class TestPipelineIntegration:

    @pytest.fixture
    def simulator(self):
        from qa_team.paper_trading import PaperTradingSimulator
        return PaperTradingSimulator()

    def test_simulator_initializes(self, simulator):
        """시뮬레이터 초기화"""
        assert simulator.signal_generator is not None
        assert simulator.risk_manager is not None
        assert simulator.execution_engine is not None

    def test_empty_scenario_runs_without_error(self, simulator):
        """빈 시나리오 실행"""
        result = simulator.run_scenario("empty", [])
        assert result.total_orders_attempted == 0
        assert result.total_orders_executed == 0

    def test_single_buy_order_executed(self, simulator):
        """단일 매수 주문 실행"""
        simulator.risk_manager.initialize_trading_day(1_000_000)
        signals = [{
            'symbol': 'AAPL',
            'action': 'BUY',
            'quantity': 5,
            'price': 180.0,
            'score': 80.0,
        }]
        result = simulator.run_scenario("single_buy", signals)
        assert result.total_orders_attempted == 1
        assert result.total_orders_executed == 1
        assert result.risk_manager_ok is True
        assert result.execution_engine_ok is True

    def test_multiple_buy_orders(self, simulator):
        """다중 매수 주문 실행"""
        simulator.risk_manager.initialize_trading_day(1_000_000)
        signals = [
            {'symbol': f'SYM{i}', 'action': 'BUY', 'quantity': 5, 'price': 100.0 + i * 10, 'score': 80.0}
            for i in range(3)
        ]
        result = simulator.run_scenario("multi_buy", signals)
        assert result.total_orders_attempted == 3
        assert result.total_orders_executed + result.total_orders_rejected == 3

    def test_order_log_recorded(self, simulator):
        """주문 로그 기록 확인"""
        simulator.risk_manager.initialize_trading_day(1_000_000)
        signals = [{
            'symbol': 'TSLA',
            'action': 'BUY',
            'quantity': 3,
            'price': 200.0,
            'score': 82.0,
        }]
        result = simulator.run_scenario("log_test", signals)
        assert len(result.order_logs) == 1
        log = result.order_logs[0]
        assert log.symbol == 'TSLA'
        assert log.action == 'BUY'
        assert log.quantity > 0
        assert log.price == 200.0

    def test_order_log_has_stop_and_take_profit(self, simulator):
        """주문 로그에 손절/익절가 기록"""
        simulator.risk_manager.initialize_trading_day(1_000_000)
        signals = [{
            'symbol': 'NVDA',
            'action': 'BUY',
            'quantity': 2,
            'price': 450.0,
            'score': 85.0,
        }]
        result = simulator.run_scenario("stop_tp_test", signals)
        executed = [log for log in result.order_logs if log.result == "SUCCESS"]
        if executed:
            log = executed[0]
            assert log.stop_loss is not None
            assert log.take_profit is not None
            assert log.stop_loss < log.price        # 손절가 < 진입가
            assert log.take_profit > log.price      # 익절가 > 진입가


# ============================================================
# 리스크 룰 준수 검증
# ============================================================

class TestRiskRuleCompliance:

    @pytest.fixture
    def simulator(self):
        from qa_team.paper_trading import PaperTradingSimulator
        return PaperTradingSimulator()

    def test_daily_loss_limit_blocks_new_orders(self, simulator):
        """일일 손실 한도 초과 후 신규 주문 거부"""
        # 일일 손실 한도 초과 강제 설정
        simulator.risk_manager.initialize_trading_day(1_000_000)
        simulator.risk_manager.daily_tracker.record_realized_trade(-60_000)  # -6%

        signals = [{
            'symbol': 'AAPL',
            'action': 'BUY',
            'quantity': 10,
            'price': 180.0,
            'score': 90.0,
        }]
        result = simulator.run_scenario("daily_limit_test", signals)
        assert result.total_orders_rejected == 1
        rejected_log = result.order_logs[0]
        assert rejected_log.result == "REJECTED"
        assert "일일 손실" in rejected_log.risk_reason

    def test_position_limit_blocks_6th_position(self, simulator):
        """최대 포지션(5개) 초과 시 거부"""
        from risk_team.core.risk_models import Position
        simulator.risk_manager.initialize_trading_day(1_000_000)

        # 5개 포지션 이미 보유 중으로 설정
        existing_positions = [
            Position(
                symbol=f"SYM{i}",
                quantity=10,
                avg_entry_price=100.0,
                current_price=100.0,
                market_value=1000.0,
                unrealized_pl=0.0,
                unrealized_pl_percent=0.0,
            )
            for i in range(5)
        ]

        from risk_team.core.risk_models import (
            OrderSignal, OrderAction, OrderType, AccountInfo
        )
        account = AccountInfo(
            account_id="test",
            cash=1_000_000,
            portfolio_value=1_000_000,
            buying_power=1_000_000,
            equity=1_000_000,
            unrealized_pl=0.0,
            realized_pl=0.0,
        )
        signal = OrderSignal(
            symbol="NEW_STOCK",
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=10,
        )
        decision = simulator.risk_manager.check_order(
            signal=signal,
            account=account,
            positions=existing_positions,
            current_price=100.0,
        )
        assert decision.allowed is False
        assert "포지션" in decision.reason

    def test_sell_without_position_rejected(self, simulator):
        """보유하지 않은 종목 매도 거부"""
        simulator.risk_manager.initialize_trading_day(1_000_000)
        from risk_team.core.risk_models import (
            OrderSignal, OrderAction, OrderType, AccountInfo
        )
        account = AccountInfo(
            account_id="test",
            cash=1_000_000,
            portfolio_value=1_000_000,
            buying_power=1_000_000,
            equity=1_000_000,
            unrealized_pl=0.0,
            realized_pl=0.0,
        )
        signal = OrderSignal(
            symbol="NOPOSITION",
            action=OrderAction.SELL,
            order_type=OrderType.MARKET,
            quantity=10,
        )
        decision = simulator.risk_manager.check_order(
            signal=signal,
            account=account,
            positions=[],
            current_price=100.0,
        )
        assert decision.allowed is False
        assert "보유하지 않은" in decision.reason

    def test_stop_loss_price_is_2_percent_below_entry(self, simulator):
        """손절가 = 진입가 × (1 - 2%) 검증"""
        from risk_team.core.risk_models import (
            OrderSignal, OrderAction, OrderType, AccountInfo
        )
        simulator.risk_manager.initialize_trading_day(1_000_000)
        account = AccountInfo(
            account_id="test",
            cash=1_000_000,
            portfolio_value=1_000_000,
            buying_power=1_000_000,
            equity=1_000_000,
            unrealized_pl=0.0,
            realized_pl=0.0,
        )
        signal = OrderSignal(
            symbol="TSLA",
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=5,
        )
        entry_price = 200.0
        decision = simulator.risk_manager.check_order(
            signal=signal,
            account=account,
            positions=[],
            current_price=entry_price,
        )
        assert decision.allowed is True
        expected_stop = entry_price * 0.98  # -2%
        assert decision.stop_loss_price == pytest.approx(expected_stop, rel=0.001)

    def test_take_profit_price_is_6_percent_above_entry(self, simulator):
        """익절가 = 진입가 × (1 + 6%) 검증"""
        from risk_team.core.risk_models import (
            OrderSignal, OrderAction, OrderType, AccountInfo
        )
        simulator.risk_manager.initialize_trading_day(1_000_000)
        account = AccountInfo(
            account_id="test",
            cash=1_000_000,
            portfolio_value=1_000_000,
            buying_power=1_000_000,
            equity=1_000_000,
            unrealized_pl=0.0,
            realized_pl=0.0,
        )
        signal = OrderSignal(
            symbol="TSLA",
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=5,
        )
        entry_price = 200.0
        decision = simulator.risk_manager.check_order(
            signal=signal,
            account=account,
            positions=[],
            current_price=entry_price,
        )
        assert decision.allowed is True
        expected_tp = entry_price * 1.06  # +6%
        assert decision.take_profit_price == pytest.approx(expected_tp, rel=0.001)


# ============================================================
# 텔레그램 알림 형식 검증
# ============================================================

class TestNotificationFormat:

    @pytest.fixture
    def simulator(self):
        from qa_team.paper_trading import PaperTradingSimulator
        return PaperTradingSimulator()

    def test_notification_format_validated(self, simulator):
        """알림 형식 검증 통과"""
        simulator.risk_manager.initialize_trading_day(1_000_000)
        signals = [{
            'symbol': 'AAPL',
            'action': 'BUY',
            'quantity': 5,
            'price': 180.0,
            'score': 80.0,
        }]
        result = simulator.run_scenario("notify_test", signals)
        assert result.notification_format_ok is True

    def test_notification_contains_symbol(self, simulator):
        """알림에 종목 심볼 포함"""
        from qa_team.paper_trading.simulator import OrderLog
        log = OrderLog(
            timestamp="2026-04-09T10:00:00",
            symbol="TSLA",
            action="BUY",
            quantity=10,
            price=210.0,
            total_amount=2100.0,
            commission=2.1,
            risk_decision="ALLOW",
            risk_reason="리스크 체크 통과",
            stop_loss=205.8,
            take_profit=222.6,
            result="SUCCESS",
            message="체결 완료 @ $210.00",
        )
        msg = simulator._format_notification(log)
        assert "TSLA" in msg
        assert "종목" in msg
        assert "가격" in msg
        assert "수량" in msg

    def test_buy_notification_format(self, simulator):
        """매수 알림 형식 확인"""
        from qa_team.paper_trading.simulator import OrderLog
        log = OrderLog(
            timestamp="2026-04-09T10:00:00",
            symbol="NVDA",
            action="BUY",
            quantity=3,
            price=500.0,
            total_amount=1500.0,
            commission=1.5,
            risk_decision="ALLOW",
            risk_reason="리스크 체크 통과",
            stop_loss=490.0,
            take_profit=530.0,
            result="SUCCESS",
        )
        msg = simulator._format_notification(log)
        assert "[매수 체결]" in msg

    def test_sell_notification_format(self, simulator):
        """매도 알림 형식 확인"""
        from qa_team.paper_trading.simulator import OrderLog
        log = OrderLog(
            timestamp="2026-04-09T10:00:00",
            symbol="NVDA",
            action="SELL",
            quantity=3,
            price=530.0,
            total_amount=1590.0,
            commission=1.6,
            risk_decision="ALLOW",
            risk_reason="매도 리스크 체크 통과",
            stop_loss=None,
            take_profit=None,
            result="SUCCESS",
        )
        msg = simulator._format_notification(log)
        assert "[매도 체결]" in msg


# ============================================================
# 전체 파이프라인 통합 테스트
# ============================================================

class TestFullPipelineIntegration:

    def test_full_pipeline_with_real_strategy(self, uptrend_df):
        """실제 전략 엔진을 사용한 전체 파이프라인"""
        from qa_team.paper_trading import PaperTradingSimulator
        simulator = PaperTradingSimulator()
        result = simulator.run_full_pipeline_test("AAPL", uptrend_df)
        # 파이프라인이 에러 없이 실행되어야 함
        assert len(result.pipeline_errors) == 0
        assert result.risk_manager_ok is True
        assert result.execution_engine_ok is True

    def test_pipeline_result_summary(self, uptrend_df):
        """파이프라인 결과 요약 출력"""
        from qa_team.paper_trading import PaperTradingSimulator
        simulator = PaperTradingSimulator()
        simulator.risk_manager.initialize_trading_day(1_000_000)
        result = simulator.run_full_pipeline_test("TSLA", uptrend_df)
        summary = result.summary()
        assert "페이퍼 트레이딩 검증" in summary
        assert "주문 시도" in summary

    def test_all_passed_when_no_errors(self):
        """파이프라인 에러 없을 때 all_passed True"""
        from qa_team.paper_trading import SimulationResult
        result = SimulationResult(
            total_orders_attempted=1,
            total_orders_executed=1,
            total_orders_rejected=0,
            total_orders_adjusted=0,
        )
        result.strategy_engine_ok = True
        result.risk_manager_ok = True
        result.execution_engine_ok = True
        result.notification_format_ok = True
        assert result.all_passed is True

    def test_all_failed_when_pipeline_error(self):
        """파이프라인 에러 있을 때 all_passed False"""
        from qa_team.paper_trading import SimulationResult
        result = SimulationResult(
            total_orders_attempted=1,
            total_orders_executed=0,
            total_orders_rejected=1,
            total_orders_adjusted=0,
        )
        result.strategy_engine_ok = True
        result.risk_manager_ok = True
        result.execution_engine_ok = True
        result.pipeline_errors.append("테스트 오류")
        assert result.all_passed is False
