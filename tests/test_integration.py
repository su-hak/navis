"""
통합 테스트 (QA Team - Integration Tests)

전체 파이프라인: Data → Strategy → Risk → Execution 통합 검증

검증 항목:
1. 전체 자동매매 파이프라인 End-to-End
2. 팀 간 인터페이스 (API 계약) 검증
3. 리스크 관리자 ↔ 실행 엔진 연동
4. 전략 엔진 → 리스크 관리자 신호 전달
5. 기획서 핵심 시나리오 검증
"""
import pytest
from conftest import make_ohlcv, make_high_volume_ohlcv


# ============================================================
# 팀 간 인터페이스 검증
# ============================================================

class TestTeamInterfaces:
    """각 팀의 API 계약(산출물) 검증"""

    def test_score_stock_returns_score_result(self, score_calculator, uptrend_df):
        """전략 팀 산출물: score_stock() 함수"""
        from strategy_engine.scoring.score_calculator import ScoreResult
        result = score_calculator.score_stock(
            symbol="AAPL",
            df=uptrend_df,
        )
        assert isinstance(result, ScoreResult)
        assert result.symbol == "AAPL"
        assert 0 <= result.total_score <= 100
        assert result.recommendation in ["BUY", "HOLD", "SELL"]

    def test_signal_generator_returns_signal_or_none(self, signal_generator, uptrend_df):
        """전략 팀 산출물: signal 생성 로직"""
        from strategy_engine.signals.signal_generator import Signal
        signal = signal_generator.generate_buy_signal("AAPL", uptrend_df)
        # Signal 또는 None 반환
        assert signal is None or isinstance(signal, Signal)

    def test_risk_manager_check_order_returns_risk_decision(self, risk_manager, account_1m, empty_positions):
        """리스크 팀 산출물: risk_manager 모듈"""
        from risk_team.core.risk_models import OrderSignal, OrderAction, OrderType, RiskDecision
        risk_manager.initialize_trading_day(1_000_000)
        signal = OrderSignal(
            symbol="TSLA",
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=10,
        )
        decision = risk_manager.check_order(
            signal=signal,
            account=account_1m,
            positions=empty_positions,
            current_price=200.0,
        )
        assert isinstance(decision, RiskDecision)
        assert decision.action is not None
        assert isinstance(decision.allowed, bool)
        assert decision.reason is not None

    def test_execution_engine_returns_order_result(self):
        """실행 팀 산출물: execute_order() 모듈"""
        from execution_team.core.execution_engine import ExecutionEngine
        from execution_team.core.order_manager import OrderManager
        from execution_team.brokers.broker_interface import BrokerInterface
        from execution_team.core.order_models import (
            AccountInfo, OrderStatus, OrderResult, OrderSignal, OrderAction, OrderType
        )

        class SimpleBroker(BrokerInterface):
            def __init__(self, config): super().__init__(config); self._initialized = True
            def connect(self): return True
            def disconnect(self): pass
            def submit_order(self, order): return "BROKER_001"
            def get_order(self, bid): return {'status': OrderStatus.FILLED, 'filled_quantity': 5, 'filled_price': 200.0, 'commission': 1.0}
            def cancel_order(self, bid): return True
            def get_account(self): return AccountInfo(account_id="t", cash=999999, portfolio_value=999999, buying_power=999999, equity=999999, unrealized_pl=0, realized_pl=0)
            def get_positions(self): return []
            def get_position(self, s): return None
            def is_market_open(self): return True
            def get_current_price(self, s): return 200.0

        engine = ExecutionEngine(SimpleBroker({}), OrderManager(), enable_circuit_breaker=False)
        signal = OrderSignal(symbol="AAPL", action=OrderAction.BUY, order_type=OrderType.MARKET, quantity=5)
        result = engine.execute_order(signal)
        assert isinstance(result, OrderResult)
        assert result.order_id is not None


# ============================================================
# 기획서 핵심 시나리오 검증
# ============================================================

class TestKeyScenarios:
    """기획서에 명시된 핵심 시나리오"""

    def test_buy_condition_score_75_and_volume_increase_and_uptrend(self, signal_generator):
        """
        기획서 4. 매수 조건: 점수 ≥ 75 + 거래량 증가 + 상승 추세
        세 조건 모두 충족 시 매수 가능
        """
        from strategy_engine.scoring.score_calculator import ScoreResult
        good_result = ScoreResult(
            symbol="TEST",
            total_score=80.0,         # 점수 ≥ 75
            technical_score=80.0,
            volume_score=90.0,
            trend_score=80.0,
            news_score=60.0,
            financial_score=60.0,
            breakdown={
                'volume': {'volume_ratio': 2.0},    # 거래량 2x 증가
                'trend': {'trend_strength': 70.0},   # 추세 강도 70
                'indicators': {'rsi': 50.0, 'macd_histogram': 0.5},
            }
        )
        can_buy, reasons, confidence = signal_generator.check_buy_conditions(
            good_result, current_price=100.0
        )
        assert can_buy is True

    def test_sell_condition_target_profit_reached(self, signal_generator, uptrend_df):
        """기획서 4. 매도 조건: 목표 수익 도달"""
        from strategy_engine.scoring.score_calculator import ScoreResult
        score_result = ScoreResult(
            symbol="TEST",
            total_score=60.0,
            technical_score=60.0,
            volume_score=60.0,
            trend_score=60.0,
            news_score=60.0,
            financial_score=60.0,
            breakdown={
                'volume': {'volume_ratio': 1.0},
                'trend': {'trend_strength': 60.0},
                'indicators': {'rsi': 55.0, 'macd_histogram': 0.1},
            }
        )
        entry_price = 100.0
        current_price = 111.0  # +11% (10% 이상이므로 익절)
        should_sell, signal_type, reasons, confidence = signal_generator.check_sell_conditions(
            score_result, current_price=current_price, entry_price=entry_price
        )
        assert should_sell is True
        from strategy_engine.signals.signal_generator import SignalType
        assert signal_type == SignalType.TAKE_PROFIT

    def test_sell_condition_stop_loss_triggered(self, signal_generator, uptrend_df):
        """기획서 4. 매도 조건: 손절 도달 (-2%)"""
        from strategy_engine.scoring.score_calculator import ScoreResult
        score_result = ScoreResult(
            symbol="TEST",
            total_score=60.0,
            technical_score=60.0,
            volume_score=60.0,
            trend_score=60.0,
            news_score=60.0,
            financial_score=60.0,
            breakdown={
                'volume': {'volume_ratio': 1.0},
                'trend': {'trend_strength': 60.0},
                'indicators': {'rsi': 55.0, 'macd_histogram': -0.1},
            }
        )
        entry_price = 100.0
        current_price = 97.5  # -2.5% (손절 기준 -2% 이하)
        should_sell, signal_type, reasons, confidence = signal_generator.check_sell_conditions(
            score_result, current_price=current_price, entry_price=entry_price
        )
        assert should_sell is True
        from strategy_engine.signals.signal_generator import SignalType
        assert signal_type == SignalType.STOP_LOSS

    def test_risk_reward_ratio_1_to_3(self, risk_manager):
        """기획서 핵심: 손절 2% / 익절 6% → Risk:Reward = 1:3"""
        stop, take = risk_manager.calculate_stops(100.0, "BUY")
        loss = 100.0 - stop    # 손실 = 2.0
        profit = take - 100.0  # 수익 = 6.0
        ratio = profit / loss  # 3.0
        assert ratio == pytest.approx(3.0, rel=0.01)

    def test_max_5_simultaneous_positions(self, risk_manager, account_1m):
        """기획서 4. 동시 보유 종목 최대 5개 제한"""
        from risk_team.core.risk_models import Position, OrderSignal, OrderAction, OrderType

        positions_5 = [
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
        risk_manager.initialize_trading_day(1_000_000)
        signal = OrderSignal(
            symbol="NEW",
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=5,
        )
        decision = risk_manager.check_order(
            signal=signal,
            account=account_1m,
            positions=positions_5,
            current_price=100.0,
        )
        assert decision.allowed is False, "5개 보유 중 6번째 매수는 거부되어야 함"

    def test_daily_max_loss_5_percent(self, risk_manager, account_1m, empty_positions):
        """기획서 5. 하루 최대 손실 제한 -5%"""
        risk_manager.initialize_trading_day(1_000_000)
        # -5% 손실 기록
        risk_manager.record_trade_result(-50_000)

        from risk_team.core.risk_models import OrderSignal, OrderAction, OrderType
        signal = OrderSignal(
            symbol="TSLA",
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=5,
        )
        decision = risk_manager.check_order(
            signal=signal,
            account=account_1m,
            positions=empty_positions,
            current_price=100.0,
        )
        assert decision.allowed is False
        assert "일일 손실" in decision.reason

    def test_position_sizing_5_to_20_percent(self, risk_manager, account_1m, empty_positions):
        """기획서 4. 1회 투자금 총 자산의 5~20%"""
        from risk_team.core.risk_models import OrderSignal, OrderAction, OrderType
        risk_manager.initialize_trading_day(1_000_000)
        signal = OrderSignal(
            symbol="AAPL",
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=10,
        )
        decision = risk_manager.check_order(
            signal=signal,
            account=account_1m,
            positions=empty_positions,
            current_price=100.0,
        )
        if decision.allowed and decision.invest_pct is not None:
            assert 5.0 <= decision.invest_pct <= 20.0


# ============================================================
# 전략 엔진 → 리스크 관리자 연동 테스트
# ============================================================

class TestStrategyToRiskIntegration:

    def test_signal_feeds_into_risk_check(self, signal_generator, risk_manager, account_1m, uptrend_df):
        """
        전략 엔진 시그널 → 리스크 관리자 체크 연동
        Signal.score, Signal.entry_price → OrderSignal 변환 후 리스크 체크
        """
        from risk_team.core.risk_models import OrderSignal, OrderAction, OrderType

        risk_manager.initialize_trading_day(1_000_000)

        # 1. 전략 엔진에서 시그널 생성
        signal = signal_generator.generate_buy_signal(
            symbol="AAPL",
            df=uptrend_df,
            news_sentiment=0.5,
            news_count=5,
        )

        if signal is None:
            pytest.skip("시그널 미생성 (데이터 조건 미충족, 정상)")

        # 2. 시그널 → 리스크 주문 신호 변환
        risk_signal = OrderSignal(
            symbol=signal.symbol,
            action=OrderAction.BUY,
            order_type=OrderType.MARKET,
            quantity=10,
            reason=f"score={signal.score:.1f}",
        )

        # 3. 리스크 체크
        decision = risk_manager.check_order(
            signal=risk_signal,
            account=account_1m,
            positions=[],
            current_price=signal.entry_price,
        )

        # 리스크 체크 결과 유효성
        assert decision is not None
        assert isinstance(decision.allowed, bool)
        if decision.allowed:
            assert decision.stop_loss_price is not None
            assert decision.take_profit_price is not None
            assert decision.stop_loss_price < signal.entry_price
            assert decision.take_profit_price > signal.entry_price

    def test_risk_status_reflects_position_count(self, risk_manager, account_1m):
        """포지션 수에 따른 리스크 상태 반영"""
        from risk_team.core.risk_models import Position

        positions_3 = [
            Position(
                symbol=f"SYM{i}",
                quantity=10,
                avg_entry_price=100.0,
                current_price=100.0,
                market_value=1000.0,
                unrealized_pl=0.0,
                unrealized_pl_percent=0.0,
            )
            for i in range(3)
        ]

        status = risk_manager.get_risk_status(account_1m, positions_3)
        assert status.position_count == 3
        assert status.can_trade is True  # 5개 미만이므로 거래 가능
